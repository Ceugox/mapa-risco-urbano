from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app import db
from app.routers import auth


@pytest.fixture
def tmpdb(monkeypatch, tmp_path):
    monkeypatch.setattr(db.settings, "database_path", str(tmp_path / "t.db"))
    monkeypatch.setattr(db.settings, "database_url", "")
    db.init_db()
    auth.rate.clear()


REQ = SimpleNamespace(client=SimpleNamespace(host="test-ip"))


def _register():
    return auth.register(
        auth.Credentials(email="Ana@Test.com ", password="segredo123"), REQ
    )


class TestRegister:
    def test_cria_conta_e_token(self, tmpdb):
        result = _register()
        assert result["token"] and result["email"] == "ana@test.com"

    def test_email_duplicado(self, tmpdb):
        _register()
        with pytest.raises(HTTPException) as exc:
            _register()
        assert exc.value.status_code == 409

    def test_email_invalido(self, tmpdb):
        with pytest.raises(HTTPException) as exc:
            auth.register(auth.Credentials(email="sem-arroba", password="segredo123"), REQ)
        assert exc.value.status_code == 422


class TestLogin:
    def test_login_ok(self, tmpdb):
        _register()
        result = auth.login(auth.Credentials(email="ana@test.com", password="segredo123"), REQ)
        assert result["token"]

    def test_senha_errada(self, tmpdb):
        _register()
        with pytest.raises(HTTPException) as exc:
            auth.login(auth.Credentials(email="ana@test.com", password="errada1"), REQ)
        assert exc.value.status_code == 401

    def test_usuario_inexistente(self, tmpdb):
        with pytest.raises(HTTPException) as exc:
            auth.login(auth.Credentials(email="nao@existe.com", password="segredo123"), REQ)
        assert exc.value.status_code == 401


class TestContacts:
    def test_roundtrip(self, tmpdb):
        token = _register()["token"]
        bearer = f"Bearer {token}"
        auth.put_contacts(
            auth.ContactsIn(contacts=[{"name": "Mãe", "phone": "5511987654321"}]), bearer
        )
        got = auth.get_contacts(bearer)
        assert got["contacts"] == [{"name": "Mãe", "phone": "5511987654321"}]
        assert got["email"] == "ana@test.com"

    def test_sem_token(self, tmpdb):
        with pytest.raises(HTTPException) as exc:
            auth.get_contacts(None)
        assert exc.value.status_code == 401

    def test_token_invalido(self, tmpdb):
        with pytest.raises(HTTPException) as exc:
            auth.get_contacts("Bearer inexistente")
        assert exc.value.status_code == 401

    def test_limpa_contato_vazio(self, tmpdb):
        token = _register()["token"]
        result = auth.put_contacts(
            auth.ContactsIn(contacts=[{"name": "", "phone": "1199"}, {"name": "Pai", "phone": "(11) 98877-6655"}]),
            f"Bearer {token}",
        )
        assert result["contacts"] == [{"name": "Pai", "phone": "11988776655"}]
