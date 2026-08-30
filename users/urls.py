from django.urls import path

from users.views import AgentListView, MeView

urlpatterns = [
    path("users/me/", MeView.as_view(), name="user-me"),
    path("agents/", AgentListView.as_view(), name="agent-list"),
]
