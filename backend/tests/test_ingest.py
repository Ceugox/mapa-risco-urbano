from app import ingest


class TestClassify:
    def test_alagamento(self):
        assert ingest.classify("Alagou a Radial Leste, água subindo") == "alagamento"

    def test_seguranca(self):
        assert ingest.classify("Tiroteio agora na Av. Paulista, corram") == "seguranca"

    def test_transito(self):
        assert ingest.classify("Acidente interditou a Marginal Tietê") == "transito"

    def test_clima(self):
        assert ingest.classify("Temporal derrubou uma árvore caída na rua") == "clima"

    def test_irrelevante(self):
        assert ingest.classify("Bom dia grupo, alguém viu o jogo ontem?") is None

    def test_negacao(self):
        assert ingest.classify("Hoje não tem alagamento, transito livre") is None


class TestSanitize:
    def test_remove_telefone(self):
        assert "[telefone]" in ingest.sanitize("Liga pra mim 11987654321 urgente")

    def test_remove_mencao(self):
        assert "[contato]" in ingest.sanitize("fala com @marcos")

    def test_limite_280(self):
        assert len(ingest.sanitize("a" * 500)) == 280


class TestStreetMentions:
    def test_par_com(self):
        pairs, _ = ingest.street_mentions("alagou a av. paulista com a rua augusta")
        assert pairs == [("PAULISTA", "AUGUSTA")]

    def test_par_x(self):
        pairs, _ = ingest.street_mentions("enchente na Marginal Tietê x Ponte da Casa Verde")
        assert len(pairs) == 1
        assert "TIET" in pairs[0][0]

    def test_via_unica(self):
        pairs, singles = ingest.street_mentions("tiroteio na av. brigadeiro faria lima")
        assert pairs == []
        assert singles and "FARIA LIMA" in singles[0]

    def test_sem_via(self):
        assert ingest.street_mentions("tudo tranquilo por aqui") == ([], [])


def _patch_geo(monkeypatch):
    calls = []

    def fake_resolve(via, ref):
        calls.append((via, ref))
        if "PAULISTA" in via or "FARIA" in via:
            return {"metodo": "cruzamento", "lat": -23.561, "lon": -46.655, "precision": "alta"}
        return {"metodo": "falhou"}

    monkeypatch.setattr(ingest, "cached_resolve", fake_resolve)
    return calls


class TestExtractLocation:
    def test_par_resolve(self, monkeypatch):
        _patch_geo(monkeypatch)
        result = ingest.extract_location("alagou a av. paulista com rua augusta")
        assert result and result["precision"] == "alta"

    def test_fallback_bairro(self, monkeypatch):
        _patch_geo(monkeypatch)
        monkeypatch.setattr(
            ingest, "_resolve_bairro",
            lambda name: {"metodo": "distrito", "lat": -23.53, "lon": -46.62, "precision": "baixa"},
        )
        result = ingest.extract_location("alagou o Brás inteiro")
        assert result and result["metodo"] == "distrito"

    def test_nada_encontrado(self, monkeypatch):
        _patch_geo(monkeypatch)
        monkeypatch.setattr(ingest, "_resolve_bairro", lambda name: {"metodo": "falhou"})
        assert ingest.extract_location("alagamento total por aqui") is None


def _patch_db(monkeypatch, nearby=None):
    ingest._seen.clear()
    ingest._seen_set.clear()
    inserted = []
    monkeypatch.setattr(ingest, "find_nearby_report", lambda *a, **kw: nearby)
    monkeypatch.setattr(ingest, "insert_report", lambda r: inserted.append(r))
    monkeypatch.setattr(ingest, "corroborate_report", lambda rid: {"confirmations": 1, "status": "visivel"})
    return inserted


class TestIngestText:
    def test_cria_report(self, monkeypatch):
        _patch_geo(monkeypatch)
        inserted = _patch_db(monkeypatch)
        result = ingest.ingest_text("alagou a av. paulista com rua augusta", "whatsapp")
        assert result["ingested"] and result["action"] == "created"
        assert inserted[0]["source"] == "whatsapp"
        assert inserted[0]["status"] == "visivel"

    def test_seguranca_pendente(self, monkeypatch):
        _patch_geo(monkeypatch)
        inserted = _patch_db(monkeypatch)
        result = ingest.ingest_text("assalto agora na av. paulista", "whatsapp")
        assert result["ingested"]
        assert inserted[0]["category"] == "seguranca"
        assert inserted[0]["status"] == "pendente"

    def test_corrobora_existente(self, monkeypatch):
        _patch_geo(monkeypatch)
        _patch_db(monkeypatch, nearby={"id": "abc", "status": "pendente"})
        result = ingest.ingest_text("alagou a av. paulista com rua augusta", "whatsapp")
        assert result["action"] == "corroborated" and result["report_id"] == "abc"

    def test_rejeita_irrelevante(self, monkeypatch):
        _patch_db(monkeypatch)
        result = ingest.ingest_text("bom dia pessoal, tudo bem?", "whatsapp")
        assert result == {"ingested": False, "reason": "fora de escopo"}

    def test_rejeita_sem_local(self, monkeypatch):
        _patch_db(monkeypatch)
        monkeypatch.setattr(ingest, "cached_resolve", lambda v, r: {"metodo": "falhou"})
        monkeypatch.setattr(ingest, "_resolve_bairro", lambda n: {"metodo": "falhou"})
        result = ingest.ingest_text("alagou tudo aqui perto de casa", "whatsapp")
        assert result["reason"] == "sem localização identificada"

    def test_dedup(self, monkeypatch):
        _patch_geo(monkeypatch)
        _patch_db(monkeypatch)
        text = "alagou a av. paulista com rua augusta, dedup test"
        assert ingest.ingest_text(text, "whatsapp")["ingested"]
        assert ingest.ingest_text(text, "whatsapp")["reason"] == "duplicada"
