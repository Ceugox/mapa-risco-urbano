# Mapa de Risco Urbano — guia para agentes

Leia este arquivo antes de alterar qualquer coisa. Ele descreve o estado atual
do projeto, como rodar, como verificar e as regras que não podem ser quebradas.

## O que é

Landing page pública com um mapa de São Paulo que reúne quatro categorias de
risco: crime, alagamento, trânsito e clima severo, mais relatos anônimos da
comunidade. Direção de design: **"instrumento, não brochura"** — o mapa real é
o hero; fundo quase preto; um único acento (lime `#c8f04c`); mono para dados;
cores fortes reservadas às camadas de risco.

Documentos de referência (fora do código, na raiz do pacote entregue):

- `docs/PROMPT_MAPA_RISCO_URBANO.md` — fontes de dados, endpoints, números
  medidos, limitações e regras de uso.
- `docs/DESIGN_SYSTEM_MAPA_RISCO_URBANO.md` — tokens, tipografia, componentes,
  padrões de mapa e motion.
- `docs/RELATORIO_VIABILIDADE.md` — relatório de validação das fontes.
- `docs/mapa-risco-urbano-plano.md` — plano de produto e roadmap.

## Estrutura

```
backend/
  app/main.py              FastAPI, CORS, scheduler dos coletores, /health
  app/config.py            Settings (pydantic-settings; lê backend/.env)
  app/db.py                SQLite local; se DATABASE_URL=postgres(ql)://... estiver
                           setada, usa Postgres (psycopg) — mesmas queries
  app/collectors/          cge.py, cemaden.py, inmet.py, meteo.py, geocoding.py, base.py
  app/routers/layers.py    GET /api/layers, GET /api/layers/{layer}  (GeoJSON)
  app/routers/reports.py   POST /api/reports, GET /api/reports, POST /api/reports/{id}/confirm
  app/routers/ingest.py    POST /api/ingest/message (texto livre -> relato)
  app/routers/whatsapp.py  webhook Cloud API (GET verifica, POST recebe)
  app/ingest.py            classificador + extração de local + dedup/corroboração
  scripts/build_crime_layer.py   job offline: SSP-SP XLSX -> data/crime_h3.json
  data/crime_h3.json       camada criminal agregada (H3 r8, versionada, ~730 KB)
  tests/test_parsers.py
frontend/
  src/App.tsx              nav, hero, mapa, ticker, "Como funciona", "Fontes e método", footer
  src/components/Map.tsx   Google Maps + TrafficLayer, marcadores, polígonos, InfoWindow, modo Reportar
  src/components/LayerPanel.tsx   painel de camadas (switches, idade, contagem, status)
  src/components/ReportForm.tsx   modal de relato
  src/api.ts, src/types.ts
  src/styles.css           tokens do design system e todo o CSS
  .env.example             VITE_GOOGLE_MAPS_API_KEY, VITE_API_URL
```

Camadas (`LayerName`): `alagamento` (CGE-SP), `cemaden`, `inmet`, `clima`
(Open-Meteo), `crime` (SSP-SP agregado), `reports` (comunidade). Trânsito vem
do `google.maps.TrafficLayer`, não do backend.

## Rodar

Requisitos: Python 3.10+, Node 20.

```bash
# backend (terminal 1)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/build_crime_layer.py   # opcional: crime_h3.json já está versionado
uvicorn app.main:app --reload         # http://localhost:8000

# frontend (terminal 2)
cd frontend
npm install
cp .env.example .env                  # preencha VITE_GOOGLE_MAPS_API_KEY
npm run dev                           # http://localhost:5173
```

`build_crime_layer.py` baixa ~111 MB da SSP-SP; só rode quando quiser
atualizar a camada criminal (publicação mensal).

## Verificar (obrigatório após qualquer alteração)

```bash
ruff check backend
pytest backend/tests
cd frontend && npx tsc --noEmit && npm run build
cd frontend && npx prettier --write src
```

