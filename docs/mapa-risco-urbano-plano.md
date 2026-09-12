# Mapa de Risco Urbano — Plano de Produto e Técnico

Ferramenta pública que reúne **crime, alagamento, trânsito e clima severo** num único mapa, atualizado continuamente, com reports enviados pela própria comunidade.

Cidade-piloto assumida: **São Paulo** (maior disponibilidade de dados públicos). O desenho é replicável para outras capitais trocando os conectores de dados.

---

## 1. Proposta de valor

| Público | O que resolve |
|---|---|
| Morador / pedestre | "É seguro passar por aqui agora? Essa rua alaga?" |
| Motorista / motoboy / entregador | Rota evitando alagamento ativo e ponto de risco |
| Líder comunitário / ONG | Evidência para cobrar poder público (dados exportáveis por bairro) |
| Defesa Civil / subprefeitura | Sinal precoce vindo da população, antes do chamado oficial |

Diferencial em relação ao que já existe (CGE, Waze, portais de estatística): as quatro camadas **juntas, no mesmo mapa**, com histórico + o canal de report cidadão.

---

## 2. Fontes de dados (o ponto mais crítico do projeto)

Importante: "tempo real" varia muito por camada. Não prometa na landing page o que a fonte não entrega — mostre sempre o **carimbo de atualização por camada**.

### 2.1 Alagamento — quase tempo real
- **CGE-SP** (`cgesp.org`) publica pontos de alagamento ativos/inativos, alimentados por agentes de campo da prefeitura, com foco em vias principais. Não há API pública documentada; hoje a via prática é *scraping* da página de alagamentos em intervalo de ~5 min (existem projetos open source fazendo exatamente isso).
- **GeoSampa** expõe camadas WFS/WMS de ocorrências de alagamento (histórico desde 2013) — ótimo para a camada de "rua que alaga sempre", não para o agora.
- **CEMADEN**: pluviômetros e alertas hidrológicos/geológicos por município. Tem painel público de alertas; o acesso programático deve ser confirmado com o órgão (o plano de dados abertos deles ainda está em construção).

### 2.2 Clima severo — tempo real de verdade
- **INMET** — avisos meteorológicos e estações automáticas, com API pública.
- **OpenWeather / Open-Meteo** — chuva, radar e previsão horária; Open-Meteo é gratuito e sem chave, bom para MVP.
- **CEMADEN** — risco de deslizamento e alagamento por município.

### 2.3 Trânsito — depende de parceria
- **Waze for Cities**: parceria gratuita com prefeituras/órgãos; dá acesso a feed GeoRSS (JSON/XML) de incidentes, engarrafamentos e alertas. É a melhor fonte, mas exige convênio — **entre na fila cedo**, é o item de maior lead time do projeto.
- **CET-SP**: boletins e ocorrências de trânsito; disponibilidade programática precisa ser verificada, provavelmente scraping/LAI.
- **Alternativa de MVP**: Google Maps / TomTom Traffic como camada visual, sem armazenar (restrição de termos de uso — não dá para persistir nem revender).

### 2.4 Crime — **não é tempo real, e tudo bem**
- **SSP-SP Transparência**: microdados de boletins de ocorrência e estatísticas por município/delegacia, atualização mensal, defasagem observada de ~2 a 3 meses.
- Consequência de produto: crime vira **camada de risco estrutural** (mapa de calor por bairro/horário/tipo), não pin de "ocorreu agora". Combinar com reports da comunidade para o "agora".
- Cuidado ético: crime georreferenciado a nível de quadra estigmatiza território e pode derrubar valor imobiliário e reforçar preconceito. Agregue em hexágonos H3 (~500 m) e nunca exiba vítima ou endereço exato.

---

## 3. Reports da comunidade

O que faz a ferramenta viver ou morrer: sem moderação, vira rumor e pânico.

**Fluxo:** abrir mapa → botão flutuante "Reportar" → escolher categoria (alagamento, risco de segurança, trânsito parado, queda de árvore/energia, outro) → arrastar pin + foto opcional + texto curto → enviar.

**Regras desde o dia 1:**
- Sem cadastro para reportar (fricção mata adesão), mas com verificação por SMS/e-mail acima de N reports ou reCAPTCHA/Turnstile.
- **Confirmação cruzada**: cada report nasce "não confirmado"; vira "confirmado" com 3+ confirmações independentes em raio de 300 m / 60 min, ou ao casar com fonte oficial.
- **Expiração automática**: alagamento some em 3 h, trânsito em 1 h, risco de segurança em 12 h. Mapa sujo é mapa abandonado.
- **Rate limit por dispositivo + IP** e *shadow ban* de reincidentes.
- Fila de moderação com ações em lote e ranking por reputação do autor.
- Categoria "segurança" tem o maior risco de abuso (denúncia racista, perseguição, delação de pessoa específica). Sugestão: proibir texto livre nessa categoria no MVP — só tipo de ocorrência predefinido.

---

## 4. Arquitetura

```
Fontes externas          Ingestão                 Núcleo                    Cliente
────────────────        ──────────               ────────                  ─────────
CGE (scrape)      ┐
INMET / Open-Meteo├─▶ workers agendados ─▶ normalizador ─▶ Postgres+PostGIS ─▶ API ─▶ Next.js
Waze feed         │    (cron/queue)         (schema único)   + Redis (cache)          MapLibre
SSP (batch mensal)┘                                │                                  WebSocket
                                                   │
Reports do app ──▶ API ──▶ antifraude/moderação ───┘
```

