import pytest
from fastapi.testclient import TestClient

from wartung.app import erzeuge_app

from hilfen import nutzer_mit_passwort, rolle_id


@pytest.fixture
def umgebung(tmp_path):
    """Frische Anwendung mit einem Administrator (admin@example.org)."""
    app = erzeuge_app(tmp_path)
    con = app.state.con
    nutzer_mit_passwort(con, "Test Admin", "admin@example.org", [rolle_id(con, "admin")])
    return TestClient(app), con
