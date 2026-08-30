from rest_framework.permissions import BasePermission


class IsAgent(BasePermission):
    """Permite el acceso únicamente a usuarios con rol AGENT (spec.md §3)."""

    message = "Se requiere rol de agente."

    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_authenticated and request.user.is_agent)
