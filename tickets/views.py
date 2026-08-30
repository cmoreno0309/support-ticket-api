from rest_framework import mixins, viewsets
from rest_framework import status as http_status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from tickets import services
from tickets.filters import ORDERING_FIELDS, SEARCH_FIELDS, TicketFilter
from tickets.models import Ticket
from tickets.permissions import IsAgent, IsTicketOwnerOrAgent
from tickets.serializers import (
    TicketAssignSerializer,
    TicketCommentCreateSerializer,
    TicketCommentSerializer,
    TicketCreateSerializer,
    TicketEventSerializer,
    TicketNoteSerializer,
    TicketPriorityUpdateSerializer,
    TicketSerializer,
    TicketStatusChangeSerializer,
)


class TicketViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Las vistas validan entrada y delegan en `tickets.services`; no
    contienen reglas de negocio (plan.md D-01). PUT/DELETE no se exponen:
    no hay edición completa del ticket ni borrado (RN-12, D-02)."""

    http_method_names = ["get", "post", "patch", "head", "options"]
    filterset_class = TicketFilter
    search_fields = SEARCH_FIELDS
    ordering_fields = ORDERING_FIELDS

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Ticket.objects.none()
        return Ticket.objects.visible_to(self.request.user).select_related(
            "created_by", "assigned_to"
        )

    def get_permissions(self):
        if self.action in {"partial_update", "assign", "unassign"}:
            classes = [IsAuthenticated, IsAgent]
        elif self.action in {"retrieve", "comments", "status", "history"}:
            classes = [IsAuthenticated, IsTicketOwnerOrAgent]
        else:
            classes = [IsAuthenticated]
        return [permission_class() for permission_class in classes]

    def get_serializer_class(self):
        if self.action == "create":
            return TicketCreateSerializer
        if self.action == "partial_update":
            return TicketPriorityUpdateSerializer
        if self.action == "assign":
            return TicketAssignSerializer
        if self.action == "unassign":
            return TicketNoteSerializer
        if self.action == "status":
            return TicketStatusChangeSerializer
        if self.action == "comments":
            if self.request.method == "POST":
                return TicketCommentCreateSerializer
            return TicketCommentSerializer
        if self.action == "history":
            return TicketEventSerializer
        return TicketSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket = services.create_ticket(author=request.user, **serializer.validated_data)
        output = TicketSerializer(ticket, context=self.get_serializer_context())
        return Response(output.data, status=http_status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        ticket = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket = services.change_priority(
            ticket=ticket,
            actor=request.user,
            new_priority=serializer.validated_data["priority"],
            note=serializer.validated_data["note"],
        )
        return Response(TicketSerializer(ticket, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        ticket = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket = services.assign_ticket(
            ticket=ticket,
            actor=request.user,
            assignee=serializer.validated_data["assigned_to"],
            note=serializer.validated_data["note"],
        )
        return Response(TicketSerializer(ticket, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"])
    def unassign(self, request, pk=None):
        ticket = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket = services.unassign_ticket(
            ticket=ticket, actor=request.user, note=serializer.validated_data["note"]
        )
        return Response(TicketSerializer(ticket, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"])
    def status(self, request, pk=None):
        ticket = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket = services.change_status(
            ticket=ticket,
            actor=request.user,
            new_status=serializer.validated_data["status"],
            note=serializer.validated_data["note"],
        )
        return Response(TicketSerializer(ticket, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["get", "post"])
    def comments(self, request, pk=None):
        ticket = self.get_object()
        if request.method == "POST":
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            comment = services.add_comment(
                ticket=ticket,
                actor=request.user,
                body=serializer.validated_data["body"],
                is_internal=serializer.validated_data["is_internal"],
            )
            output = TicketCommentSerializer(comment, context=self.get_serializer_context())
            return Response(output.data, status=http_status.HTTP_201_CREATED)

        # RN-08: los comentarios internos solo los ve un agente.
        queryset = ticket.comments.all()
        if not request.user.is_agent:
            queryset = queryset.filter(is_internal=False)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        ticket = self.get_object()
        serializer = self.get_serializer(ticket.events.all(), many=True)
        return Response(serializer.data)
