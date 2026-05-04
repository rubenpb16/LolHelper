"""Tests de los endpoints de autenticación."""
import pytest
from tests.conftest import USUARIO_TEST


class TestRegistro:

    def test_registro_exitoso(self, client, usuario_registrado):
        # El fixture ya registra al usuario; verificamos que /auth/me responde
        r = client.post("/auth/login", data={
            "username": USUARIO_TEST["email"],
            "password": USUARIO_TEST["password"],
        })
        assert r.status_code == 200
        assert r.json()["game_name"] == USUARIO_TEST["riot_game_name"]

    def test_registro_email_duplicado(self, client, usuario_registrado):
        r = client.post("/auth/register", json=USUARIO_TEST)
        assert r.status_code == 409
        assert "email" in r.json()["detail"].lower()

    def test_registro_riot_id_duplicado(self, client, usuario_registrado):
        duplicado = {**USUARIO_TEST, "email": "otro@lolhelper.dev"}
        r = client.post("/auth/register", json=duplicado)
        assert r.status_code == 409
        assert "riot" in r.json()["detail"].lower()

    def test_registro_sin_consentimiento(self, client):
        sin_consent = {**USUARIO_TEST,
                       "email": "noconsent@lolhelper.dev",
                       "consentimiento_datos": False}
        r = client.post("/auth/register", json=sin_consent)
        assert r.status_code == 422   # pydantic validator

    def test_registro_password_corta(self, client):
        corta = {**USUARIO_TEST,
                 "email": "short@lolhelper.dev",
                 "password": "abc"}
        r = client.post("/auth/register", json=corta)
        assert r.status_code == 422


class TestLogin:

    def test_login_exitoso(self, client, usuario_registrado):
        r = client.post("/auth/login", data={
            "username": USUARIO_TEST["email"],
            "password": USUARIO_TEST["password"],
        })
        assert r.status_code == 200
        data = r.json()
        assert "game_name" in data
        assert "token" in r.cookies  # cookie httpOnly seteada

    def test_login_password_incorrecta(self, client, usuario_registrado):
        r = client.post("/auth/login", data={
            "username": USUARIO_TEST["email"],
            "password": "contraseña_incorrecta",
        })
        assert r.status_code == 401

    def test_login_email_inexistente(self, client):
        r = client.post("/auth/login", data={
            "username": "noexiste@lolhelper.dev",
            "password": "cualquiera",
        })
        assert r.status_code == 401


class TestMe:

    def test_me_con_sesion(self, client, cookie_sesion):
        r = client.get("/auth/me")
        assert r.status_code == 200
        assert r.json()["email"] == USUARIO_TEST["email"]

    def test_me_sin_sesion(self, client):
        # Cliente fresco sin cookies
        from fastapi.testclient import TestClient
        from api import app
        fresh = TestClient(app, cookies={})
        r = fresh.get("/auth/me")
        assert r.status_code == 401


class TestCambioPassword:

    def test_cambio_exitoso(self, client, cookie_sesion):
        r = client.put("/auth/password", json={
            "password_actual": USUARIO_TEST["password"],
            "password_nueva":  "nueva_contraseña_8",
        })
        assert r.status_code == 200
        # Restaurar para no romper otros tests
        client.put("/auth/password", json={
            "password_actual": "nueva_contraseña_8",
            "password_nueva":  USUARIO_TEST["password"],
        })

    def test_cambio_password_actual_incorrecta(self, client, cookie_sesion):
        r = client.put("/auth/password", json={
            "password_actual": "contraseña_incorrecta",
            "password_nueva":  "otra_nueva_1234",
        })
        assert r.status_code == 400

    def test_cambio_sin_sesion(self, client):
        from fastapi.testclient import TestClient
        from api import app
        fresh = TestClient(app, cookies={})
        r = fresh.put("/auth/password", json={
            "password_actual": USUARIO_TEST["password"],
            "password_nueva":  "nueva_contraseña_8",
        })
        assert r.status_code == 401


class TestLogout:

    def test_logout(self, client, cookie_sesion):
        r = client.post("/auth/logout")
        assert r.status_code == 200
        # Tras logout, /auth/me debe devolver 401
        r2 = client.get("/auth/me")
        assert r2.status_code == 401