**Stack sugerida** (escolhida por custo baixo e facilidade de contribuição open source):
- **Frontend**: Next.js + React + Tailwind + **MapLibre GL** (sem custo de tile proprietário; tiles via Protomaps/MapTiler).
- **Backend**: Node (NestJS) ou Python (FastAPI). Python leva vantagem se houver análise geoespacial pesada (GeoPandas, H3).
- **Banco**: PostgreSQL + **PostGIS**; agregação espacial em **H3**; TimescaleDB se a série temporal crescer.
- **Realtime**: WebSocket/SSE para novos eventos; tiles vetoriais gerados a cada N minutos para as camadas densas.
- **Infra**: Fly.io / Railway / Render no início; Cloudflare na frente (cache + Turnstile). Custo inicial realista: **US$ 30–80/mês**.

**Modelo de dados unificado** (um evento é um evento, venha de onde vier):

```
event(
  id, source            -- 'cge' | 'waze' | 'inmet' | 'ssp' | 'community'
  category              -- flood | crime | traffic | weather
  subtype, severity     -- 1..4
  geom(Point|LineString), h3_r8
  started_at, ended_at, expires_at
  status                -- active | resolved | unconfirmed | rejected
  confidence            -- 0..1
  payload jsonb         -- campos originais da fonte
)
```

---

## 5. Landing page

Objetivo duplo: **explicar em 5 segundos** e **entregar o mapa sem clique extra**.

1. **Hero com o mapa vivo ao fundo** (não um mockup) — título curto, contador "X eventos ativos agora em São Paulo", CTA "Ver meu bairro" que pede geolocalização.
2. **Barra de camadas** sempre visível: 4 toggles com cor fixa por tema (azul alagamento, vermelho crime, laranja trânsito, roxo clima) e o horário da última atualização de cada.
3. **Bloco "Como funciona"** em 3 passos, com ilustração leve.
4. **Prova de confiança**: logos/nomes das fontes oficiais + explicação honesta da defasagem de cada camada. Isso é o que separa a ferramenta de um boato coletivo.
5. **CTA de comunidade**: "Viu algo? Reporte em 20 segundos."
6. **Impacto**: números agregados (reports enviados, bairros cobertos, alagamentos confirmados no mês).
7. Rodapé: dados abertos, API pública, código no GitHub, contato.

**Não negociável**: mobile-first (o uso real acontece na rua, no celular, com 3G), modo escuro, acessibilidade AA — cor nunca sozinha como significado (use ícone + cor, por daltonismo), foco visível, leitura por leitor de tela das informações do pin.

---

## 6. Roadmap

| Fase | Escopo | Esforço |
|---|---|---|
| **0 — Descoberta** | Confirmar acesso a cada fonte, abrir pedido de parceria Waze for Cities, LAI para CET se preciso | 1 sessão + espera externa |
| **1 — MVP** | Mapa + clima (Open-Meteo/INMET) + alagamento (CGE) + reports com moderação manual | 1–2 sessões |
| **2 — Crime + landing** | Camada de risco estrutural em H3, landing completa, compartilhamento | 1–2 sessões |
| **3 — Trânsito + realtime** | Feed Waze, WebSocket, expiração/confirmação automática | 1–2 sessões |
| **4 — Escala** | Alertas por bairro (push/WhatsApp), API pública, painel para subprefeitura, segunda cidade | contínuo |

O caminho crítico não é código — é **liberação de dados** (parceria Waze, resposta a LAI). Comece por isso na semana 1.

---

## 7. Riscos e como mitigar

| Risco | Mitigação |
|---|---|
| Scraping do CGE quebra ou é bloqueado | Cache do último estado válido, alerta de falha, banner "camada indisponível", buscar convênio oficial |
| Mapa de crime estigmatiza bairro | Agregação H3 + normalização por população + nunca mostrar endereço; revisão com conselho comunitário |
| Reports falsos / uso para perseguição | Confirmação cruzada, expiração, sem texto livre em segurança, canal de denúncia |
| Responsabilidade legal por informação errada | Termos de uso claros: informação orientativa, não substitui 190/193/199; log de auditoria |
| LGPD | Não guardar localização contínua; geolocalização do report truncada; foto com EXIF removido; base legal = interesse legítimo + finalidade pública declarada |
| Projeto morre por falta de reports | Fase 1 funciona só com dados oficiais — o mapa já é útil com zero usuários |

---

## 8. Sustentabilidade

Ferramenta de impacto social precisa de custeio previsível: editais (FAPESP, Serrapilheira, Google.org, Mozilla), patrocínio de seguradora/mobilidade, licença de painel analítico para prefeituras (mantendo o mapa público e gratuito), doações. Código aberto (AGPL) protege o bem público e atrai contribuidores.

---

## 9. Primeiros passos concretos

1. Enviar pedido de parceria **Waze for Cities** (maior lead time).
2. Validar tecnicamente o scraping do CGE e a API do INMET — 1 script cada, provando frequência real de atualização.
3. Baixar a base da SSP-SP e montar o mapa de calor H3 offline, para ver se a granularidade serve.
4. Desenhar a landing (Figma ou direto em código) e montar o MVP da fase 1.
