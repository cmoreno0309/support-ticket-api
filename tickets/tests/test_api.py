"""Tests de API — uno por cada criterio de aceptación CA-01 a CA-16 de
docs/spec.md §6."""

import pytest
from django.urls import reverse

from tickets import services
from tickets.models import Ticket, TicketEvent


def _create_ticket(client, **overrides):
    payload = {
        "subject": "No enciende",
        "description": "El equipo no enciende desde ayer.",
        "priority": "HIGH",
    }
    payload.update(overrides)
    return client.post(reverse("ticket-list"), payload, format="json")


@pytest.mark.django_db
def test_ca_01_creacion(customer_client, customer):
    response = _create_ticket(customer_client)

    assert response.status_code == 201
    assert response.data["status"] == "NEW"
    assert response.data["assigned_to"] is None
    assert response.data["created_by"]["username"] == customer.username

    history = customer_client.get(reverse("ticket-history", args=[response.data["id"]]))
    assert history.status_code == 200
    assert len(history.data) == 1
    assert history.data[0]["event_type"] == "CREATED"


@pytest.mark.django_db
def test_ca_02_validacion_de_entrada(customer_client):
    sin_asunto = _create_ticket(customer_client, subject="")
    assert sin_asunto.status_code == 400

    prioridad_invalida = _create_ticket(customer_client, priority="URGENTE")
    assert prioridad_invalida.status_code == 400

    assert Ticket.objects.count() == 0


@pytest.mark.django_db
def test_ca_03_aislamiento_por_rol(customer_client, other_customer_client, ticket_new):
    ajeno = _create_ticket(other_customer_client)
    assert ajeno.status_code == 201

    listing = customer_client.get(reverse("ticket-list"))
    assert listing.status_code == 200
    assert listing.data["count"] == 1
    assert listing.data["results"][0]["id"] == str(ticket_new.id)

    detail = customer_client.get(reverse("ticket-detail", args=[ajeno.data["id"]]))
    assert detail.status_code == 404


@pytest.mark.django_db
def test_ca_04_visibilidad_del_agente(agent_client, agent, ticket_new, other_customer):
    # `ticket_new` y `ticket_assigned` no sirven juntos aquí: la segunda
    # fixture asigna el mismo ticket que crea la primera. Se necesita un
    # segundo ticket independiente para probar que el agente ve ambos.
    second_ticket = services.create_ticket(
        author=other_customer,
        subject="Otra falla",
        description="No conecta a la red.",
        priority=Ticket.Priority.LOW,
    )
    services.assign_ticket(ticket=second_ticket, actor=agent, assignee=agent)

    listing = agent_client.get(reverse("ticket-list"))
    assert listing.status_code == 200
    assert listing.data["count"] == 2

    filtered = agent_client.get(reverse("ticket-list"), {"status": "ASSIGNED"})
    assert filtered.status_code == 200
    assert filtered.data["count"] == 1
    assert filtered.data["results"][0]["id"] == str(second_ticket.id)


