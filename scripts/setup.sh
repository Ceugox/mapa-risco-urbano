#!/usr/bin/env bash
# Prepara um checkout novo para trabalhar: venv do backend e node_modules do
# frontend. É o setup hook que o Orca roda ao criar um worktree (`--setup run`),
# e serve igual para um clone manual.
#
# Por que existe: em 14/09/2026 cinco agentes em worktrees sem node_modules
# criaram junctions (mklink /J) apontando para o checkout principal. A limpeza
# com `git worktree remove --force` seguiu as junctions e apagou o node_modules
# real. Um worktree que se instala sozinho remove o motivo de existir junction.
#
# Idempotente: rodar de novo em checkout já preparado não refaz nada.
# Falha fechada: qualquer passo que quebrar aborta com mensagem e status != 0,
# porque worktree meio pronto é pior que worktree sem setup.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# O registro npm público está bloqueado nesta rede; o mirror do Yarn serve os
# mesmos tarballs. Sobrescreva exportando NPM_REGISTRY antes de chamar.
NPM_REGISTRY="${NPM_REGISTRY:-https://registry.yarnpkg.com}"

log() { printf '[setup] %s\n' "$*"; }

# --- backend: venv + dependências -------------------------------------------
# O venv fica dentro do checkout (backend/.venv, ignorado pelo git) para cada
# worktree ter o seu: venv compartilhado entre worktrees quebra quando um deles
# é removido.
if [ -x "backend/.venv/Scripts/python.exe" ] || [ -x "backend/.venv/bin/python" ]; then
  log "backend: venv já existe, pulando"
else
  log "backend: criando venv"
  python -m venv backend/.venv
fi

if [ -x "backend/.venv/Scripts/python.exe" ]; then
  VENV_PY="backend/.venv/Scripts/python.exe"   # Windows
else
  VENV_PY="backend/.venv/bin/python"           # Linux e macOS
fi

log "backend: instalando requirements"
"$VENV_PY" -m pip install --quiet --disable-pip-version-check -r backend/requirements.txt

# --- frontend: node_modules --------------------------------------------------
# `npm ci` exige package-lock.json e apaga node_modules antes de instalar, que é
# o que garante o mesmo conteúdo em todo worktree.
if [ -d "frontend/node_modules/.bin" ]; then
  log "frontend: node_modules já existe, pulando"
else
  log "frontend: npm ci (registry $NPM_REGISTRY)"
  npm ci --prefix frontend --registry "$NPM_REGISTRY" --no-audit --no-fund
fi

# --- prova de que o checkout está utilizável ---------------------------------
# Não roda a suíte inteira: o setup prova que as ferramentas respondem, a
# verificação de código é a seção `## Verificação` do AGENTS.md.
log "conferindo ferramentas"
"$VENV_PY" -c "import fastapi, h3, shapely, psycopg" \
  || { echo "[setup] ERRO: dependências do backend não importam" >&2; exit 1; }
[ -x "frontend/node_modules/.bin/vite" ] || [ -f "frontend/node_modules/.bin/vite" ] \
  || { echo "[setup] ERRO: frontend/node_modules/.bin/vite ausente" >&2; exit 1; }

log "pronto. Verificação do projeto: ver a seção '## Verificação' do AGENTS.md"
