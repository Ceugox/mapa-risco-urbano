# Design System — Mapa de Risco Urbano

Referências analisadas: Palantir, Anduril, Anthropic, Snowflake, Linear, Vercel, PlanetScale, Railway, Tailscale, Modal, Zed, Warp, Stripe, Raycast (+ galerias siteinspire, godly, land-book, Refero, Mobbin, Awwwards).

## 0. O que essas referências têm em comum (e o que pegamos)

| Padrão observado | Onde | Como aplicamos |
|---|---|---|
| Fundo quase-preto neutro, não azul-marinho | Linear, Vercel, Raycast, Zed, Warp | `#0a0a0b` base, superfícies em cinza-neutro; o mapa é a única área clara |
| Uma cor de acento, usada com parcimônia | Linear (roxo), Railway (roxo), Modal (verde), Anduril (branco puro) | Acento `lime #c8f04c` só em CTA primário, indicador "ao vivo" e foco |
| Tipografia grande, tracking negativo, peso médio (não bold) | Anthropic, Palantir, Anduril, Stripe | Display `Inter Tight`/`Geist`, -0.03em, 500 |
| Monoespaçada para dados e labels técnicos | Palantir, Anduril, Warp, Modal, Vercel | `JetBrains Mono` em eyebrows, timestamps, contagens, coordenadas |
| Grid visível: hairlines 1px, bordas em vez de sombras | Linear, Vercel, PlanetScale, Stripe | `border: 1px solid rgba(255,255,255,.08)`; zero box-shadow em superfícies escuras |
| Produto real como hero (não ilustração) | Linear, Raycast, Warp, Zed, Railway | O mapa ao vivo já aparece no hero, com dados reais e carimbo "atualizado há X min" |
| Densidade de painel de controle / "mission control" | Palantir, Anduril, Snowflake | Layout do mapa como cockpit: painel lateral com status por fonte, contadores, badges |
| Movimento sutil, funcional | Linear, Vercel, Stripe | Fade/slide 150–250 ms, easing `cubic-bezier(.2,.8,.2,1)`; sem parallax, sem hero animado |
| Seriedade institucional + confiança | Palantir, Anthropic, Tailscale | Tom de voz sóbrio, sem exclamação, fonte dos dados sempre visível |

Princípio-guia: **"instrumento, não brochura"**. O usuário abre para saber se está seguro agora. Cada pixel decorativo compete com essa resposta.

## 1. Tokens

### Cor
```css
:root {
  /* superfícies (neutro, sem tint azul) */
  --bg-0: #0a0a0b;        /* página */
  --bg-1: #111113;        /* seções alternadas */
  --bg-2: #18181b;        /* cards, painel */
  --bg-3: #1f1f23;        /* hover, inputs */
  --line-1: rgba(255,255,255,.08);   /* hairline padrão */
  --line-2: rgba(255,255,255,.14);   /* hairline enfatizada */

  /* texto */
  --fg-0: #fafafa;        /* títulos */
  --fg-1: #d4d4d8;        /* corpo */
  --fg-2: #8b8b93;        /* secundário */
  --fg-3: #5c5c66;        /* desabilitado, legendas */

  /* acento único */
  --accent: #c8f04c;
  --accent-fg: #0a0a0b;   /* texto sobre o acento */
  --accent-dim: rgba(200,240,76,.12);

  /* semântica de risco — as ÚNICAS outras cores na interface */
  --risk-flood: #3b82f6;      /* alagamento */
  --risk-geo: #f97316;        /* CEMADEN deslizamento/hidrológico */
  --risk-weather: #ef4444;    /* aviso INMET */
  --risk-crime: #dc2626;      /* rampa de crime, ver §4 */
  --risk-traffic: #22c55e;    /* trânsito (cor do Google, só na legenda) */
  --risk-community: #a855f7;  /* relatos */

  /* estado */
  --ok: #22c55e; --warn: #f59e0b; --err: #ef4444;
}
```
Regra: cor de risco aparece **só** em marcadores, legenda, swatch do painel e badge da camada. Nunca em fundos, botões ou títulos.

