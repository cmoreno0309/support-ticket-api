class DomainError(Exception):
    """Base de los errores de negocio de `tickets`. El handler de
    `config.exceptions` (Hito 2, T-07) los traduce al formato único de
    plan.md §4."""

    code = "domain_error"
    status_code = 400

    def __init__(self, message: str, **extra):
        self.message = message
        self.extra = extra
        super().__init__(message)


class InvalidStatusTransition(DomainError):
    """La transición (desde, hacia) no existe en `TRANSITIONS`: el estado del
    recurso no lo permite, sin importar el rol de quien pide el cambio
    (RN-03). Distinto de `TransitionNotAllowedForRole`: aquí ni siquiera hay
    una transición que autorizar."""

    code = "invalid_status_transition"
    status_code = 409

    def __init__(self, from_status, to_status, allowed):
        self.from_status = from_status
        self.to_status = to_status
        self.allowed = list(allowed)
        super().__init__(
            f"No se puede pasar de {from_status} a {to_status}.",
            allowed=self.allowed,
        )


class TransitionNotAllowedForRole(DomainError):
    """La transición (desde, hacia) existe en `TRANSITIONS`, pero el rol de
    quien la pide no está en el conjunto autorizado (RN-02, RN-03). El
    recurso sí admite ese cambio de estado; quien lo pide no puede
    ejecutarlo."""

    code = "transition_not_allowed_for_role"
    status_code = 403

    def __init__(self, from_status, to_status):
        self.from_status = from_status
        self.to_status = to_status
        super().__init__(f"No tiene permiso para pasar de {from_status} a {to_status}.")


class TicketClosed(DomainError):
    """RN-05: `CLOSED` es final. No admite cambios de estado, asignación,
    prioridad ni nuevos comentarios."""

    code = "ticket_closed"
    status_code = 409

    def __init__(self, message: str = "La solicitud está cerrada y no admite cambios."):
        super().__init__(message)


class NotAnAgent(DomainError):
    """RN-06: solo se puede asignar una solicitud a un usuario con rol
    AGENT."""

    code = "not_an_agent"
    status_code = 400

    def __init__(self, message: str = "Solo se puede asignar a un usuario con rol de agente."):
        super().__init__(message)


class TicketNotAssigned(DomainError):
    """RN-04: no se puede pasar a IN_PROGRESS ni a RESOLVED sin agente
    asignado."""

    code = "ticket_not_assigned"
    status_code = 409

    def __init__(self, message: str = "La solicitud no tiene un agente asignado."):
        super().__init__(message)


class CloseReasonRequired(DomainError):
    """RN-16: al cerrar una solicitud que no está en RESOLVED, la nota es
    obligatoria: es el motivo del cierre."""

    code = "close_reason_required"
    status_code = 400

    def __init__(
        self, message: str = "Debe indicar un motivo para cerrar una solicitud no resuelta."
    ):
        super().__init__(message)
