"""Tests del endpoint /historial — paginación y rango de fechas."""
from tests.conftest import USUARIO_TEST


class TestHistorial:

    def test_historial_sin_sesion(self, client):
        from fastapi.testclient import TestClient
        from api import app
        fresh = TestClient(app, cookies={})
        r = fresh.get("/historial")
        assert r.status_code == 401

    def test_historial_sin_puuid(self, client, cookie_sesion):
        r = client.get("/historial")
        assert r.status_code == 200
        data = r.json()
        assert data["partidas"] == []
        assert data["total"] == 0

    def test_historial_estructura_campos(self, client, cookie_sesion):
        r = client.get("/historial?dias=30")
        assert r.status_code == 200
        data = r.json()
        for campo in ("partidas", "total", "limit", "offset", "resumen",
                      "dias_excedidos", "por_campeon"):
            assert campo in data, f"Campo '{campo}' ausente en la respuesta"

    def test_historial_paginacion_parametros(self, client, cookie_sesion):
        r = client.get("/historial?dias=30&limit=10&offset=0")
        assert r.status_code == 200
        data = r.json()
        assert data["limit"]  == 10
        assert data["offset"] == 0

    def test_historial_rango_fechas_valido(self, client, cookie_sesion):
        r = client.get("/historial?fecha_inicio=2025-01-01&fecha_fin=2025-01-31")
        assert r.status_code == 200

    def test_historial_fecha_inicio_posterior_a_fin(self, client, cookie_sesion):
        r = client.get("/historial?fecha_inicio=2025-02-01&fecha_fin=2025-01-01")
        assert r.status_code == 400
        assert "posterior" in r.json()["detail"].lower()

    def test_historial_formato_fecha_invalido(self, client, cookie_sesion):
        r = client.get("/historial?fecha_inicio=01-01-2025&fecha_fin=31-01-2025")
        assert r.status_code == 400
        assert "formato" in r.json()["detail"].lower()

    def test_historial_dias_default(self, client, cookie_sesion):
        """Sin parámetros usa 30 días por defecto."""
        r = client.get("/historial")
        assert r.status_code == 200
        assert r.json()["periodo_dias"] == 30


class TestObjetivo:

    def test_get_objetivo(self, client, cookie_sesion):
        r = client.get("/objetivo")
        assert r.status_code == 200
        data = r.json()
        for campo in ("limite_horas_dia", "limite_horas_semana", "alerta_al_porcentaje"):
            assert campo in data

    def test_get_objetivo_valores_iniciales(self, client, cookie_sesion):
        r = client.get("/objetivo")
        assert r.status_code == 200
        data = r.json()
        assert float(data["limite_horas_dia"])    == USUARIO_TEST["limite_horas_dia"]
        assert float(data["limite_horas_semana"]) == USUARIO_TEST["limite_horas_semana"]
        assert data["alerta_al_porcentaje"]       == USUARIO_TEST["alerta_porcentaje"]

    def test_put_objetivo_actualiza_limite_dia(self, client, cookie_sesion):
        r = client.put("/objetivo", json={"limite_horas_dia": 3.0})
        assert r.status_code == 200

        r2 = client.get("/objetivo")
        assert float(r2.json()["limite_horas_dia"]) == 3.0

    def test_put_objetivo_sin_cambios(self, client, cookie_sesion):
        r = client.put("/objetivo", json={})
        assert r.status_code == 200
        assert "no hay cambios" in r.json()["message"].lower()

    def test_put_objetivo_sin_sesion(self, client):
        from fastapi.testclient import TestClient
        from api import app
        fresh = TestClient(app, cookies={})
        r = fresh.put("/objetivo", json={"limite_horas_dia": 1.0})
        assert r.status_code == 401


class TestHealth:

    def test_health_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"]   == "ok"
        assert data["database"] == "ok"
        assert "timestamp" in data
