# PROMPT — Mapa de Risco Urbano (São Paulo)

Copie tudo abaixo para iniciar um novo agente/sessão com todo o contexto do projeto.

---

Você vai trabalhar no **Mapa de Risco Urbano**, uma ferramenta de impacto social para São Paulo: landing page bonita e acessível com um mapa que reúne **alagamento, clima severo, deslizamento/hidrológico, crime (agregado) e trânsito**, atualizado continuamente a partir de bases públicas, e que permite à comunidade enviar **reports** georreferenciados.

Todas as fontes abaixo foram **validadas com scripts reais em 12/09/2026**. Os números são medidos, não teóricos. Use exatamente estes endpoints e respeite as limitações listadas.

## 1. Fontes de dados

### 1.1 Alagamentos ativos — CGE-SP (Prefeitura de São Paulo)
- URL: `https://www.cgesp.org/v3/alagamentos.jsp` (banner de contagem em `https://www.cgesp.org/v3/`)
- Acesso: HTML renderizado no servidor, **sem JavaScript**, sem chave. ~24 KB, latência ~0,1 s.
- Estrutura HTML: `h1.tit-bairros` (zona) → `table.tb-pontos-de-alagamentos` → `td.bairro` → `div.ponto-de-alagamento` → `li[title]` com classe `ativo-intransitavel | ativo-transitavel | inativo-intransitavel | inativo-transitavel`; `li.arial-descr-alag.col-local` (horário "De HH:MM a HH:MM" + via); `li.arial-descr-alag` (Sentido: … / Referência: …).
- Medido: 17 pontos ativos (10 intransitáveis), 100% com via + referência, carimbo "12/09/2026 08:58".
- **Limitação crítica: não há coordenadas**, só texto ("MARGINAL TIETÊ × PONTE DA CASA VERDE"). Geocodificar com Nominatim/OSM erra até 8 km (devolve centroide da via). Use a malha viária oficial (GeoSampa `segmento_logradouro`), interseção geométrica via × referência; fallback: ponto mais próximo ≤30 m; último recurso: centroide. Resultado medido: 10/17 com precisão alta/média. Normalizar abreviações (`R`, `AV`, `PTE`, `VD`, `CEL`, `JORN`, `DEP`…). Cachear geocodificação por (via, referência).
- Frequência sugerida: a cada 5 min. É scraping: manter último estado válido e exibir "camada indisponível" em falha.

### 1.2 Histórico de alagamento, limites e malha viária — GeoSampa WFS
- URL: `http://wfs.geosampa.prefeitura.sp.gov.br/geoserver/geoportal/wfs`
- Acesso: OGC WFS 2.0, sem chave. Ex.: `?service=WFS&version=2.0.0&request=GetFeature&typeNames=geoportal:risco_ocorrencia_alagamento&outputFormat=application/json&srsName=EPSG:4326`
- Camadas úteis (477 no total): `risco_ocorrencia_alagamento` (197 pontos, campos `dt_ocorrencia`, `dc_tipo_ocorrencia`, `nm_subprefeitura`), `risco_ocorrencia_inundacao`, `risco_ocorrencia_deslizamento`, `mancha_inundacao_5|25|100`, `area_inundavel`, `risco_hidrologico`, `area_risco_geologico`, `distrito_municipal` (96 polígonos), `subprefeitura`, `segmento_logradouro` (218.768 LineStrings, campo `nm_logradouro`; filtrar com `CQL_FILTER=nm_logradouro LIKE '%NOME%'`).
- Latência 1–2 s. Última carga observada: 02/09/2026.

### 1.3 Avisos meteorológicos — INMET
- URL: `https://apiprevmet3.inmet.gov.br/avisos/ativos`
- Acesso: JSON público, sem chave. Retorna `hoje` e `futuro`; campos: `severidade`, `aviso_cor`, `descricao`, `inicio`, `fim`, `municipios`, `estados`, `geocodes`, `poligono`, `riscos`, `instrucoes`.
- Medido: 4 avisos hoje + 4 futuros (ex.: "Tempestade — Perigo Potencial"). Filtrar por SP.
- Catálogo de estações: `https://apitempo.inmet.gov.br/estacoes/T` (674 estações; SP capital: `A701` Mirante, `A771` Interlagos).
- **Não usar** leituras horárias `https://apitempo.inmet.gov.br/estacao/{ini}/{fim}/{cod}` — retornaram HTTP 204 (vazio) em todos os testes; aparentemente exige token.

### 1.4 Observação e previsão do tempo — Open-Meteo
- URL: `https://api.open-meteo.com/v1/forecast?latitude=-23.55&longitude=-46.63&current=temperature_2m,precipitation,rain,wind_gusts_10m,weather_code&hourly=precipitation,precipitation_probability&timezone=America/Sao_Paulo`
- Acesso: sem chave, latência ~0,7 s, atualização a cada 15 min. Substitui as estações do INMET.

