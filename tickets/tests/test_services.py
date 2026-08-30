"""TC-082 a TC-085 (docs/test-cases.md §9): reglas de dominio contra
`services.py`, sin cliente HTTP."""

import pytest

from tickets import services
from tickets.exceptions import (
    InvalidStatusTransition,
    TicketNotAssigned,
    TransitionNotAllowedForRole,
)
from tickets.models import Ticket, TicketEvent


@pytest.mark.django_db
def test_unknown_transition_raises_invalid_status_transition(agent, ticket_new):
    """TC-082: NEW -> RESOLVED no está en TRANSITIONS."""
    with pytest.raises(InvalidStatusTransition):
        services.change_status(ticket=ticket_new, actor=agent, new_status=Ticket.Status.RESOLVED)


@pytest.mark.django_db
def test_existing_transition_forbidden_for_role_raises_distinct_error(customer, ticket_assigned):
    """TC-083: ASSIGNED -> IN_PROGRESS existe, pero solo para AGENT; el
    cliente (ni siquiera autor de una transición vedada) recibe un error
    distinto del de transición inexistente."""
    with pytest.raises(TransitionNotAllowedForRole):
        services.change_status(
            ticket=ticket_assigned, actor=customer, new_status=Ticket.Status.IN_PROGRESS
        )

    assert InvalidStatusTransition.status_code == 409
    assert TransitionNotAllowedForRole.status_code == 403
    assert not issubclass(TransitionNotAllowedForRole, InvalidStatusTransition)
    assert not issubclass(InvalidStatusTransition, TransitionNotAllowedForRole)


@pytest.mark.django_db
def test_domain_error_inside_change_status_rolls_back(agent, ticket_new):
    """TC-084: la transición NEW -> IN_PROGRESS existe y agent_1 sí puede
    ejecutarla, pero el ticket no tiene agente asignado (RN-04); el error
    debe dejar el ticket y su historial exactamente como estaban."""
    status_before = ticket_new.status
    event_ids_before = set(
        TicketEvent.objects.filter(ticket=ticket_new).values_list("id", flat=True)
    )

    with pytest.raises(TicketNotAssigned):
        services.change_status(ticket=ticket_new, actor=agent, new_status=Ticket.Status.IN_PROGRESS)

    ticket_new.refresh_from_db()
    assert ticket_new.status == status_before
    event_ids_after = set(
        TicketEvent.objects.filter(ticket=ticket_new).values_list("id", flat=True)
    )
    assert event_ids_after == event_ids_before


@pytest.mark.django_db
def test_create_ticket_generates_distinct_references(customer):
    """TC-085: dos llamadas a create_ticket producen referencias distintas."""
    ticket_1 = services.create_ticket(
        author=customer, subject="Uno", description="Primer caso.", priority=Ticket.Priority.LOW
    )
    ticket_2 = services.create_ticket(
        author=customer, subject="Dos", description="Segundo caso.", priority=Ticket.Priority.LOW
    )

    assert ticket_1.reference != ticket_2.reference
    assert ticket_1.reference.startswith("TCK-")
    assert ticket_2.reference.startswith("TCK-")
