from rest_framework.permissions import BasePermission

from users.permissions import IsAgent

__all__ = ["IsAgent", "IsTicketOwnerOrAgent"]


class IsTicketOwnerOrAgent(BasePermission):
    """Verificación de objeto para las acciones de detalle. El filtrado
    grueso —qué solicitudes existen para este usuario— ya lo hace
    `visible_to()` en el queryset (spec.md RN-10, plan.md D-07); esto es la
    comprobación a nivel de objeto que la acompaña.

    No decide transiciones de estado: cuál transición puede ejecutar cada rol
    se resuelve en `tickets.services.change_status` contra `TRANSITIONS`
    (plan.md D-03/D-04), no aquí.
    """

    message = "No tiene acceso a esta solicitud."

    def has_object_permission(self, request, view, obj) -> bool:
        user = request.user
        return bool(user.is_agent or obj.created_by_id == user.id)