### 1.5 Alertas de deslizamento e risco hidrológico — CEMADEN
- URL: `https://painelalertas.cemaden.gov.br/wsAlertas2` (endpoint interno do painel `https://painelalertas.cemaden.gov.br/`, descoberto em `resources/js/painelalertas.js`; **não documentado**).
- Resposta: `{ "alertas": [...], "atualizado": "12-09-2026 14:37:02 UTC" }`. Cada alerta: `uf`, `municipio`, `evento`, `nivel`, `latitude`, `longitude`, código IBGE, datas.
- Medido: 145 alertas vigentes, 75 em SP, 100% com coordenadas. Tipos: Movimentos de Massa (92), Risco Hidrológico Moderado (49), Alto (4).
- Granularidade: **município** (não bairro). Tratar como scraping (cache + fallback). Frequência: 10 min.

### 1.6 Crime — SSP-SP (microdados de boletins)
- Índice: `https://www.ssp.sp.gov.br/assets/estatistica/transparencia/spDados160_516.json`
- Arquivo: `https://www.ssp.sp.gov.br/assets/estatistica/transparencia/spDados/SPDadosCriminais_{ANO}.xlsx` (anos 2022–2026; 2026 tem 111 MB).
- Abas: `Campos da Tabela_SPDADOS`, `JAN-JUN_2026`, `JUL-DEZ_2026`. Colunas: `NOME_MUNICIPIO`, `NUM_BO`, `ANO_BO`, `DATA_REGISTRO`, `DATA_OCORRENCIA_BO`, `HORA_OCORRENCIA_BO`, `DESCR_TIPOLOCAL`, `BAIRRO`, `LOGRADOURO`, `LATITUDE`, `LONGITUDE`, `RUBRICA`, `NATUREZA_APURADA`, `MES_ESTATISTICA`, `COD IBGE`.
- Medido: 645.725 boletins; 496.728 (76,9%) com coordenada válida; município de São Paulo 260.108 (222.989 com coordenada). 110.720 registros com logradouro suprimido por lei — **não mapear**. Coordenadas inválidas aparecem como `-`, `0` ou vazio. Mês completo mais recente: **julho/2026 → defasagem ≈ 2 meses**. ~1% com datas antigas por registro tardio → filtrar por `MES_ESTATISTICA`.
- Top naturezas: FURTO - OUTROS, LESÃO CORPORAL DOLOSA, ROUBO - OUTROS, FURTO DE VEÍCULO, LESÃO CORPORAL CULPOSA POR ACIDENTE DE TRÂNSITO.
- **Regra do produto**: crime é camada mensal e **agregada** (hexágonos H3 res. 8, mínimo 5 ocorrências por célula); nunca exibir boletim individual nem endereço. Processamento do XLSX: ~90 s em Python; job mensal.
- `dados.gov.br` (CKAN) exige chave — não usar.

### 1.7 Trânsito — Google Maps Platform
- Uso decidido: **Maps JavaScript API + `TrafficLayer`** para mapa base e trânsito em tempo real (somente visualização). Não persiste eventos nem cruza com outras camadas; se isso virar requisito, buscar Waze for Cities (exige convênio).
- Habilitar no Google Cloud: Maps JavaScript API. Restringir a chave por HTTP referrer (domínio do site) e às APIs necessárias.

## 2. Chaves e segredos
- `GOOGLE_MAPS_API_KEY` — chave da Google Maps Platform. **Salva no cofre de segredos do Devin** (escopo do usuário); no código, ler apenas de variável de ambiente (`VITE_GOOGLE_MAPS_API_KEY` no frontend). Nunca commitar o valor.
- Todas as demais fontes (CGE, GeoSampa, INMET, Open-Meteo, CEMADEN, SSP-SP) **não exigem chave**.

## 3. Arquitetura definida
- Backend próprio (FastAPI) é dono dos eventos: coletores agendados (CGE 5 min, CEMADEN/INMET 10 min, Open-Meteo 15 min, SSP mensal, GeoSampa sob demanda), snapshot por camada com `fetched_at`, `source_updated_at`, `ok/erro`, último payload válido.
- Frontend Vite + React + TypeScript, Google Maps como base; camadas ligáveis com carimbo "atualizado há X min"; reports da comunidade (categorias alagamento/trânsito/clima/segurança/outro, expiração 6 h/24 h, confirmação por outros usuários, rate limit por IP, moderação para segurança).
- LGPD: reports sem dados pessoais, EXIF removido, geolocalização só para o report; crime só agregado.
- API: `GET /api/layers`, `GET /api/layers/{alagamento|cemaden|inmet|clima|crime|reports}` (GeoJSON), `POST /api/reports`, `POST /api/reports/{id}/confirm`.

## 4. Material existente
- Plano de produto: `mapa-risco-urbano-plano.md`
- Relatório de validação: `risco-urbano-probes/RELATORIO_VIABILIDADE.md`
- Scripts de prova (parsers prontos): `risco-urbano-probes/probe_cge.py`, `probe_cemaden.py`, `probe_clima.py`, `probe_crime_geosampa.py`, `probe_ssp_microdados.py`, `probe_geocoding_geosampa.py` e saídas `saida_*.json`
- Código do MVP: repositório `mapa-risco-urbano` (backend FastAPI + frontend React)
