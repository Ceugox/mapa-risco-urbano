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
                           setada, usa Postgres (psycopg) — mesmas queries; inclui
                           flood_history (histórico de alagamentos, dedupe 30 min,
                           episódios agrupados por gap > 2 h, retenção 90 dias)
  app/collectors/          cge.py, cemaden.py, inmet.py, meteo.py, geocoding.py, base.py
                           (base.py grava flood_history a cada coleta ok de alagamento)
  app/routers/layers.py    GET /api/layers, GET /api/layers/{layer}  (GeoJSON);
                           alagamento_hist é calculada de flood_recurrence(30), sem snapshot
  app/routers/reports.py   POST /api/reports, GET /api/reports, POST /api/reports/{id}/confirm
  app/routers/ingest.py    POST /api/ingest/message (texto livre -> relato)
  app/routers/whatsapp.py  webhook Cloud API (GET verifica, POST recebe)
  app/routers/risk.py      GET /api/risk/here (resumo de risco perto de um ponto)
  app/places.py            sugestão de endereço (Photon, reserva Nominatim); cache e dedup
  app/risk.py              summarize(lat, lon, radius_m=800): resumo por camada via H3 r8
  app/routers/admin.py     login de admin, GET /api/admin/stats, POST /api/events
  app/routers/trips.py     trajeto acompanhado ao vivo: POST /api/trips, POST /api/trips/{id}/position,
                           POST /api/trips/{id}/finish, GET /api/trips/shared/{share_token}
  app/routers/route.py     POST /api/route (mode driving/walking, depart_at)
  app/routing.py           fetch_routes (OSRM) e score_route (pesos por camada,
                           ajustados por modo/horário em time_weights)
  app/text.py              normaliza() de logradouros (sem dependências; usado por db, geocoding, ingest)
  app/canonical.py         301/308 de www e do domínio *.railway.app para CANONICAL_HOST (inerte sem a var)
  app/caching.py           middleware ASGI de Cache-Control por caminho (HTML/sw/manifest revalidam,
                           /assets/ com hash immutable, imagem e fonte um dia; /api e /health intactos)
  app/netutil.py           client_ip(): primeiro salto do X-Forwarded-For atrás do proxy do Railway
  app/analytics.py         middleware ASGI de acesso (buffer em memória -> access_log),
                           agregação por período, retenção; sem IP persistido
  app/ingest.py            classificador + extração de local + dedup/corroboração
  scripts/build_crime_layer.py   job offline: SSP-SP XLSX -> data/crime_h3.json
  data/crime_h3.json       camada criminal agregada (H3 r8, versionada, ~730 KB)
  tests/test_parsers.py
  tests/test_flood_history.py   dedupe, contagem de episódios, GeoJSON, retenção
frontend/
  src/main.tsx             escolhe App (site), AdminApp (/admin) ou TripPage (/t/<token>)
  src/App.tsx              nav, hero, mapa, ticker, "Como funciona", "Fontes e método", footer
  src/admin/AdminApp.tsx   painel do admin: login por senha, KPIs, gráfico SVG, rankings, erros
  src/trip/TripPage.tsx    página pública do trajeto acompanhado (share_token), sem nav do site
  src/components/Map.tsx   Google Maps + TrafficLayer, marcadores, polígonos, InfoWindow, modo Reportar
  src/components/LayerPanel.tsx   painel de camadas (switches, idade, contagem, status)
  src/components/RoutePanel.tsx   traça rota e compartilha trajeto ao vivo (link /t/<token>)
  src/components/ReportForm.tsx   modal de relato
  src/components/HerePanel.tsx    "Risco aqui e agora": posição atual + Casa/Trabalho salvos
  src/places.ts            searchPlaces(q): busca de endereço (Google Places -> Nominatim),
                           usada por RoutePanel e HerePanel
  src/api.ts, src/types.ts
  src/styles.css           tokens do design system e todo o CSS
  public/manifest.webmanifest   nome, ícones, display standalone (PWA)
  public/sw.js             service worker fonte (placeholder __BUILD__, ver vite.config.ts)
  public/icons/, public/apple-touch-icon.png   gerados por scripts/make_icons.py
  scripts/make_icons.py    gera os PNGs do PWA (stdlib-only: zlib + struct, sem Pillow)
  .env.example             VITE_GOOGLE_MAPS_API_KEY, VITE_API_URL
