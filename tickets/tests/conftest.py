import pytest
from rest_framework.test import APIClient

from tickets import services
from tickets.models import Ticket
from users.models import User


@pytest.fixture
def customer(db):
    return User.objects.create_user(
        username="customer_a", password="testpass123", role=User.Role.CUSTOMER
    )


@pytest.fixture
def other_customer(db):
    return User.objects.create_user(
        username="customer_b", password="testpass123", role=User.Role.CUSTOMER
    )


@pytest.fixture
def agent(db):
    return User.objects.create_user(
        username="agent_1", password="testpass123", role=User.Role.AGENT
    )


@pytest.fixture
def other_agent(db):
    return User.objects.create_user(
        username="agent_2", password="testpass123", role=User.Role.AGENT
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


@pytest.fixture
def ticket_closed(ticket_assigned, agent):
    return services.change_status(
        ticket=ticket_assigned,
        actor=agent,
        new_status=Ticket.Status.CLOSED,
        note="Cerrado por falta de respuesta del cliente",
    )


def _client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def customer_client(customer):
    return _client_for(customer)


@pytest.fixture
def other_customer_client(other_customer):
    return _client_for(other_customer)


@pytest.fixture
def agent_client(agent):
    return _client_for(agent)


@pytest.fixture
def other_agent_client(other_agent):
    return _client_for(other_agent)


@pytest.fixture
def anonymous_client():
    return APIClient()
