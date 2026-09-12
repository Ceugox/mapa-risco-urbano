# Mapa de Risco Urbano — Validação das fontes de dados

Coleta real feita em 12/09/2026 (~14:40 UTC) com scripts Python (`probe_*.py`, saídas em `saida_*.json`). Todos os números abaixo vêm dessas execuções, não de documentação.

## Resumo

| Camada | Fonte | Acesso | Frescura medida | Georreferência | Veredito |
|---|---|---|---|---|---|
| Alagamento (agora) | CGE-SP | scraping HTML (sem JS) | página carimbada 08:58 do mesmo dia; 17 pontos ativos | **texto** (via + referência) | Viável — exige geocodificação própria |
| Alagamento (histórico) | GeoSampa WFS | API aberta (OGC) | última carga 02/09/2026, ocorrências até 04/2026 | ponto | Viável, defasagem ~5 meses |
| Clima severo | INMET avisos | API pública JSON | 4 avisos vigentes hoje, com polígono e municípios | polígono | Viável |
| Clima (observação/previsão) | Open-Meteo | API pública, sem chave | leitura a cada 15 min | ponto/grade | Viável |
| Clima (estações) | INMET estações | API devolve 204 (vazio) para leituras | — | — | **Não confiável sem token** |
| Deslizamento / hidrológico | CEMADEN `wsAlertas2` | JSON não documentado | atualizado 14:37 UTC (mesmo minuto da coleta); 145 alertas, 75 em SP | ponto por município | Viável, tratar como scraping |
| Crime | SSP-SP microdados | download XLSX direto (111 MB, 2026) | mês completo mais recente: **julho/2026** (~2 meses de atraso) | 76,9% com lat/lon | Viável, camada mensal |
| Trânsito | Google Maps (decisão com você) | Maps JS API | tempo real | camada visual | Visualização OK; sem dados persistíveis |

## Detalhes por fonte

### CGE-SP (alagamentos ativos)
- Página `alagamentos.jsp` é HTML renderizado no servidor, 24 KB, latência 0,08 s. Estrutura estável (`table.tb-pontos-de-alagamentos`, `li.ativo-intransitavel`, etc.).
- 17 pontos parseados = 17 do banner da home (consistência 100%). 10 intransitáveis, 7 transitáveis. 100% com via + referência.
- **Gargalo: não há coordenada.** Testes de geocodificação sobre os 17 pontos reais:
  - Nominatim/OSM: 15/17 "acertos", mas **0 no cruzamento** — devolve o centroide da via. Para a Marginal Tietê o erro foi de ~8 km (caiu em Vila Leopoldina em vez de Ponte da Casa Verde). Inutilizável.
  - Malha oficial GeoSampa (`segmento_logradouro`, 218.768 segmentos) + interseção geométrica: **10/17 com precisão alta/média** (7 cruzamentos exatos, 3 por aproximação a ≤30 m), 5 só no centroide, 2 falhas (viaduto e "Cebolão"). Ganho veio de tratar abreviações do CGE (`R`, `AV`, `PTE`, `CEL`, `JORN`…). Com dicionário de apelidos e camada de pontes/viadutos, a estimativa é passar de 85%.
- Recomendação: rodar scraping a cada 5 min, geocodificar com a malha oficial em PostGIS, cachear coordenadas por par (via, referência) — o CGE repete os mesmos pontos.

### GeoSampa (WFS)
- 477 camadas públicas. Relevantes: `risco_ocorrencia_alagamento` (197 pontos), `risco_ocorrencia_inundacao`, `mancha_inundacao_5/25/100`, `area_risco_geologico`, `risco_ocorrencia_queda_arvore`, `distrito_municipal` (96 polígonos), `subprefeitura`, `segmento_logradouro`.
- GeoJSON direto em EPSG:4326. Latência 1–2 s.
- Uso: camada "rua que alaga sempre", limites para agregação, e a malha viária para geocodificar o CGE.

### INMET
- `apiprevmet3.inmet.gov.br/avisos/ativos`: 4 avisos hoje + 4 futuros, campos `severidade`, `aviso_cor`, `poligono`, `municipios`, `geocodes`, `instrucoes`. Exemplo real: "Tempestade — Perigo Potencial", 12/09 00:00–23:59.
- `apitempo.inmet.gov.br/estacoes/T`: catálogo de 674 estações (40 em SP, A701 Mirante e A771 Interlagos).
- Leituras horárias (`/estacao/{ini}/{fim}/{cod}`) devolveram **204 sem conteúdo** para 5 dias diferentes e duas estações — endpoint aparentemente exige token hoje. Não depender dele.
- `condicao/capitais/{data}` responde, mas com valores `*` — inútil.

### Open-Meteo
- Sem chave, 0,7 s, leitura atual com intervalo de 15 min (temperatura, precipitação, rajada, código de tempo) e horária com probabilidade de chuva. Cobre o que o INMET-estações não entregou.

### CEMADEN
- Nenhuma API documentada; painel público carrega `https://painelalertas.cemaden.gov.br/wsAlertas2`.
- Resposta: `{alertas:[...], atualizado:"12-09-2026 14:37:02 UTC"}`, 145 alertas vigentes, 100% com lat/lon e código IBGE. SP: 75 (Santo André, Guarujá, Santos, Mauá, Cubatão…). Tipos: Movimentos de Massa (92), Risco Hidrológico Moderado (49) e Alto (4).
- Granularidade é **município**, não bairro. Serve como faixa de alerta, não como pino.

### SSP-SP (crime)
- Portal novo é Angular; os dados ficam em JSON estático + XLSX em `ssp.sp.gov.br/assets/estatistica/transparencia/spDados/SPDadosCriminais_{ano}.xlsx`, anos 2022–2026. `dados.gov.br` exigiu chave (401).
- Arquivo 2026: 111 MB, 645.725 boletins, 30 colunas incluindo `LATITUDE/LONGITUDE`, `DATA_OCORRENCIA_BO`, `NATUREZA_APURADA`, `BAIRRO`, `LOGRADOURO`.
- 496.728 (76,9%) com coordenada válida. Município de São Paulo: 260.108 boletins, 222.989 georreferenciados.
- 110.720 registros (17%) com logradouro suprimido por lei (crimes sexuais e afins) — não mapear.
- Meses completos: jan–jul/2026 (80–97 mil/mês). Agosto tem 2 registros → **defasagem efetiva ≈ 2 meses**. Há ~1% de ocorrências com datas antigas (2006–2025) por registro tardio — filtrar por `MES_ESTATISTICA`.
- Top naturezas: furto (306 mil), lesão corporal dolosa (100 mil), roubo (81 mil), furto de veículo (47 mil), lesão por acidente de trânsito (40 mil).
- Processamento do XLSX inteiro: 90 s em Python puro — cabe num job mensal.

### Trânsito
- Decisão tomada com você: **Google Maps JS API** com `TrafficLayer` para visualização em tempo real. Não persiste nem cruza com outros eventos; se isso virar requisito, buscar Waze for Cities.

## Implicações para o MVP

1. Mapa base pode ser Google Maps (unifica com trânsito) — precisa de chave com faturamento habilitado.
2. Backend próprio com PostGIS é obrigatório mesmo assim: geocodificação do CGE, agregação H3 do crime e reports da comunidade.
3. Jobs: CGE a cada 5 min; CEMADEN e INMET a cada 10 min; Open-Meteo a cada 15 min; SSP mensal; GeoSampa sob demanda.
4. Todas as fontes não documentadas (CGE, CEMADEN) entram com cache do último estado válido e banner de "camada indisponível".