### Tipografia
```css
--font-display: "Inter Tight", "Geist", system-ui, sans-serif;
--font-body:    "Inter", "Geist", system-ui, sans-serif;
--font-mono:    "JetBrains Mono", "Geist Mono", ui-monospace, monospace;
```
| Token | Fonte | Tamanho / linha | Peso | Tracking | Uso |
|---|---|---|---|---|---|
| display-xl | display | clamp(48px, 7vw, 96px) / 0.95 | 500 | -0.035em | H1 hero |
| display-l | display | clamp(32px, 4vw, 56px) / 1.05 | 500 | -0.03em | H2 de seção |
| title | body | 20px / 1.3 | 500 | -0.01em | Títulos de card |
| body-l | body | 18px / 1.6 | 400 | 0 | Lead do hero |
| body | body | 15px / 1.6 | 400 | 0 | Corpo |
| caption | body | 13px / 1.5 | 400 | 0 | Legendas |
| mono-label | mono | 11px / 1 | 500 | +0.12em, uppercase | Eyebrows, badges, status |
| mono-data | mono | 13px / 1.4 | 400 | 0 | Timestamps, contadores, coordenadas |

Máximo de 65ch em textos corridos. Sem itálico decorativo (o `<em>São Paulo</em>` atual vira cor `--fg-2`, não itálico).

### Espaço, raio, borda
- Escala 4px: `4 8 12 16 24 32 48 64 96 128`.
- Seções: padding vertical `clamp(64px, 10vw, 128px)`.
- Container: `max-width 1200px`, gutter `24px` mobile / `48px` desktop.
- Raio: `6px` (controles), `10px` (cards), `14px` (modal), `999px` (pills). Nada além disso.
- Bordas substituem sombras. Única sombra permitida: modal e popover (`0 20px 60px rgba(0,0,0,.5)`).

### Motion
- Duração: `120ms` (hover), `200ms` (entrada de painel/popover), `320ms` (modal).
- Easing: `cubic-bezier(.2,.8,.2,1)`.
- `prefers-reduced-motion`: desliga tudo exceto opacidade.
- Proibido: parallax, contadores animados, gradientes girando, texto digitando.
- Permitido: pulso lento (2s) no ponto "AO VIVO"; fade-in de marcadores novos.

## 2. Layout da landing

Estrutura em 6 blocos, do mais útil ao mais institucional (padrão Linear/Vercel):

1. **Nav** fixa, 56px, blur `backdrop-filter: blur(12px)` sobre `--bg-0` a 80%. Esquerda: marca em mono. Centro: 3 links. Direita: pill "● AO VIVO · 5 fontes ativas" (mono-label) + CTA secundário "Reportar".
2. **Hero** = mapa. Duas colunas em desktop (5/7): à esquerda eyebrow + H1 + lead + 2 CTAs + linha de métricas mono ("17 alagamentos ativos · 75 alertas CEMADEN · atualizado 14:59"); à direita o mapa real com painel de camadas embutido, 70vh, borda hairline, raio 10. Em mobile empilha, mapa 60vh.
3. **Ticker de status por fonte** — faixa de 1 linha com hairlines: `CGE ● 2 min` `CEMADEN ● 1 min` `INMET ○ indisponível` … (padrão status page Vercel/Railway). Gera confiança e mostra a atualização contínua sem prometer "tempo real".
4. **Como funciona** — 3 colunas numeradas em mono (`01 02 03`), título 20px, texto 15px `--fg-2`, hairline superior em cada coluna, sem ícones ilustrativos.
5. **Fontes e método** — tabela densa (Camada · Fonte · Frequência · Cobertura · Última atualização) em mono-data. Nota de método sobre crime agregado (H3, mínimo 5). Isso é o que Palantir/Anduril fazem: mostrar rigor.
6. **Footer** — marca, LGPD em 2 linhas, links (código aberto, API, contato). Sem newsletter.

## 3. Componentes

### Botões
| Variante | Estilo | Uso |
|---|---|---|
| primary | fundo `--accent`, texto `--accent-fg`, 500, raio 6, h 40 | 1 por tela ("Ver o mapa") |
| secondary | transparente, borda `--line-2`, texto `--fg-0`; hover `--bg-3` | "Reportar ocorrência" |
| ghost | só texto `--fg-1`; hover `--fg-0` | nav, cancelar |
| danger-ghost | texto `--err` | remover relato próprio |
Foco: `outline: 2px solid var(--accent); outline-offset: 2px` sempre visível no teclado.