```

Camadas (`LayerName`): `alagamento` (CGE-SP), `alagamento_hist` (recorrência de
alagamentos nos últimos 30 dias, CGE-SP histórico, começa **desligada** na UI),
`cemaden`, `inmet`, `clima` (Open-Meteo), `crime` (SSP-SP agregado), `reports`
(comunidade). Trânsito vem do `google.maps.TrafficLayer`, não do backend.

## PWA (service worker e caches)

O plugin `closeBundle` em `vite.config.ts` copia `public/sw.js` para
`dist/sw.js` trocando `__BUILD__` pelo timestamp do build, então o service
worker muda de versão a cada deploy. Estratégias: navegação
(`network-first` com fallback ao `index.html` em cache), `/assets/*`
(`cache-first`, hash já versiona), `GET /api/layers` e `/api/layers/*`
(`stale-while-revalidate` no cache `mapasp-api`, respondendo do cache e
marcando `X-From-Cache: 1` quando a rede falha). `/api/admin`, `/api/events`,
`/api/auth`, `/api/contacts` e qualquer POST nunca são interceptados. O
`activate` limpa caches versionados antigos (`mapasp-shell-*`,
`mapasp-assets-*`). O SW só é registrado em produção (`main.tsx`).

## Preparar um checkout novo

```bash
node scripts/setup.mjs
```

Cria `backend/.venv` com os requirements e instala `frontend/node_modules` pelo
mirror do Yarn (o registro npm público está bloqueado nesta rede). É idempotente
e é o setup hook que o Orca roda ao criar um worktree com `--setup run`. Um
worktree que se instala sozinho é o que evita a junction para o checkout
principal, que em 14/09/2026 foi seguida por `git worktree remove --force` e
apagou o `node_modules` de verdade.

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

## Verificação

Obrigatória após qualquer alteração. Cada linha é um comando único, rodado da
raiz do repo, sem `cd` nem `&&`: o portão de evidência do harness só aceita
assim, e o CI roda exatamente estes passos.

```bash
ruff check backend
pytest backend/tests
npm --prefix frontend run build
npm --prefix frontend run lint
```

`ruff` e `pytest` precisam estar no PATH (`pip install --user ruff pytest`) ou
o venv de `backend/` ativado. `build` faz `tsc --noEmit` + `vite build`; `lint`
é `prettier --check`; para formatar, `npm --prefix frontend run format`.

Depois, abra `http://localhost:5173` e confira: mapa carrega com trânsito,
painel de camadas responde, banner "N fonte(s) indisponível(is)" aparece no
rodapé do mapa quando uma fonte falha, modo Reportar funciona (botão -> clique
no mapa -> modal -> toast), Esc cancela o modo.

## Busca de endereço

Roda no servidor, não no browser: o Places do Google responde `REQUEST_DENIED`
(as APIs legadas não são liberadas para projetos criados depois de março/2025) e
o Nominatim bloqueia por CORS quando chamado de `mapasp.com`. O motor é o
**Photon**, que responde a consulta parcial; o Nominatim é reserva, porque é
geocodificador e quer endereço quase completo.

No frontend, `useSuggestions` (em `src/places.ts`) espera 180 ms de pausa e
descarta resposta atrasada por número de sequência. Sem esse descarte, a
resposta de "rua a" chega depois da de "rua augusta" e sobrescreve a lista — era
o motivo de a sugestão nunca corresponder ao que se acabou de digitar.

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
- Sem moderação real de relatos.
- Domínio: `mapasp.com` e `www.mapasp.com` são custom domains do serviço no Railway; DNS na
  Cloudflare. O proxy precisa ficar **desligado (nuvem cinza) enquanto o certificado é emitido**,
  senão trava em VALIDATING_OWNERSHIP; depois de emitido ele pode ser religado, e hoje está
  **ligado** (em 15/09/2026 `mapasp.com` resolve para 104.21.81.245 / 172.67.192.34, faixas da
  Cloudflare, e a resposta traz `cf-cache-status`; o domínio `*.up.railway.app` responde
  `Server: railway-hikari`, sem nenhum header `cf-*`).
  `CANONICAL_HOST=mapasp.com` liga o redirect de www e do domínio Railway para o apex.
- **A Cloudflare pode reescrever o Cache-Control na borda — hoje não reescreve.** Em
  15/09/2026 a zona foi posta em Browser Cache TTL = **"Respect Existing Headers"**
  (Caching -> Configuration) e o header do app chega intacto ao browser; conferido nas oito
  rotas. Não vá atrás desse sintoma: ele está resolvido.
  O mecanismo fica registrado porque o Browser Cache TTL é um dropdown que alguém pode
  remexer. Enquanto esteve em 4 h, ele elevava o TTL das respostas que a Cloudflare cacheia
  quando o origin mandava menos: `/sw.js` saía do app como `no-cache, must-revalidate` e
  chegava ao browser como `max-age=14400, must-revalidate` — o `no-cache` virava 4 h e os
  outros tokens ficavam. `/assets/*` passava intacto porque `max-age=31536000` já era maior
  que o TTL da zona, e `/` e `/manifest.webmanifest` passavam porque a Cloudflare não os
  cacheia por extensão.
  **Como separar app de borda**, se um Cache-Control errado reaparecer em produção: suba o
  app local (`uvicorn`) e compare o header das mesmas rotas. Igual, o problema é
  `app/caching.py`; diferente, é a borda, e a correção é na Cloudflare, não no Python.
  Depois de mexer na config, lembre que as entradas já cacheadas continuam como estavam —
  o `/sw.js` velho só saiu com um purge seletivo da URL. Um `?cb=<timestamp>` na ponta da
  URL fura o edge e mostra o que o origin responde agora.
- Observabilidade: `/admin` (senha em `ADMIN_PASSWORD`; `ANALYTICS_SALT` tempera o hash
  diário de visitante). O middleware ignora `/health`, `/api/admin/*` e `/api/events`.
  Flush a cada 15 s pelo scheduler; retenção `ANALYTICS_RETENTION_DAYS` (90). A agregação
  lê as linhas do período em Python — reavaliar se passar de ~200 mil linhas/mês.
- Pendências de UX: revisar viewport mobile, navegação por teclado, contraste
  sistemático e painel de camadas com labels longos.
- `alagamento_hist`: cada coleta ok de `alagamento` grava uma linha por ponto
  em `flood_history` (chave = nome normalizado + lat/lon arredondados a 4
  casas), sem duplicar se já houver linha do mesmo ponto nos últimos 30 min.
  `episodes` agrupa ocorrências separadas por mais de 2 h. Retenção de 90 dias
  via job do scheduler (`flood_history_purge`, a cada 6 h). O histórico ainda
  não entra no score de rota (`routing.py`).

## Endpoints úteis

```
GET  /health
GET  /api/layers                 status de todas as camadas (idade, ok, contagem)
GET  /api/layers/{layer}         GeoJSON FeatureCollection
GET  /api/layers/alagamento_hist GeoJSON com {name, episodes, last_seen, days} por ponto
POST /api/reports                {lat, lng, category, description}
GET  /api/reports
POST /api/reports/{id}/confirm
POST /api/route                {origin, destination, mode, depart_at} -> rotas com score de
                                risco; mode "driving" (OSRM router.project-osrm.org) ou
                                "walking" (OSRM FOSSGIS routed-foot); depart_at ISO 8601
                                opcional (default: agora), usado com fuso America/Sao_Paulo
                                para ajustar os pesos por horário (ver regra 4)
POST /api/ingest/message       {text, channel} -> classifica, geocodifica, cria/corrobora
GET  /api/webhooks/whatsapp    verificação Meta (hub.mode/hub.verify_token/hub.challenge)
POST /api/webhooks/whatsapp    Cloud API: texto -> pipeline; location -> riscos próximos
GET  /api/risk/here?lat&lon    resumo de risco num raio de ~800 m (H3 r8), usado por
                               /api/webhooks/whatsapp e pelo painel "Risco aqui e agora"
POST /api/admin/login          {password} -> {token}; exige ADMIN_PASSWORD no ambiente (403 sem ela)
GET  /api/places/suggest?q=     autocompletar de endereço; 60/min por IP; sempre 200, lista vazia se as fontes caírem
GET  /api/admin/stats?range=   24h|7d|30d; Bearer token de admin; KPIs, série, rankings, erros
POST /api/events               {name, meta} -> 204; evento do frontend (page_view, route_calculated...)
POST /api/auth/register        {email, password} -> {token}; PBKDF2-SHA256
POST /api/auth/login           -> {token} (sessão opaca em tabela sessions)
GET/PUT /api/contacts          Bearer token; contatos de emergência da conta
POST /api/trips                 {destination:{lat,lon,label?}, duration_min?} -> {id,share_token,update_token,expires_at}
POST /api/trips/{id}/position   {lat, lon, update_token} -> 204; valida token/expiração/bbox
POST /api/trips/{id}/finish     {update_token} -> 204; marca finished_at
GET  /api/trips/shared/{token}  {destination, last_position, finished_at, expires_at, active}; nunca expõe update_token
```

Ingestão de texto (grupos/WhatsApp): PII é descartada na entrada (telefone e
@menção viram `[telefone]`/`[contato]`, remetente nunca é recebido nem salvo).
Relatos de `seguranca` entram `pendente` e só ficam `visivel` com 2+
corroborações. Mensagens iguais em 10 min são deduplicadas; relato novo a
≤400 m/3 h de um existente vira confirmação, não duplicata. Variáveis opcionais
em `backend/.env`: `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_TOKEN`,
`WHATSAPP_PHONE_ID` (sem elas o webhook ainda processa e devolve o resumo).