Depois, abra `http://localhost:5173` e confira: mapa carrega com trânsito,
painel de camadas responde, banner "N fonte(s) indisponível(is)" aparece no
rodapé do mapa quando uma fonte falha, modo Reportar funciona (botão -> clique
no mapa -> modal -> toast), Esc cancela o modo.

## Regras que não podem ser quebradas

1. **Chave do Google Maps** só via `VITE_GOOGLE_MAPS_API_KEY` em
   `frontend/.env` (ignorado pelo git). Nunca em código, commit, log ou
   documento. Restringir a chave por HTTP referrer no Google Cloud Console.
2. **Crime é agregado**: células H3 resolução 8, mínimo 5 ocorrências por
   célula, sem boletim individual, sem endereço, registros com logradouro
   suprimido não são mapeados. Crime começa **desligado** na UI e a legenda
   deixa claro o período (jan–jul/2026) e o atraso (~2 meses).
3. **Não prometer tempo real** onde não há: cada camada mostra idade e status
   na UI (painel, ticker, tabela de fontes).
4. **Trânsito do Google é visual**: não persistir, republicar nem misturar
   com os eventos do backend sem licença adequada (ex.: Waze for Cities).
5. **Coletores falham isoladamente**: erro é registrado, último snapshot
   válido é preservado e a UI sinaliza indisponibilidade. Nunca derrubar a
   API por causa de uma fonte.
6. **Relatos**: anônimos, sem dados pessoais, com rate limiting, confirmação
   e expiração automática (6 h / 24 h por categoria). Modo Reportar precisa de
   ativação explícita antes de clicar no mapa.
7. **CEMADEN `wsAlertas2`** e o **HTML do CGE** são não documentados — tratar
   como scraping frágil, com parser defensivo e testes.
8. Design: manter tokens de `styles.css`; lime é acento de interação, não
   substitui cores semânticas de risco; respeitar `prefers-reduced-motion`;
   foco visível; textos em português institucional.
9. Código: mudanças pequenas e focadas; sem `Any`/`getattr` no Python; sem
   comentários que só explicam o diff; imports no topo; não editar
   `crime_h3.json` à mão (regenerar pelo script).

## Estado conhecido e pendências

- INMET (`apiprevmet3.inmet.gov.br/avisos/ativos`) responde de forma instável
  (204 / desconexão); a UI mostra "indisponível" e mantém o último snapshot.
- Geocodificação do CGE usa malha viária GeoSampa (`segmento_logradouro`) com
  cache; pontes/viadutos/apelidos ainda falham em alguns casos.
- Sem moderação real de relatos; sem deploy; sem observabilidade; sem remote git.
- Pendências de UX: revisar viewport mobile, navegação por teclado, contraste
  sistemático e painel de camadas com labels longos.

## Endpoints úteis

```
GET  /health
GET  /api/layers                 status de todas as camadas (idade, ok, contagem)
GET  /api/layers/{layer}         GeoJSON FeatureCollection
POST /api/reports                {lat, lng, category, description}
GET  /api/reports
POST /api/reports/{id}/confirm
POST /api/ingest/message       {text, channel} -> classifica, geocodifica, cria/corrobora
GET  /api/webhooks/whatsapp    verificação Meta (hub.mode/hub.verify_token/hub.challenge)
POST /api/webhooks/whatsapp    Cloud API: texto -> pipeline; location -> riscos próximos
```

Ingestão de texto (grupos/WhatsApp): PII é descartada na entrada (telefone e
@menção viram `[telefone]`/`[contato]`, remetente nunca é recebido nem salvo).
Relatos de `seguranca` entram `pendente` e só ficam `visivel` com 2+
corroborações. Mensagens iguais em 10 min são deduplicadas; relato novo a
≤400 m/3 h de um existente vira confirmação, não duplicata. Variáveis opcionais
em `backend/.env`: `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_TOKEN`,
`WHATSAPP_PHONE_ID` (sem elas o webhook ainda processa e devolve o resumo).
