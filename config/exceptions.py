from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from tickets.exceptions import DomainError


def exception_handler(exc, context):
    """Traduce un `DomainError` de `tickets` al formato de error único de
    plan.md §4: `{"error": {"code": ..., "message": ..., ...extra}}`. Para
    cualquier otra excepción, delega en el handler por defecto de DRF."""
    if isinstance(exc, DomainError):
        body = {"code": exc.code, "message": exc.message, **exc.extra}
        return Response({"error": body}, status=exc.status_code)
    return drf_exception_handler(exc, context)
