from rest_framework.generics import ListAPIView, RetrieveAPIView

from users.models import User
from users.permissions import IsAgent
from users.serializers import UserSerializer


class MeView(RetrieveAPIView):
    """GET /users/me/ — datos del usuario autenticado, incluido su rol."""

    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class AgentListView(ListAPIView):
    """GET /agents/ — solo agentes; sirve para elegir a quién asignar un ticket."""

    serializer_class = UserSerializer
    permission_classes = [IsAgent]
    queryset = User.objects.filter(role=User.Role.AGENT).order_by("username")
