"""Flujos completos end-to-end — docs/test-cases.md §10 (TC-100 a TC-102).

Cada test recorre la vida entera de una solicitud y verifica la secuencia
del historial resultante: número de eventos, orden y actor de cada uno. No
repite aserciones que ya cubren los tests de criterios (test_api.py)."""

import pytest
from django.urls import reverse


def _post(client, url_name, ticket_id, payload=None):
    return client.post(reverse(url_name, args=[ticket_id]), payload or {}, format="json")


@pytest.mark.django_db
def test_tc_100_camino_feliz_el_cliente_cierra(customer_client, agent_client, agent):
    create = customer_client.post(
        reverse("ticket-list"),
        {"subject": "No enciende", "description": "El equipo no enciende.", "priority": "HIGH"},
        format="json",
    )
    assert create.status_code == 201
    ticket_id = create.data["id"]

    assign = _post(agent_client, "ticket-assign", ticket_id, {"assigned_to": agent.id})
    assert assign.status_code == 200
    assert assign.data["status"] == "ASSIGNED"

    in_progress = _post(agent_client, "ticket-status", ticket_id, {"status": "IN_PROGRESS"})
    assert in_progress.status_code == 200

    comment = _post(
        agent_client, "ticket-comments", ticket_id, {"body": "Diagnóstico", "is_internal": True}
    )
    assert comment.status_code == 201

    resolved = _post(
        agent_client, "ticket-status", ticket_id, {"status": "RESOLVED", "note": "Pieza reemplazada"}
    )
    assert resolved.status_code == 200

    closed = _post(customer_client, "ticket-status", ticket_id, {"status": "CLOSED"})
    assert closed.status_code == 200
    assert closed.data["status"] == "CLOSED"
    assert closed.data["assigned_to"]["id"] == agent.id
    assert closed.data["resolved_at"] < closed.data["closed_at"]

    history = agent_client.get(reverse("ticket-history", args=[ticket_id])).data
    assert [e["event_type"] for e in history] == [
        "STATUS_CHANGED",  # CLOSED
        "STATUS_CHANGED",  # RESOLVED
        "COMMENT_ADDED",
        "STATUS_CHANGED",  # IN_PROGRESS
        "STATUS_CHANGED",  # ASSIGNED (automático, RN-07)
        "ASSIGNED",
        "CREATED",
    ]
    assert history[0]["actor"]["username"] == "customer_a"  # CLOSED
    for event in history[1:-1]:
        assert event["actor"]["username"] == "agent_1"
    assert history[-1]["actor"]["username"] == "customer_a"  # CREATED

    customer_comments = customer_client.get(reverse("ticket-comments", args=[ticket_id]))
    assert len(customer_comments.data) == 0


@pytest.mark.django_db
def test_tc_101_disconformidad_reapertura_y_segunda_resolucion(
    customer_client, agent_client, agent
):
    create = customer_client.post(
        reverse("ticket-list"),
        {"subject": "No enciende", "description": "El equipo no enciende.", "priority": "HIGH"},
        format="json",
    )
    ticket_id = create.data["id"]

    _post(agent_client, "ticket-assign", ticket_id, {"assigned_to": agent.id})
    _post(agent_client, "ticket-status", ticket_id, {"status": "IN_PROGRESS"})

    first_resolution = _post(
        agent_client, "ticket-status", ticket_id, {"status": "RESOLVED", "note": "Primer intento"}
    )
    assert first_resolution.status_code == 200
    first_resolved_at = first_resolution.data["resolved_at"]

    complaint = _post(
        customer_client,
        "ticket-comments",
        ticket_id,
        {"body": "Faltó parte del problema", "is_internal": True},
    )
    assert complaint.status_code == 201
    assert complaint.data["is_internal"] is False

    reopened = _post(agent_client, "ticket-status", ticket_id, {"status": "IN_PROGRESS"})
    assert reopened.status_code == 200
    assert reopened.data["status"] == "IN_PROGRESS"

    second_resolution = _post(
        agent_client, "ticket-status", ticket_id, {"status": "RESOLVED", "note": "Segundo intento"}
    )
    assert second_resolution.status_code == 200
    second_resolved_at = second_resolution.data["resolved_at"]
    assert second_resolved_at > first_resolved_at

    closed = _post(customer_client, "ticket-status", ticket_id, {"status": "CLOSED"})
    assert closed.status_code == 200
    assert closed.data["resolved_at"] == second_resolved_at
    assert closed.data["resolved_at"] != first_resolved_at

    history = agent_client.get(reverse("ticket-history", args=[ticket_id])).data
    assert [e["event_type"] for e in history] == [
        "STATUS_CHANGED",  # CLOSED
        "STATUS_CHANGED",  # RESOLVED (segunda vez)
        "STATUS_CHANGED",  # IN_PROGRESS (reapertura)
        "COMMENT_ADDED",
        "STATUS_CHANGED",  # RESOLVED (primera vez)
        "STATUS_CHANGED",  # IN_PROGRESS
        "STATUS_CHANGED",  # ASSIGNED
        "ASSIGNED",
        "CREATED",
    ]
    resolved_events = [e for e in history if e["new_value"] == "RESOLVED"]
    assert len(resolved_events) == 2

    customer_comment_view = customer_client.get(reverse("ticket-comments", args=[ticket_id]))
    assert len(customer_comment_view.data) == 1
    agent_comment_view = agent_client.get(reverse("ticket-comments", args=[ticket_id]))
    assert len(agent_comment_view.data) == 1


@pytest.mark.django_db
def test_tc_102_sin_respuesta_el_agente_cierra(customer_client, agent_client, agent):
    create = customer_client.post(
        reverse("ticket-list"),
        {"subject": "No enciende", "description": "El equipo no enciende.", "priority": "HIGH"},
        format="json",
    )
    ticket_id = create.data["id"]

    assign = _post(agent_client, "ticket-assign", ticket_id, {"assigned_to": agent.id})
    assert assign.status_code == 200

    pending = _post(agent_client, "ticket-status", ticket_id, {"status": "PENDING_CUSTOMER"})
    assert pending.status_code == 200
    assert pending.data["status"] == "PENDING_CUSTOMER"

    closed = _post(
        agent_client,
        "ticket-status",
        ticket_id,
        {"status": "CLOSED", "note": "Sin respuesta del cliente"},
    )
    assert closed.status_code == 200
    assert closed.data["status"] == "CLOSED"
    assert closed.data["resolved_at"] is None
    assert closed.data["closed_at"] is not None

    late_comment = _post(customer_client, "ticket-comments", ticket_id, {"body": "¿Hola?"})
    assert late_comment.status_code == 409

    history = agent_client.get(reverse("ticket-history", args=[ticket_id])).data
    assert [e["event_type"] for e in history] == [
        "STATUS_CHANGED",  # CLOSED
        "STATUS_CHANGED",  # PENDING_CUSTOMER
        "STATUS_CHANGED",  # ASSIGNED
        "ASSIGNED",
        "CREATED",
    ]
    close_event = history[0]
    assert close_event["new_value"] == "CLOSED"
    assert close_event["note"] == "Sin respuesta del cliente"

    ticket = customer_client.get(reverse("ticket-detail", args=[ticket_id])).data
    assert ticket["status"] == "CLOSED"
