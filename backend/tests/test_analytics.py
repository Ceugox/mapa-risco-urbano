from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app import analytics, db
from app.routers import admin

REQ = SimpleNamespace(client=SimpleNamespace(host="test-ip"))
IPHONE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15"
    " (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"
)
CHROME_WIN = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    " (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)


@pytest.fixture
def tmpdb(monkeypatch, tmp_path):
    monkeypatch.setattr(db.settings, "database_path", str(tmp_path / "t.db"))
    monkeypatch.setattr(db.settings, "database_url", "")
    monkeypatch.setattr(db.settings, "admin_password", "senha-forte")
    db.init_db()
    analytics.buffer.clear()
    admin.rate.clear()


def _iso(delta_hours: float = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=delta_hours)).isoformat()


def _hit(path="/api/layers", status=200, hours=0.0, method="GET", ua=CHROME_WIN, ip="1.2.3.4"):
    analytics.record(
        analytics.entry(
            method=method, path=path, status=status, duration_ms=12.5,
            ip=ip, user_agent=ua, referer="https://www.linkedin.com/feed/", ts=_iso(hours),
        )
    )


class TestClassify:
    def test_iphone_e_mobile_safari(self):
        assert analytics.classify_agent(IPHONE) == ("mobile", "safari")

    def test_windows_e_desktop_chrome(self):
        assert analytics.classify_agent(CHROME_WIN) == ("desktop", "chrome")

    def test_bot(self):
        device, browser = analytics.classify_agent("Mozilla/5.0 (compatible; Googlebot/2.1)")
        assert device == "bot" and browser == "bot"

    def test_vazio(self):
        assert analytics.classify_agent("") == ("unknown", "unknown")


class TestVisitor:
    def test_hash_estavel_no_dia_e_nao_expoe_ip(self):
        first = analytics.visitor_hash("1.2.3.4", CHROME_WIN, "2026-09-14")
        again = analytics.visitor_hash("1.2.3.4", CHROME_WIN, "2026-09-14")
        other_day = analytics.visitor_hash("1.2.3.4", CHROME_WIN, "2026-09-15")
        assert first == again and first != other_day
        assert "1.2.3.4" not in first and len(first) == 16

    def test_referer_vira_host(self):
        assert analytics.referer_host("https://www.linkedin.com/feed/?x=1") == "linkedin.com"
        assert analytics.referer_host("") == ""

    def test_path_normalizado_sem_query_nem_ids(self):
        assert analytics.normalize_path("/api/reports/abc123def/confirm") == "/api/reports/{id}/confirm"
        assert analytics.normalize_path("/api/support/nearby?lat=1&lon=2") == "/api/support/nearby"
        assert analytics.normalize_path("/assets/index-Bx1.js") == "/assets/*"


class TestBufferAndFlush:
    def test_flush_persiste_e_esvazia(self, tmpdb):
        _hit()
        _hit(path="/", ua=IPHONE, ip="5.6.7.8")
        assert len(analytics.buffer) == 2
        assert analytics.flush() == 2
        assert analytics.buffer == []
        with db.connection() as conn:
            rows = conn.execute("SELECT * FROM access_log ORDER BY path").fetchall()
        assert [row["path"] for row in rows] == ["/", "/api/layers"]
        assert rows[0]["device"] == "mobile" and rows[0]["referer"] == "linkedin.com"

    def test_ignora_health_e_admin(self):
        assert analytics.should_log("/health") is False
        assert analytics.should_log("/api/admin/stats") is False
        assert analytics.should_log("/api/layers") is True

    def test_retencao_apaga_antigos(self, tmpdb):
        _hit(hours=24 * 100)
        _hit()
        analytics.flush()
        assert analytics.purge(days=90) == 1


