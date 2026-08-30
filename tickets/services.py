"""Lógica de dominio de tickets (plan.md D-01). Las vistas (Hito 3) validan
entrada y traducen errores; estas funciones aplican las reglas de negocio de
spec.md §5 y escriben el historial, siempre dentro de una transacción."""

from django.db import transaction
from django.utils import timezone

from tickets.exceptions import (
    CloseReasonRequired,
    InvalidStatusTransition,
    NotAnAgent,
    TicketClosed,
    TicketNotAssigned,
    TransitionNotAllowedForRole,
)
from tickets.models import (
    AGENT,
    OWNER,
    STATUSES_REQUIRING_ASSIGNMENT,
    TRANSITIONS,
    Ticket,
    TicketComment,
    TicketEvent,
    allowed_transitions,
)


def _actor_tokens(ticket: Ticket, actor) -> set:
    tokens = set()
    if actor.is_agent:
        tokens.add(AGENT)
    if ticket.created_by_id == actor.id:
        tokens.add(OWNER)
    return tokens


def _record_event(
    ticket: Ticket,
    actor,
    event_type: str,
    *,
    field: str | None = None,
    old_value: str | None = None,
    new_value: str | None = None,
    note: str = "",
) -> TicketEvent:
    return TicketEvent.objects.create(
        ticket=ticket,
        actor=actor,
        event_type=event_type,
        field=field,
        old_value=old_value,
        new_value=new_value,
        note=note or "",
    )


def _apply_status_change(ticket: Ticket, *, actor, new_status: str, note: str = "") -> Ticket:
    """Muta el estado y registra el evento, sin validar la transición: quien
    llama ya decidió que este cambio debe ocurrir (por política, en
    `change_status`, o como efecto automático de `assign_ticket`, RN-07)."""
    old_status = ticket.status
    ticket.status = new_status
    update_fields = ["status", "updated_at"]
    now = timezone.now()
    if new_status == Ticket.Status.RESOLVED:
        ticket.resolved_at = now
        update_fields.append("resolved_at")
    if new_status == Ticket.Status.CLOSED:
        ticket.closed_at = now
        update_fields.append("closed_at")
    ticket.save(update_fields=update_fields)
    _record_event(
        ticket,
        actor,
        TicketEvent.EventType.STATUS_CHANGED,
        field="status",
        old_value=old_status,
        new_value=new_status,
        note=note,
    )
    return ticket


@transaction.atomic
def create_ticket(*, author, subject: str, description: str, priority: str) -> Ticket:
    """RN-01: toda solicitud nace en NEW, sin agente, con el usuario
    autenticado como autor."""
    ticket = Ticket.objects.create(
        subject=subject,
        description=description,
        priority=priority,
        created_by=author,
    )
    _record_event(ticket, author, TicketEvent.EventType.CREATED)
    return ticket


@transaction.atomic
def assign_ticket(*, ticket: Ticket, actor, assignee, note: str = "") -> Ticket:
    """RN-06: solo se asigna a un AGENT. RN-07: asignar en NEW mueve
    automáticamente a ASSIGNED y registra ambos eventos."""
    ticket = Ticket.objects.select_for_update().get(pk=ticket.pk)
    if ticket.status == Ticket.Status.CLOSED:
        raise TicketClosed
    if not assignee.is_agent:
        raise NotAnAgent

    previous_assignee = ticket.assigned_to
    was_new = ticket.status == Ticket.Status.NEW

    ticket.assigned_to = assignee
    update_fields = ["assigned_to", "updated_at"]
    if ticket.assigned_at is None:
        ticket.assigned_at = timezone.now()
        update_fields.append("assigned_at")
    ticket.save(update_fields=update_fields)

    _record_event(
        ticket,
        actor,
        TicketEvent.EventType.ASSIGNED,
        field="assigned_to",
        old_value=previous_assignee.username if previous_assignee else None,
        new_value=assignee.username,
        note=note,
    )

    if was_new:
        _apply_status_change(ticket, actor=actor, new_status=Ticket.Status.ASSIGNED)

    return ticket


