import secrets
import uuid

from django.conf import settings
from django.db import models

# Tokens de rol usados en TRANSITIONS. No son el `role` del usuario: AGENT sí
# corresponde a User.Role.AGENT, pero OWNER es contextual (el autor de *este*
# ticket), no un rol almacenado.
AGENT = "AGENT"
OWNER = "OWNER"


class Priority(models.TextChoices):
    LOW = "LOW", "Low"
    MEDIUM = "MEDIUM", "Medium"
    HIGH = "HIGH", "High"
    CRITICAL = "CRITICAL", "Critical"


class Status(models.TextChoices):
    NEW = "NEW", "New"
    ASSIGNED = "ASSIGNED", "Assigned"
    IN_PROGRESS = "IN_PROGRESS", "In progress"
    PENDING_CUSTOMER = "PENDING_CUSTOMER", "Pending customer"
    RESOLVED = "RESOLVED", "Resolved"
    CLOSED = "CLOSED", "Closed"


# Máquina de estados como dato (plan.md D-03). Clave (desde, hacia), valor: el
# conjunto de roles que pueden ejecutar esa transición. Si la clave no existe,
# la transición no existe (-> InvalidStatusTransition); si existe pero el rol
# del actor no está en el conjunto, existe pero le está vedada
# (-> TransitionNotAllowedForRole). Deriva de spec.md §4.1.
TRANSITIONS = {
    (Status.NEW, Status.ASSIGNED): {AGENT},
    (Status.NEW, Status.IN_PROGRESS): {AGENT},
    (Status.NEW, Status.CLOSED): {AGENT},
    (Status.ASSIGNED, Status.IN_PROGRESS): {AGENT},
    (Status.ASSIGNED, Status.PENDING_CUSTOMER): {AGENT},
    (Status.ASSIGNED, Status.CLOSED): {AGENT},
    (Status.IN_PROGRESS, Status.PENDING_CUSTOMER): {AGENT},
    (Status.IN_PROGRESS, Status.RESOLVED): {AGENT},
    (Status.IN_PROGRESS, Status.CLOSED): {AGENT},
    (Status.PENDING_CUSTOMER, Status.IN_PROGRESS): {AGENT},
    (Status.PENDING_CUSTOMER, Status.RESOLVED): {AGENT},
    (Status.PENDING_CUSTOMER, Status.CLOSED): {AGENT},
    (Status.RESOLVED, Status.IN_PROGRESS): {AGENT},
    (Status.RESOLVED, Status.CLOSED): {AGENT, OWNER},
    # CLOSED es final: no aparece como origen (RN-05).
}

# Estados a los que solo se puede llegar con agente asignado (RN-04).
STATUSES_REQUIRING_ASSIGNMENT = {Status.IN_PROGRESS, Status.RESOLVED}


def allowed_transitions(from_status):
    """Destinos declarados desde `from_status`, sin filtrar por rol. Alimenta
    el campo `allowed` del error `InvalidStatusTransition` (plan.md §4)."""
    return sorted(to for (frm, to) in TRANSITIONS if frm == from_status)


def _generate_reference() -> str:
    return f"TCK-{secrets.token_hex(4).upper()}"


class TicketQuerySet(models.QuerySet):
    def visible_to(self, user):
        """RN-10 / plan.md D-07: un cliente solo ve lo suyo; un agente, todo."""
        if user.is_agent:
            return self
        return self.filter(created_by=user)


class Ticket(models.Model):
    Priority = Priority
    Status = Status

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(max_length=20, unique=True, editable=False)
    subject = models.CharField(max_length=200)
    description = models.TextField()
    priority = models.CharField(max_length=16, choices=Priority.choices)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.NEW)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="tickets_created",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tickets_assigned",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    objects = TicketQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["priority"]),
            models.Index(fields=["assigned_to"]),
            models.Index(fields=["created_by"]),
        ]

    def __str__(self) -> str:
        return f"{self.reference} — {self.subject}"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self._generate_unique_reference()
        super().save(*args, **kwargs)

    @classmethod
    def _generate_unique_reference(cls) -> str:
        for _ in range(10):
            candidate = _generate_reference()
            if not cls.objects.filter(reference=candidate).exists():
                return candidate
        raise RuntimeError("No se pudo generar una referencia única de ticket.")


class TicketComment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    body = models.TextField()
    is_internal = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"Comentario de {self.author} en {self.ticket.reference}"


class TicketEvent(models.Model):
    """Historial inmutable: se crea, nunca se modifica ni se borra (spec.md §4.3,
    plan.md §3). No expone `update()`/`delete()` — eso se hace cumplir en la
    API (Hito 3), no aquí."""

    class EventType(models.TextChoices):
        CREATED = "CREATED", "Created"
        STATUS_CHANGED = "STATUS_CHANGED", "Status changed"
        ASSIGNED = "ASSIGNED", "Assigned"
        UNASSIGNED = "UNASSIGNED", "Unassigned"
        PRIORITY_CHANGED = "PRIORITY_CHANGED", "Priority changed"
        COMMENT_ADDED = "COMMENT_ADDED", "Comment added"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    event_type = models.CharField(max_length=24, choices=EventType.choices)
    field = models.CharField(max_length=64, null=True, blank=True)
    old_value = models.CharField(max_length=64, null=True, blank=True)
    new_value = models.CharField(max_length=64, null=True, blank=True)
    note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.event_type} — {self.ticket.reference}"
