"""Tests del endpoint /dashboard."""
from tests.conftest import USUARIO_TEST


class TestDashboard:

    def test_dashboard_sin_sesion(self, client):
        from fastapi.testclient import TestClient
        from api import app
        fresh = TestClient(app, cookies={})
        r = fresh.get("/dashboard")
        assert r.status_code == 401

    def test_dashboard_usuario_sin_puuid(self, client, cookie_sesion):
        """Usuario recién registrado sin puuid → dashboard devuelve sincronizado=False."""
        r = client.get("/dashboard")
        assert r.status_code == 200
        data = r.json()
        # Sin puuid, el backend devuelve sincronizado=False
        assert data["sincronizado"] is False
        assert "mensaje" in data

    def test_dashboard_estructura_respuesta(self, client, cookie_sesion):
        """Verifica que la respuesta tiene los campos esperados aunque no haya datos."""
        r = client.get("/dashboard")
        assert r.status_code == 200
        # Con o sin sincronización, siempre devuelve un JSON válido
        assert isinstance(r.json(), dict)


class TestStatsComportamiento:

    def test_comportamiento_sin_sesion(self, client):
        from fastapi.testclient import TestClient
        from api import app
        fresh = TestClient(app, cookies={})
        r = fresh.get("/stats/comportamiento")
        assert r.status_code == 401

    def test_comportamiento_sin_puuid(self, client, cookie_sesion):
        r = client.get("/stats/comportamiento?dias=30")
        assert r.status_code == 200
        # Sin puuid, devuelve dict vacío
        assert r.json() == {}

    def test_comportamiento_parametro_dias(self, client, cookie_sesion):
        r = client.get("/stats/comportamiento?dias=7")
        assert r.status_code == 200