@transaction.atomic
def unassign_ticket(*, ticket: Ticket, actor, note: str = "") -> Ticket:
    ticket = Ticket.objects.select_for_update().get(pk=ticket.pk)
    if ticket.status == Ticket.Status.CLOSED:
        raise TicketClosed

    previous_assignee = ticket.assigned_to
    ticket.assigned_to = None
    ticket.save(update_fields=["assigned_to", "updated_at"])

    _record_event(
        ticket,
        actor,
        TicketEvent.EventType.UNASSIGNED,
        field="assigned_to",
        old_value=previous_assignee.username if previous_assignee else None,
        new_value=None,
        note=note,
    )
    return ticket


@transaction.atomic
def change_status(*, ticket: Ticket, actor, new_status: str, note: str = "") -> Ticket:
    """Resuelve dos preguntas por separado (plan.md D-03/D-04):
    ¿existe la transición? -> InvalidStatusTransition (409) si no.
    ¿el rol del actor puede ejecutarla? -> TransitionNotAllowedForRole (403) si no.
    """
    ticket = Ticket.objects.select_for_update().get(pk=ticket.pk)
    current_status = ticket.status

    if current_status == Ticket.Status.CLOSED:
        raise TicketClosed

    key = (current_status, new_status)
    allowed_roles = TRANSITIONS.get(key)
    if allowed_roles is None:
        raise InvalidStatusTransition(
            current_status, new_status, allowed_transitions(current_status)
        )

    if allowed_roles.isdisjoint(_actor_tokens(ticket, actor)):
        raise TransitionNotAllowedForRole(current_status, new_status)

    # RN-04: sin agente asignado no se puede entrar a IN_PROGRESS ni a RESOLVED.
    if new_status in STATUSES_REQUIRING_ASSIGNMENT and ticket.assigned_to_id is None:
        raise TicketNotAssigned

    # RN-16: cerrar algo que no está en RESOLVED exige motivo.
    if new_status == Ticket.Status.CLOSED and current_status != Ticket.Status.RESOLVED and not note:
        raise CloseReasonRequired

    return _apply_status_change(ticket, actor=actor, new_status=new_status, note=note)


@transaction.atomic
def change_priority(*, ticket: Ticket, actor, new_priority: str, note: str = "") -> Ticket:
    """RN-12: solo un agente cambia la prioridad; queda en el historial. La
    verificación de que `actor` es agente es responsabilidad de la vista
    (permiso de transporte), igual que en `add_comment`; aquí solo se aplica
    la regla que no depende de quién llama: un ticket cerrado no admite el
    cambio (RN-05)."""
    ticket = Ticket.objects.select_for_update().get(pk=ticket.pk)
    if ticket.status == Ticket.Status.CLOSED:
        raise TicketClosed

    old_priority = ticket.priority
    ticket.priority = new_priority
    ticket.save(update_fields=["priority", "updated_at"])

    _record_event(
        ticket,
        actor,
        TicketEvent.EventType.PRIORITY_CHANGED,
        field="priority",
        old_value=old_priority,
        new_value=new_priority,
        note=note,
    )
    return ticket


@transaction.atomic
def add_comment(*, ticket: Ticket, actor, body: str, is_internal: bool = True) -> TicketComment:
    """RN-08: un cliente solo puede comentar en público, sin importar lo que
    pida; RN-05: CLOSED no admite comentarios nuevos."""
    ticket = Ticket.objects.select_for_update().get(pk=ticket.pk)
    if ticket.status == Ticket.Status.CLOSED:
        raise TicketClosed

    if not actor.is_agent:
        is_internal = False

    comment = TicketComment.objects.create(
        ticket=ticket,
        author=actor,
        body=body,
        is_internal=is_internal,
    )
    _record_event(ticket, actor, TicketEvent.EventType.COMMENT_ADDED)
    return comment
