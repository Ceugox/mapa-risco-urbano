# MapaSP — o mapa de risco urbano de São Paulo

[![CI](https://github.com/Ceugox/mapa-risco-urbano/actions/workflows/ci.yml/badge.svg)](https://github.com/Ceugox/mapa-risco-urbano/actions/workflows/ci.yml)
[![Licença MIT](https://img.shields.io/badge/licen%C3%A7a-MIT-black)](LICENSE)
[![App no ar](https://img.shields.io/badge/app-mapasp.com-c8f04c)](https://mapasp.com)

**No ar em [mapasp.com](https://mapasp.com).** Código aberto, sem cadastro, de graça.

> 🏆 **1º lugar no Hack for Humanity São Paulo**, 12 de setembro de 2026 — hackathon da
> [The AI Collective](https://theaicollective.com) na Universidade Anhembi Morumbi, no
> desafio que o capítulo São Paulo escolheu por conta própria: **resiliência urbana**.
> Construído do zero no dia, em quatro horas de hacking, sob a regra da casa: resolver um
> problema da nossa comunidade.

---

## O problema

Nos últimos 12 meses, por medo da violência, **36,5%** dos brasileiros de 16 anos ou mais
mudaram um percurso rotineiro e **35,6%** deixaram de sair à noite. Entre as mulheres,
**40,9%** deixaram de sair à noite, contra 29,8% dos homens — onze pontos de diferença.

<sub>Fórum Brasileiro de Segurança Pública e Instituto Datafolha, [*"Medo do crime e
eleições 2026: os gatilhos da
insegurança"*](https://forumseguranca.org.br/wp-content/uploads/2026/05/os-gatilhos-da-inseguranca-relatorio-completo-2026.pdf).
Campo em 9 e 10 de março de 2026, 2.004 entrevistas pessoais em 137 municípios, margem de
±2 pontos, confiança de 95%.</sub>

A informação que evitaria parte disso **já existe e é pública** — e está espalhada por seis
órgãos, em seis formatos, nenhum deles feito para quem só quer saber se dá para ir a pé até
o ponto de ônibus às 6h da manhã.

O MapaSP junta tudo num mapa só e responde três perguntas:

- **Qual o risco aqui e agora?** A sua vizinhança imediata — a célula H3 em que você está
  mais as adjacentes, cerca de 800 m — resumida por camada.
- **Qual o caminho mais seguro?** Rotas a pé ou de carro, pontuadas por risco, com peso
  ajustado pelo horário da saída.
- **Você chegou bem?** Um link que seu círculo acompanha ao vivo, sem instalar nada, que
  expira sozinho.

## O que tem no mapa

| Camada | Fonte | Atualização | Observação |
|---|---|---|---|
| Alagamento agora | CGE-SP | a cada coleta | geocodificação própria sobre a malha do GeoSampa |
| Recorrência de alagamento | histórico próprio do CGE | 30 dias corridos | episódios por ponto; começa desligada |
| Deslizamento e hidrológico | CEMADEN | a cada coleta | alerta por município |
| Clima severo | INMET avisos | a cada coleta | polígono de abrangência |
| Clima | Open-Meteo | 15 min | observação e previsão |
| Crime agregado | SSP-SP microdados | mensal, ~2 meses de atraso | jan–jul/2026; começa desligada |
| Relatos da comunidade | quem está na rua | ao vivo | anônimos, expiram em 6 h ou 24 h |
| Trânsito | Google Maps | tempo real | camada visual, não persistida |

Cada camada mostra **a própria idade e o próprio status** na interface. Quando uma fonte
cai, o mapa diz qual caiu e continua mostrando o último dado válido, carimbado. Crime tem
dois meses de atraso e alagamento é quase ao vivo: misturar os dois sem avisar seria
desonesto.

## Princípios que o código respeita

**Crime é sempre agregado, nunca individual.** A camada sai dos microdados da SSP-SP e é
reduzida a células H3 de resolução 8 (~0,74 km²). Célula com menos de cinco ocorrências é
descartada; registro com logradouro suprimido não é mapeado. Nenhum boletim, endereço ou
vítima aparece. Hoje são **1.415 células e 222.523 ocorrências** de janeiro a julho de 2026.
A camada **começa desligada**, e a legenda declara o período e o atraso. Mapa de segurança
que estigmatiza a periferia não serve como mapa de segurança.

**Não prometer tempo real onde não há.** Toda camada carrega a hora da última coleta.

**Relato não pede quem você é.** Anônimo, sem dado pessoal, com limite por IP, confirmação
por corroboração e expiração automática. Relato de segurança só fica visível com duas
confirmações independentes.

**Uma fonte que cai não derruba o mapa.** Coletores falham isolados, o erro é registrado, o
último snapshot bom é preservado e a interface sinaliza.

## Como ajudar

O app está no ar, o código é aberto e estamos começando por São Paulo — mas o alcance disso
depende de gente que hoje não está na mesa. Se você é uma dessas pessoas, [abra uma
issue](https://github.com/Ceugox/mapa-risco-urbano/issues/new) e vamos conversar:

**Prefeitura de São Paulo e Governo do Estado** — a camada mais quente do mapa é raspada de
uma página HTML sem contrato, e a mais sensível chega com dois meses de atraso. Um endpoint
estável do CGE e da COE, e a base da SSP com menos defasagem, mudam o produto de patamar. A
CET tem dados de sinistro que hoje não estão aqui. O caminho inverso também vale: os relatos
da comunidade são um sensor que a cidade ainda não tem.

**Google e Waze** — o trânsito aparece pela Maps JS API e por isso é só visual: não entra no
cálculo de rota nem é persistido, porque a licença não permite. Com [Waze for
Cities](https://www.waze.com/wazeforcities) ou um acordo equivalente, alerta de via e
incidente entram no score da rota. Cota de Maps para uso cívico também resolve um gargalo
real.

**Plataformas e infraestrutura** — hospedagem, banco, CDN, tiles de mapa, geocodificação.
Hoje o projeto roda em conta pessoal e a busca de endereço depende de serviço comunitário
gratuito. Crédito de infra vira alcance direto.

**Quem pesquisa segurança pública, mobilidade e clima** — o score de rota pondera camadas com
pesos que vieram de julgamento, não de estudo. Se você trabalha com isso, o modelo precisa de
você mais do que precisa de mais código.

**Quem conhece o território** — um bairro, uma linha de ônibus, um trajeto que você faz todo
dia. Onde o mapa erra, erra para quem está na rua.

**Quem programa** — as issues abertas e o `AGENTS.md` dizem o que falta. Toda contribuição
entra pela mesma porta: CI verde e a seção de verificação abaixo.

## Rodar localmente

Requisitos: Python 3.10+ e Node 20. Um checkout novo se instala sozinho:

```bash
node scripts/setup.mjs
```

Depois, backend e frontend em terminais separados:

```bash
uvicorn app.main:app --reload --app-dir backend    # http://localhost:8000
npm --prefix frontend run dev                      # http://localhost:5173
```

Copie `frontend/.env.example` para `frontend/.env` e preencha `VITE_GOOGLE_MAPS_API_KEY`.
**Nenhuma chave vive no repositório.** A camada de crime já vem versionada em
`backend/data/crime_h3.json`; só rode `python backend/scripts/build_crime_layer.py` para
regenerá-la, porque ele baixa ~111 MB da SSP-SP.

## Verificação

Obrigatória em qualquer alteração. Cada linha é um comando único, rodado da raiz, e o CI
roda exatamente estes passos:

```bash
ruff check backend
pytest backend/tests
npm --prefix frontend run build
npm --prefix frontend run lint
```

## Arquitetura

FastAPI e SQLite com WAL (ou Postgres, via `DATABASE_URL`) no backend; Vite, React,
TypeScript e Google Maps no frontend; PWA instalável com o último snapshot disponível
offline. Os coletores rodam em scheduler dentro do próprio processo. `AGENTS.md` tem o mapa
completo do código, as regras que não podem ser quebradas e o estado conhecido de cada
pendência — leia antes de mexer.

## Licença

MIT. Ver [LICENSE](LICENSE).

Os dados vêm de CGE-SP, CEMADEN, INMET, Open-Meteo, SSP-SP e GeoSampa, cada um sob os
próprios termos. O trânsito é do Google Maps e não é redistribuído.
