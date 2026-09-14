// Prepara um checkout novo para trabalhar: venv do backend e node_modules do
// frontend. É o setup hook que o Orca roda ao criar um worktree (orca.yaml),
// e serve igual para um clone manual: `node scripts/setup.mjs`.
//
// Por que Node e não shell: no Windows o runner do Orca chama o comando por
// cmd.exe, e ali `bash` resolve para o bash do WSL, não para o Git Bash. Sem
// distro instalada isso falha com
// `execvpe(/bin/bash) failed: No such file or directory` e o worktree nasce
// vazio em silêncio. Node já é dependência dura deste repo e existe nos dois
// sistemas.
//
// Por que existe: em 14/09/2026 cinco agentes em worktrees sem node_modules
// criaram junctions (mklink /J) apontando para o checkout principal. A limpeza
// com `git worktree remove --force` seguiu as junctions e apagou o node_modules
// real. Um worktree que se instala sozinho remove o motivo de existir junction.
//
// Idempotente: rodar de novo em checkout já preparado não refaz nada.
// Falha fechada: qualquer passo que quebrar aborta com status != 0, porque
// worktree meio pronto é pior que worktree sem setup.

import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const ehWindows = process.platform === "win32";

// O registro npm público está bloqueado nesta rede; o mirror do Yarn serve os
// mesmos tarballs. Sobrescreva exportando NPM_REGISTRY antes de chamar.
const REGISTRY = process.env.NPM_REGISTRY ?? "https://registry.yarnpkg.com";

const log = (msg) => console.log(`[setup] ${msg}`);

// shell só onde é necessário. `npm` é um .cmd e `python` do PATH não tem
// extensão, então os dois precisam do shell no Windows; o interpretador do venv
// vem por caminho absoluto e roda sem ele. Isso não é detalhe: com shell:true o
// cmd.exe reescreve os argumentos, e `python -c "import fastapi, h3, shapely"`
// chegava do outro lado como `import`, quebrando a conferência final.
function rodar(comando, args, { shell = false } = {}) {
  execFileSync(comando, args, { cwd: ROOT, stdio: "inherit", shell });
}

function pythonDoVenv() {
  const windows = join(ROOT, "backend", ".venv", "Scripts", "python.exe");
  const unix = join(ROOT, "backend", ".venv", "bin", "python");
  if (existsSync(windows)) return windows;
  if (existsSync(unix)) return unix;
  return null;
}

// --- backend: venv + dependências -------------------------------------------
// O venv fica dentro do checkout (backend/.venv, ignorado pelo git) para cada
// worktree ter o seu: venv compartilhado entre worktrees quebra quando um deles
// é removido.
if (pythonDoVenv()) {
  log("backend: venv já existe, pulando");
} else {
  log("backend: criando venv");
  rodar("python", ["-m", "venv", "backend/.venv"], { shell: ehWindows });
}

const python = pythonDoVenv();
if (!python) {
  console.error("[setup] ERRO: venv criado mas o interpretador não apareceu");
  process.exit(1);
}

log("backend: instalando requirements");
rodar(python, [
  "-m",
  "pip",
  "install",
  "--quiet",
  "--disable-pip-version-check",
  "-r",
  "backend/requirements.txt",
]);

// --- frontend: node_modules --------------------------------------------------
// `npm ci` exige package-lock.json e apaga node_modules antes de instalar, que é
// o que garante o mesmo conteúdo em todo worktree.
if (existsSync(join(ROOT, "frontend", "node_modules", ".bin"))) {
  log("frontend: node_modules já existe, pulando");
} else {
  log(`frontend: npm ci (registry ${REGISTRY})`);
  rodar("npm", ["ci", "--prefix", "frontend", "--registry", REGISTRY, "--no-audit", "--no-fund"], {
    shell: ehWindows,
  });
}

// --- prova de que o checkout está utilizável ---------------------------------
// Não roda a suíte inteira: o setup prova que as ferramentas respondem, a
// verificação de código é a seção `## Verificação` do AGENTS.md.
log("conferindo ferramentas");
try {
  rodar(python, ["-c", "import fastapi, h3, shapely, psycopg"]);
} catch {
  console.error("[setup] ERRO: dependências do backend não importam");
  process.exit(1);
}

const vite = join(ROOT, "frontend", "node_modules", ".bin", "vite");
if (!existsSync(vite) && !existsSync(`${vite}.cmd`)) {
  console.error("[setup] ERRO: frontend/node_modules/.bin/vite ausente");
  process.exit(1);
}

log("pronto. Verificação do projeto: ver a seção '## Verificação' do AGENTS.md");
