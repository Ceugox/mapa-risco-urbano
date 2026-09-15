import { useCallback, useEffect, useRef, useState } from "react";

export type Place = { lat: number; lng: number; label: string };

const base = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

// Espera esta pausa na digitação antes de consultar. Curto o bastante para
// parecer instantâneo, longo o bastante para não disparar uma busca por tecla.
const PAUSA_MS = 180;
const MIN_CARACTERES = 2;

/** Sugestões para uma consulta parcial, pelo nosso backend.
 *
 * Não fala com o Google nem com o Nominatim daqui: o Places do Google responde
 * REQUEST_DENIED para projetos novos e o Nominatim bloqueia por CORS quando
 * chamado do browser. Quem resolve isso é `backend/app/places.py`.
 */
export async function searchPlaces(q: string, signal?: AbortSignal): Promise<Place[]> {
  const consulta = q.trim();
  if (consulta.length < MIN_CARACTERES) return [];
  const response = await fetch(`${base}/api/places/suggest?q=${encodeURIComponent(consulta)}`, {
    signal,
  });
  if (!response.ok) return [];
  const data: { places?: { label: string; lat: number; lon: number }[] } = await response.json();
  return (data.places ?? []).map((p) => ({ lat: p.lat, lng: p.lon, label: p.label }));
}

/** Autocompletar de endereço: uma pausa na digitação dispara a busca.
 *
 * Guarda a ordem das respostas. Sem isso, a resposta de "rua a" pode chegar
 * depois da de "rua augusta" e sobrescrever a lista com o resultado antigo —
 * era esse o motivo de a sugestão nunca corresponder ao que se acabou de
 * digitar.
 */
export function useSuggestions() {
  const [suggestions, setSuggestions] = useState<Place[]>([]);
  const [searching, setSearching] = useState(false);
  const sequencia = useRef(0);
  const timer = useRef<number | undefined>(undefined);
  const emVoo = useRef<AbortController | undefined>(undefined);

  const cancelar = useCallback(() => {
    window.clearTimeout(timer.current);
    emVoo.current?.abort();
    emVoo.current = undefined;
  }, []);

  const clear = useCallback(() => {
    cancelar();
    sequencia.current += 1;
    setSuggestions([]);
    setSearching(false);
  }, [cancelar]);

  const query = useCallback(
    (texto: string) => {
      cancelar();
      if (texto.trim().length < MIN_CARACTERES) {
        sequencia.current += 1;
        setSuggestions([]);
        setSearching(false);
        return;
      }
      const minhaVez = ++sequencia.current;
      // Não mantenha opções da consulta anterior visíveis durante a pausa:
      // elas não correspondem mais ao conteúdo do campo.
      setSuggestions([]);
      setSearching(true);
      timer.current = window.setTimeout(async () => {
        const controller = new AbortController();
        emVoo.current = controller;
        try {
          const found = await searchPlaces(texto, controller.signal);
          if (minhaVez !== sequencia.current) return; // resposta atrasada
          setSuggestions(found);
        } catch {
          if (minhaVez === sequencia.current) setSuggestions([]);
        } finally {
          if (minhaVez === sequencia.current) {
            emVoo.current = undefined;
            setSearching(false);
          }
        }
      }, PAUSA_MS);
    },
    [cancelar],
  );

  useEffect(() => cancelar, [cancelar]);

  return { suggestions, searching, query, clear };
}
