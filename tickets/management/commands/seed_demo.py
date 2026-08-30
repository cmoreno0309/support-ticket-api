from django.core.management.base import BaseCommand
from django.db import transaction

from tickets import services
from tickets.models import Priority, Status, Ticket
from users.models import User

DEMO_PASSWORD = "demo12345"

DEMO_AGENTS = ["agent_1", "agent_2"]
DEMO_CUSTOMERS = ["customer_1", "customer_2", "customer_3"]


def _get_or_create_user(username: str, role: str) -> User:
    user, created = User.objects.get_or_create(username=username, defaults={"role": role})
    if created:
        user.set_password(DEMO_PASSWORD)
        user.save(update_fields=["password"])
    return user


class Command(BaseCommand):
    help = "Crea agentes, clientes y solicitudes de ejemplo para explorar la API (spec.md, pregunta abierta #1)."

    @transaction.atomic
    def handle(self, *args, **options):
        agent_1 = _get_or_create_user("agent_1", User.Role.AGENT)
        agent_2 = _get_or_create_user("agent_2", User.Role.AGENT)
        customer_1 = _get_or_create_user("customer_1", User.Role.CUSTOMER)
        customer_2 = _get_or_create_user("customer_2", User.Role.CUSTOMER)
        customer_3 = _get_or_create_user("customer_3", User.Role.CUSTOMER)

        if Ticket.objects.filter(created_by__in=[customer_1, customer_2, customer_3]).exists():
            self.stdout.write("Ya existen solicitudes de demo; no se crean duplicados.")
            return

        # NEW: recién creada, sin agente.
        services.create_ticket(
            author=customer_1,
            subject="No enciende el monitor",
            description="El monitor no enciende desde esta mañana.",
            priority=Priority.MEDIUM,
        )

        # ASSIGNED: un agente la tomó, todavía no la empezó a trabajar.
        assigned = services.create_ticket(
            author=customer_2,
            subject="Error al iniciar sesión",
            description="El sistema rechaza credenciales que sabemos correctas.",
            priority=Priority.HIGH,
        )
        services.assign_ticket(ticket=assigned, actor=agent_1, assignee=agent_1)

        # IN_PROGRESS: agente trabajándola activamente, con un comentario interno.
        in_progress = services.create_ticket(
            author=customer_3,
            subject="Impresora de red no responde",
            description="Ningún equipo del piso 3 puede imprimir.",
            priority=Priority.HIGH,
        )
        services.assign_ticket(ticket=in_progress, actor=agent_2, assignee=agent_2)
        services.change_status(ticket=in_progress, actor=agent_2, new_status=Status.IN_PROGRESS)
        services.add_comment(
            ticket=in_progress,
            actor=agent_2,
            body="Reiniciando el spooler de impresión del servidor.",
            is_internal=True,
        )

        # PENDING_CUSTOMER: a la espera de información del cliente.
        pending = services.create_ticket(
            author=customer_1,
            subject="VPN se desconecta cada pocos minutos",
            description="La VPN corporativa se cae de forma intermitente.",
            priority=Priority.MEDIUM,
        )
        services.assign_ticket(ticket=pending, actor=agent_1, assignee=agent_1)
        services.change_status(ticket=pending, actor=agent_1, new_status=Status.IN_PROGRESS)
        services.change_status(
            ticket=pending,
            actor=agent_1,
            new_status=Status.PENDING_CUSTOMER,
            note="Se pide el log de conexión del cliente VPN.",
        )

        # RESOLVED: a la espera de que el cliente la cierre (spec.md CA-14).
        resolved = services.create_ticket(
            author=customer_2,
            subject="Solicitud de licencia de software",
            description="Necesito una licencia de la suite de diseño.",
            priority=Priority.LOW,
        )
        services.assign_ticket(ticket=resolved, actor=agent_2, assignee=agent_2)
        services.change_status(ticket=resolved, actor=agent_2, new_status=Status.IN_PROGRESS)
        services.change_status(
            ticket=resolved,
            actor=agent_2,
            new_status=Status.RESOLVED,
            note="Licencia asignada y notificada por correo.",
        )

        # CLOSED por el agente, con motivo, sin pasar por RESOLVED (RN-15/RN-16).
        closed = services.create_ticket(
            author=customer_3,
            subject="Solicitud duplicada de acceso a carpeta compartida",
            description="Ya se había pedido este mismo acceso la semana pasada.",
            priority=Priority.LOW,
        )
        services.assign_ticket(ticket=closed, actor=agent_1, assignee=agent_1)
        services.change_status(
            ticket=closed,
            actor=agent_1,
            new_status=Status.CLOSED,
            note="Duplicado de una solicitud equivalente ya en curso; se cierra sin acción adicional.",
        )

        self.stdout.write(
            self.style.SUCCESS("Datos de demo creados: 2 agentes, 3 clientes, 6 solicitudes.")
        )
        self.stdout.write(
            f"Usuarios: {', '.join(DEMO_AGENTS + DEMO_CUSTOMERS)} — contraseña: {DEMO_PASSWORD}"
        )