### Pill / Badge (mono-label)
`● AO VIVO` (ponto pulsando em `--ok`), `○ INDISPONÍVEL` (`--err`), `CGE-SP`, `H3 R8`. Altura 22, padding 0 8, borda hairline, raio 999.

### Card
`--bg-2`, borda hairline, raio 10, padding 24. Hover: borda `--line-2` (sem elevar). Nunca sombra.

### Painel de camadas (map cockpit)
- Overlay no canto superior esquerdo do mapa, 280px, `--bg-2` a 92% + blur, borda hairline, raio 10.
- Cada linha: switch (não checkbox) · swatch 10px na cor da camada · nome · à direita mono-data "há 2 min" e contagem "17".
- Camada indisponível: swatch vazio, texto `--fg-3`, tooltip com o erro em linguagem humana ("INMET não respondeu; mostrando dados de 14:20").
- Crime: quando ligada, expande legenda de 5 swatches + "jan–jul/2026 · células ≥5".
- Colapsável em mobile para uma barra de chips horizontais.

### Marcadores
- Círculo 16–22px, preenchido na cor da camada, borda branca 1.5px, `fillOpacity .9`. Severidade = tamanho, nunca cor diferente.
- Polígono INMET: contorno `--risk-weather` 1px, preenchimento 12%.
- Hexágonos H3: rampa `#fef3c7 → #fdba74 → #f97316 → #dc2626 → #7f1d1d` por quantis, `fillOpacity .35`, sem contorno; desliga automaticamente em zoom ≥ 15 (evita estigma de quadra).
- Relatos: círculo `--risk-community`; relatos com ≥3 confirmações ganham anel externo.
- Estilo do mapa Google: usar `mapId` com estilo "grayscale/silver" reduzido (POIs ocultos, labels em cinza) para que marcadores e trânsito sejam as únicas cores. Criar o Map Style no Cloud Console.

### Popover de ocorrência (InfoWindow custom)
`--bg-2`, raio 10, largura 280, sem seta padrão do Google. Cabeçalho: badge da fonte + mono-data horário. Título 15px 500. Corpo 13px `--fg-1`. Rodapé: "Confirmar (3)" ghost + "Fonte: CGE-SP ↗".

### Modo Reportar
- Botão secundário no mapa vira estado ativo (borda `--accent`, texto "Clique no local · Esc cancela").
- Cursor crosshair; hint flutuante mono no rodapé do mapa.
- Modal (raio 14, 420px): categoria como **segmented control** com swatch de cor; descrição ≤280 com contador mono; "Enviar relato" primary; nota LGPD 12px `--fg-3`.
- Sucesso: toast inferior-direito 200ms, "Relato publicado · expira em 6h".

### Estados vazios / erro
Nunca tela em branco. Fonte fora: linha no ticker + banner fino no topo do mapa "1 fonte indisponível — mostrando últimos dados válidos".

## 4. Acessibilidade
- Contraste mínimo 4.5:1 em texto (`--fg-2` sobre `--bg-0` = 5.1:1 ✓; `--fg-3` só para texto ≥ 18px ou não essencial).
- Todo marcador tem equivalente em lista (painel "Ocorrências" acessível por teclado) — mapa nunca é a única via.
- Foco visível, ordem lógica, `aria-live="polite"` no ticker e no toast.
- Cores de risco sempre acompanhadas de texto/ícone (não depender só de cor).
- Tamanho de alvo ≥ 40px em mobile.

## 5. Voz e conteúdo
- Português direto, sem exclamação, sem "incrível/poderoso".
- Sempre dizer a idade do dado ("há 4 min", "julho/2026"), nunca "tempo real" sem qualificar.
- Crime: "ocorrências registradas por região", nunca "área perigosa".
- Números em mono; datas `dd/mm HH:mm`.

## 6. Implementação (ordem)
1. Tokens em `styles.css` (`:root`) + fontes via `@fontsource/inter-tight`, `@fontsource/inter`, `@fontsource/jetbrains-mono` (self-host, sem Google Fonts por LGPD).
2. Nav fixa + hero em 2 colunas com mapa.
3. Ticker de status.
4. Painel de camadas com switches, swatches, contagens, legenda de crime.
5. Marcadores circulares por camada; estilo grayscale do mapa.
6. Modo reportar + modal segmentado + toast.
7. Tabela de fontes e footer.
8. Auditoria: Lighthouse a11y ≥ 95, teclado completo, reduced-motion.
