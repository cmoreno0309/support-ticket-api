from django_filters import rest_framework as filters

from tickets.models import Ticket

# plan.md §4: búsqueda sobre asunto y descripción, orden por estas tres.
SEARCH_FIELDS = ["subject", "description"]
ORDERING_FIELDS = ["created_at", "priority", "status"]


class TicketFilter(filters.FilterSet):
    unassigned = filters.BooleanFilter(field_name="assigned_to", lookup_expr="isnull")
    created_after = filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = Ticket
        fields = ["status", "priority", "assigned_to"]
