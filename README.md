# Mapa de Risco Urbano — São Paulo

MVP de um mapa cívico que combina alertas oficiais, previsão do tempo, crime
agregado e relatos anônimos da comunidade. O backend usa FastAPI + SQLite
(WAL); o frontend usa Vite, React, TypeScript e Google Maps.

## Executar

Requisitos: Python 3.10 e Node 20.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/build_crime_layer.py
uvicorn app.main:app --reload
```

Em outro terminal:

```bash
cd frontend
npm install
cp .env.example .env
# preencha VITE_GOOGLE_MAPS_API_KEY no .env localmente
npm run dev
```

Ou use `make dev` a partir da raiz depois de instalar as dependências. O
backend expõe `http://localhost:8000`; a interface expõe `http://localhost:5173`.
Nenhuma chave é incluída no repositório.

## Verificação

```bash
ruff check backend
pytest backend/tests
cd frontend && npm run build && npx tsc --noEmit
```

## Fontes

| Camada | Fonte | Acesso | Frescura medida | Georreferência | Veredito |
|---|---|---|---|---|---|
| Alagamento (agora) | CGE-SP | scraping HTML (sem JS) | página carimbada 08:58 do mesmo dia; 17 pontos ativos | **texto** (via + referência) | Viável — exige geocodificação própria |
| Alagamento (histórico) | GeoSampa WFS | API aberta (OGC) | última carga 02/09/2026, ocorrências até 04/2026 | ponto | Viável, defasagem ~5 meses |
| Clima severo | INMET avisos | API pública JSON | 4 avisos vigentes hoje, com polígono e municípios | polígono | Viável |
| Clima (observação/previsão) | Open-Meteo | API pública, sem chave | leitura a cada 15 min | ponto/grade | Viável |
| Clima (estações) | INMET estações | API devolve 204 (vazio) para leituras | — | — | **Não confiável sem token** |
| Deslizamento / hidrológico | CEMADEN `wsAlertas2` | JSON não documentado | atualizado 14:37 UTC (mesmo minuto da coleta); 145 alertas, 75 em SP | ponto por município | Viável, tratar como scraping |
| Crime | SSP-SP microdados | download XLSX direto (111 MB, 2026) | mês completo mais recente: **julho/2026** (~2 meses de atraso) | 76,9% com lat/lon | Viável, camada mensal |
| Trânsito | Google Maps (decisão com você) | Maps JS API | tempo real | camada visual | Visualização OK; não persiste |

Relatos expiram em seis ou 24 horas conforme categoria. A camada criminal é
sempre agregada em células H3 e remove células com menos de cinco registros;
nenhum boletim individual é exposto.
