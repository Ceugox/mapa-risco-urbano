import { readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

const here = dirname(fileURLToPath(import.meta.url));

// Copia public/sw.js para dist/sw.js trocando o placeholder __BUILD__ pelo
// timestamp do build, para que o service worker mude de versão a cada build
// e o cliente detecte a atualização.
function serviceWorkerBuildId(): Plugin {
  return {
    name: "sw-build-id",
    closeBundle() {
      const src = resolve(here, "public/sw.js");
      const dest = resolve(here, "dist/sw.js");
      const contents = readFileSync(src, "utf-8").replace(/__BUILD__/g, String(Date.now()));
      writeFileSync(dest, contents);
    },
  };
}

export default defineConfig({ plugins: [react(), serviceWorkerBuildId()] });