@pytest.mark.django_db
def test_ca_05_asignacion(agent_client, other_agent, ticket_new):
    response = agent_client.post(
        reverse("ticket-assign", args=[ticket_new.id]),
        {"assigned_to": other_agent.id},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["status"] == "ASSIGNED"
    assert response.data["assigned_to"]["id"] == other_agent.id

    event_types = list(
        TicketEvent.objects.filter(ticket=ticket_new)
        .order_by("created_at")
        .values_list("event_type", flat=True)
    )
    assert event_types == ["CREATED", "ASSIGNED", "STATUS_CHANGED"]


@pytest.mark.django_db
def test_ca_06_asignacion_invalida(agent_client, customer, ticket_new):
    response = agent_client.post(
        reverse("ticket-assign", args=[ticket_new.id]),
        {"assigned_to": customer.id},
        format="json",
    )

    assert response.status_code == 400
    assert response.data["error"]["code"] == "not_an_agent"

    ticket_new.refresh_from_db()
    assert ticket_new.status == Ticket.Status.NEW
    assert ticket_new.assigned_to is None


@pytest.mark.django_db
def test_ca_07_transicion_valida(agent_client, ticket_assigned):
    response = agent_client.post(
        reverse("ticket-status", args=[ticket_assigned.id]),
        {"status": "IN_PROGRESS"},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["status"] == "IN_PROGRESS"

    event = TicketEvent.objects.filter(ticket=ticket_assigned, event_type="STATUS_CHANGED").latest(
        "created_at"
    )
    assert event.old_value == "ASSIGNED"
    assert event.new_value == "IN_PROGRESS"


@pytest.mark.django_db
def test_ca_08_transicion_invalida(agent_client, ticket_new):
    response = agent_client.post(
        reverse("ticket-status", args=[ticket_new.id]), {"status": "RESOLVED"}, format="json"
    )

    assert response.status_code == 409
    assert response.data["error"]["code"] == "invalid_status_transition"

    ticket_new.refresh_from_db()
    assert ticket_new.status == Ticket.Status.NEW


@pytest.mark.django_db
def test_ca_09_estado_final(agent_client, ticket_closed):
    status_response = agent_client.post(
        reverse("ticket-status", args=[ticket_closed.id]),
        {"status": "IN_PROGRESS"},
        format="json",
    )
    assert status_response.status_code == 409

    assign_response = agent_client.post(
        reverse("ticket-assign", args=[ticket_closed.id]),
        {"assigned_to": ticket_closed.assigned_to_id},
        format="json",
    )
    assert assign_response.status_code == 409

    comment_response = agent_client.post(
        reverse("ticket-comments", args=[ticket_closed.id]),
        {"body": "no debería poder"},
        format="json",
    )
    assert comment_response.status_code == 409


@pytest.mark.django_db
def test_ca_10_comentario_interno(agent_client, customer_client, ticket_assigned):
    response = agent_client.post(
        reverse("ticket-comments", args=[ticket_assigned.id]),
        {"body": "Diagnóstico interno", "is_internal": True},
        format="json",
    )
    assert response.status_code == 201

    agent_view = agent_client.get(reverse("ticket-comments", args=[ticket_assigned.id]))
    assert len(agent_view.data) == 1

    customer_view = customer_client.get(reverse("ticket-comments", args=[ticket_assigned.id]))
    assert len(customer_view.data) == 0


@pytest.mark.django_db
def test_ca_11_permisos_de_cliente(customer_client, ticket_assigned):
    response = customer_client.post(
        reverse("ticket-status", args=[ticket_assigned.id]),
        {"status": "IN_PROGRESS"},
        format="json",
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_ca_12_historial(agent_client, ticket_assigned):
    agent_client.post(
        reverse("ticket-status", args=[ticket_assigned.id]),
        {"status": "IN_PROGRESS"},
        format="json",
    )
    agent_client.post(
        reverse("ticket-comments", args=[ticket_assigned.id]), {"body": "avance"}, format="json"
    )

    response = agent_client.get(reverse("ticket-history", args=[ticket_assigned.id]))
    assert response.status_code == 200

    event_types = [event["event_type"] for event in response.data]
    assert event_types == [
        "COMMENT_ADDED",
        "STATUS_CHANGED",
        "STATUS_CHANGED",
        "ASSIGNED",
        "CREATED",
    ]
    created_ats = [event["created_at"] for event in response.data]
    assert created_ats == sorted(created_ats, reverse=True)
    assert all("actor" in event for event in response.data)

    write_attempt = agent_client.post(reverse("ticket-history", args=[ticket_assigned.id]))
    assert write_attempt.status_code == 405
    delete_attempt = agent_client.delete(reverse("ticket-history", args=[ticket_assigned.id]))
    assert delete_attempt.status_code == 405


@pytest.mark.django_db
def test_ca_13_disconformidad_y_reapertura(agent_client, customer_client, ticket_assigned):
    agent_client.post(
        reverse("ticket-status", args=[ticket_assigned.id]),
        {"status": "IN_PROGRESS"},
        format="json",
    )
    resolved = agent_client.post(
        reverse("ticket-status", args=[ticket_assigned.id]),
        {"status": "RESOLVED", "note": "Reemplazo de pieza"},
        format="json",
    )
    assert resolved.status_code == 200

    comment = customer_client.post(
        reverse("ticket-comments", args=[ticket_assigned.id]),
        {"body": "Sigue fallando", "is_internal": True},
        format="json",
    )
    assert comment.status_code == 201
    assert comment.data["is_internal"] is False

    reopened = agent_client.post(
        reverse("ticket-status", args=[ticket_assigned.id]),
        {"status": "IN_PROGRESS"},
        format="json",
    )
    assert reopened.status_code == 200
    assert reopened.data["status"] == "IN_PROGRESS"

    history = agent_client.get(reverse("ticket-history", args=[ticket_assigned.id]))
    event_types = [event["event_type"] for event in history.data]
    assert event_types.count("STATUS_CHANGED") == 4
    assert "COMMENT_ADDED" in event_types


@pytest.mark.django_db
def test_ca_14_cierre_por_el_cliente(agent_client, customer_client, ticket_assigned, customer):
    agent_client.post(
        reverse("ticket-status", args=[ticket_assigned.id]),
        {"status": "IN_PROGRESS"},
        format="json",
    )
    agent_client.post(
        reverse("ticket-status", args=[ticket_assigned.id]),
        {"status": "RESOLVED", "note": "listo"},
        format="json",
    )

    response = customer_client.post(
        reverse("ticket-status", args=[ticket_assigned.id]), {"status": "CLOSED"}, format="json"
    )
    assert response.status_code == 200
    assert response.data["status"] == "CLOSED"
    assert response.data["closed_at"] is not None

    event = TicketEvent.objects.get(
        ticket=ticket_assigned, event_type="STATUS_CHANGED", new_value="CLOSED"
    )
    assert event.actor_id == customer.id


@pytest.mark.django_db
def test_ca_15_cierre_prematuro_por_el_cliente(
    agent_client, customer_client, other_customer_client, ticket_assigned
):
    agent_client.post(
        reverse("ticket-status", args=[ticket_assigned.id]),
        {"status": "IN_PROGRESS"},
        format="json",
    )

    premature = customer_client.post(
        reverse("ticket-status", args=[ticket_assigned.id]), {"status": "CLOSED"}, format="json"
    )
    assert premature.status_code == 403
    ticket_assigned.refresh_from_db()
    assert ticket_assigned.status == Ticket.Status.IN_PROGRESS

    agent_client.post(
        reverse("ticket-status", args=[ticket_assigned.id]),
        {"status": "RESOLVED", "note": "listo"},
        format="json",
    )
    ajena = other_customer_client.post(
        reverse("ticket-status", args=[ticket_assigned.id]), {"status": "CLOSED"}, format="json"
    )
    assert ajena.status_code == 404


@pytest.mark.django_db
def test_ca_16_cierre_por_el_agente(agent_client, ticket_assigned):
    agent_client.post(
        reverse("ticket-status", args=[ticket_assigned.id]),
        {"status": "PENDING_CUSTOMER"},
        format="json",
    )

    sin_motivo = agent_client.post(
        reverse("ticket-status", args=[ticket_assigned.id]), {"status": "CLOSED"}, format="json"
    )
    assert sin_motivo.status_code == 400
    assert sin_motivo.data["error"]["code"] == "close_reason_required"

    con_motivo = agent_client.post(
        reverse("ticket-status", args=[ticket_assigned.id]),
        {"status": "CLOSED", "note": "Sin respuesta del cliente"},
        format="json",
    )
    assert con_motivo.status_code == 200
    assert con_motivo.data["status"] == "CLOSED"

    event = TicketEvent.objects.get(
        ticket=ticket_assigned, event_type="STATUS_CHANGED", new_value="CLOSED"
    )
    assert event.note == "Sin respuesta del cliente"
