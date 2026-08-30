from rest_framework import serializers

from users.models import User


class UserSerializer(serializers.ModelSerializer):
    """Representación de solo lectura de un usuario (yo mismo o un agente)."""

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "role"]
        read_only_fields = fields
