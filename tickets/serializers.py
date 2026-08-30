from rest_framework import serializers

from tickets.models import Priority, Status, Ticket, TicketComment, TicketEvent
from users.models import User
from users.serializers import UserSerializer


class TicketCreateSerializer(serializers.Serializer):
    """RN-01: el resto de los campos (estado, autor, agente) los decide
    `services.create_ticket`; lo que el cliente envíe además de esto se
    ignora (TC-014)."""

    subject = serializers.CharField(max_length=200)
    description = serializers.CharField()
    priority = serializers.ChoiceField(choices=Priority.choices)


class TicketSerializer(serializers.ModelSerializer):
    """Representación de solo lectura, usada tanto en el listado como en el
    detalle."""

    created_by = UserSerializer(read_only=True)
    assigned_to = UserSerializer(read_only=True)

    class Meta:
        model = Ticket
        fields = [
            "id",
            "reference",
            "subject",
            "description",
            "priority",
            "status",
            "created_by",
            "assigned_to",
            "created_at",
            "updated_at",
            "assigned_at",
            "resolved_at",
            "closed_at",
        ]
        read_only_fields = fields


class TicketPriorityUpdateSerializer(serializers.Serializer):
    """RN-12: único campo editable por PATCH; asunto y descripción no se
    tocan después de creada la solicitud."""

    priority = serializers.ChoiceField(choices=Priority.choices)
    note = serializers.CharField(required=False, allow_blank=True, default="")


class TicketAssignSerializer(serializers.Serializer):
    assigned_to = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    note = serializers.CharField(required=False, allow_blank=True, default="")


class TicketNoteSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, default="")


class TicketStatusChangeSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Status.choices)
    note = serializers.CharField(required=False, allow_blank=True, default="")


class TicketCommentCreateSerializer(serializers.Serializer):
    body = serializers.CharField()
    is_internal = serializers.BooleanField(required=False, default=True)


class TicketCommentSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)

    class Meta:
        model = TicketComment
        fields = ["id", "author", "body", "is_internal", "created_at"]
        read_only_fields = fields


class TicketEventSerializer(serializers.ModelSerializer):
    actor = UserSerializer(read_only=True)

    class Meta:
        model = TicketEvent
        fields = [
            "id",
            "event_type",
            "actor",
            "field",
            "old_value",
            "new_value",
            "note",
            "created_at",
        ]
        read_only_fields = fields
