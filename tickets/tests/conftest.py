import pytest

from tickets import services
from tickets.models import Ticket
from users.models import User


@pytest.fixture
def customer(db):
    return User.objects.create_user(
        username="customer_a", password="testpass123", role=User.Role.CUSTOMER
    )


@pytest.fixture
def agent(db):
    return User.objects.create_user(
        username="agent_1", password="testpass123", role=User.Role.AGENT
    )


@pytest.fixture
def ticket_new(customer):
    return services.create_ticket(
        author=customer,
        subject="No enciende",
        description="El equipo no enciende desde ayer.",
        priority=Ticket.Priority.HIGH,
    )


@pytest.fixture
def ticket_assigned(ticket_new, agent):
    return services.assign_ticket(ticket=ticket_new, actor=agent, assignee=agent)