class TestStats:
    def test_agrega_kpis_e_series(self, tmpdb):
        _hit(path="/", ua=IPHONE, ip="a")
        _hit(path="/", ua=CHROME_WIN, ip="b")
        _hit(path="/", ua=CHROME_WIN, ip="b", hours=30)
        _hit(path="/api/route", method="POST", ip="a")
        _hit(path="/api/route", method="POST", ip="a", status=502)
        _hit(path="/api/reports", method="POST", ip="b")
        analytics.record(
            analytics.entry(
                method="EVENT", path="route_calculated", status=0, duration_ms=0,
                ip="a", user_agent=IPHONE, referer="", ts=_iso(),
            )
        )
        analytics.flush()
        stats = analytics.stats("24h")
        kpi = stats["kpi"]
        assert kpi["page_views"] == 2
        assert kpi["visitors"] == 2
        assert kpi["api_calls"] == 3
        assert kpi["errors"] == 1
        assert kpi["routes"] == 1 and kpi["reports"] == 1
        assert stats["devices"]["mobile"] == 1 and stats["devices"]["desktop"] == 1
        assert stats["referers"][0] == {"name": "linkedin.com", "count": 2}
        assert stats["events"] == [{"name": "route_calculated", "count": 1}]
        assert len(stats["series"]) == 24
        assert sum(point["requests"] for point in stats["series"]) == 5
        assert stats["top_paths"][0]["path"] in ("/", "/api/route")
        assert stats["recent_errors"][0]["status"] == 502

    def test_periodo_7d_agrupa_por_dia(self, tmpdb):
        _hit(path="/", hours=30)
        analytics.flush()
        stats = analytics.stats("7d")
        assert len(stats["series"]) == 7
        assert stats["kpi"]["page_views"] == 1

    def test_periodo_invalido(self, tmpdb):
        with pytest.raises(ValueError):
            analytics.stats("1y")


class TestAdminAuth:
    def test_login_ok_gera_token(self, tmpdb):
        result = admin.login(admin.AdminLogin(password="senha-forte"), REQ)
        assert result["token"]
        assert admin.require_admin(f"Bearer {result['token']}") is True

    def test_senha_errada(self, tmpdb):
        with pytest.raises(HTTPException) as exc:
            admin.login(admin.AdminLogin(password="errada"), REQ)
        assert exc.value.status_code == 401

    def test_admin_desabilitado_sem_senha(self, tmpdb, monkeypatch):
        monkeypatch.setattr(db.settings, "admin_password", "")
        with pytest.raises(HTTPException) as exc:
            admin.login(admin.AdminLogin(password="qualquer"), REQ)
        assert exc.value.status_code == 403

    def test_token_invalido(self, tmpdb):
        with pytest.raises(HTTPException) as exc:
            admin.require_admin("Bearer nada")
        assert exc.value.status_code == 401

    def test_token_de_usuario_comum_nao_e_admin(self, tmpdb):
        db.create_user("u1", "ana@test.com", "h", "s")
        db.create_session("tok-user", "u1")
        with pytest.raises(HTTPException):
            admin.require_admin("Bearer tok-user")

    def test_stats_exige_token(self, tmpdb):
        with pytest.raises(HTTPException):
            admin.stats("7d", None)
        token = admin.login(admin.AdminLogin(password="senha-forte"), REQ)["token"]
        result = admin.stats("7d", f"Bearer {token}")
        assert "kpi" in result and result["range"] == "7d"

    def test_evento_do_frontend(self, tmpdb):
        request = SimpleNamespace(client=SimpleNamespace(host="9.9.9.9"), headers={"user-agent": IPHONE})
        admin.track(admin.EventIn(name="page_view", meta={"w": 390}), request)
        assert analytics.buffer[0]["path"] == "page_view"
        assert analytics.buffer[0]["method"] == "EVENT"

    def test_evento_nome_invalido(self, tmpdb):
        request = SimpleNamespace(client=SimpleNamespace(host="9.9.9.9"), headers={})
        with pytest.raises(HTTPException):
            admin.track(admin.EventIn(name="DROP TABLE", meta={}), request)
