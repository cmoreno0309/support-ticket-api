from rest_framework.routers import SimpleRouter

from tickets.views import TicketViewSet

router = SimpleRouter()
router.register("tickets", TicketViewSet, basename="ticket")

urlpatterns = router.urls
