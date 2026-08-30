"""TC-080, TC-081 (docs/test-cases.md §9): la tabla TRANSITIONS es el único
lugar donde vive la máquina de estados; se verifica como dato, sin HTTP."""

from tickets.models import AGENT, OWNER, TRANSITIONS, Status


def test_every_transition_key_has_at_least_one_role():
    """TC-080: ninguna entrada de la tabla está vacía."""
    assert TRANSITIONS
    for key, roles in TRANSITIONS.items():
        assert roles, f"La transición {key} no tiene roles autorizados"
        assert roles.issubset({AGENT, OWNER})


def test_closed_never_appears_as_origin():
    """TC-081: CLOSED es un estado final, no tiene transiciones salientes."""
    origins = {from_status for (from_status, _to_status) in TRANSITIONS}
    assert Status.CLOSED not in origins
