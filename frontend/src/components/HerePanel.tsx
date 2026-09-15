import { KeyboardEvent, useEffect, useId, useState } from "react";
import { getRiskHere, RiskHereResult } from "../api";
import { Place, useSuggestions } from "../places";

type SlotKey = "here" | "home" | "work";
type SavedPlace = { label: string; lat: number; lng: number; lastLevel?: string };
type PlacesStore = Partial<Record<"home" | "work", SavedPlace>>;

type SlotState = {
  place?: SavedPlace;
  query: string;
  result?: RiskHereResult;
  queriedAt?: string;
  changed: boolean;
  status: string;
  loading: boolean;
};

const PLACES_KEY = "mapasp_places";
const SLOT_TITLE: Record<SlotKey, string> = {
  here: "Posição atual",
  home: "Casa",
  work: "Trabalho",
};
const LEVEL_LABEL: Record<string, string> = { baixo: "Baixo", moderado: "Moderado", alto: "Alto" };
const LEVEL_VAR: Record<string, string> = {
  baixo: "var(--ok)",
  moderado: "var(--warn)",
  alto: "var(--err)",
};

function emptySlot(): SlotState {
  return { query: "", changed: false, status: "", loading: false };
}

function loadPlaces(): PlacesStore {
  try {
    return JSON.parse(localStorage.getItem(PLACES_KEY) ?? "{}");
  } catch {
    return {};
  }
}

function persistPlaces(store: PlacesStore) {
  localStorage.setItem(PLACES_KEY, JSON.stringify(store));
}

function shortLabel(label: string) {
  return label.split(",")[0].split("—")[0].trim();
}

export function HerePanel() {
  const [slots, setSlots] = useState<Record<SlotKey, SlotState>>({
    here: emptySlot(),
    home: emptySlot(),
    work: emptySlot(),
  });

  function patch(key: SlotKey, next: Partial<SlotState>) {
    setSlots((state) => ({ ...state, [key]: { ...state[key], ...next } }));
  }

  async function evaluate(key: SlotKey, lat: number, lng: number, place?: SavedPlace) {
    patch(key, { loading: true, status: "Consultando risco…" });
    try {
      const result = await getRiskHere(lat, lng);
      const previousLevel = place?.lastLevel;
      const changed = Boolean(previousLevel && previousLevel !== result.level);
      patch(key, {
        result,
        changed,
        status: "",
        loading: false,
        queriedAt: new Date().toISOString(),
      });
      if (key !== "here" && place) {
        const store = loadPlaces();
        const updated: SavedPlace = { ...place, lastLevel: result.level };
        store[key] = updated;
        persistPlaces(store);
        patch(key, { place: updated });
      }
    } catch {
      patch(key, { loading: false, status: "Não foi possível avaliar o risco agora." });
    }
  }

  useEffect(() => {
    const store = loadPlaces();
    (["home", "work"] as const).forEach((key) => {
      const place = store[key];
      if (!place) return;
      patch(key, { place, query: place.label });
      evaluate(key, place.lat, place.lng, place);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function useMyPosition() {
    if (!navigator.geolocation) {
      patch("here", { status: "Geolocalização não disponível neste aparelho." });
      return;
    }
    patch("here", { status: "Localizando…", loading: true });
    navigator.geolocation.getCurrentPosition(
      (pos) => evaluate("here", pos.coords.latitude, pos.coords.longitude),
      () => patch("here", { status: "Não foi possível obter sua localização.", loading: false }),
      { enableHighAccuracy: true, timeout: 10000 },
    );
  }

  function choosePlace(key: "home" | "work", found: Place) {
    const place: SavedPlace = { label: shortLabel(found.label), lat: found.lat, lng: found.lng };
    const store = loadPlaces();
    store[key] = place;
    persistPlaces(store);
    patch(key, { place, query: place.label });
    evaluate(key, place.lat, place.lng, place);
  }

  return (
    <section id="agora" className="here section container">
      <div className="section-intro">
        <p className="eyebrow">EM TEMPO REAL</p>
        <h2>Risco aqui e agora</h2>
        <p>
          Um resumo do que há de risco num raio de 800 m a partir de onde você está ou dos seus
          lugares salvos.
        </p>
      </div>
      <div className="here-actions">
        <button className="button primary" onClick={useMyPosition} type="button">
          Usar minha posição
        </button>
      </div>
      <div className="here-grid">
        {(Object.keys(SLOT_TITLE) as SlotKey[]).map((key) => (
          <HereCard
            key={key}
            slotKey={key}
            title={SLOT_TITLE[key]}
            state={slots[key]}
            onQueryChange={(q) => patch(key as "home" | "work", { query: q })}
            onChoose={(place) => choosePlace(key as "home" | "work", place)}
          />
        ))}
      </div>
    </section>
  );
}

function HereCard({
  slotKey,
  title,
  state,
  onQueryChange,
  onChoose,
}: {
  slotKey: SlotKey;
  title: string;
  state: SlotState;
  onQueryChange: (q: string) => void;
  onChoose: (place: Place) => void;
}) {
  const { result } = state;
  const { suggestions, query: querySuggestions, clear: clearSuggestions } = useSuggestions();
  const [activeSuggestion, setActiveSuggestion] = useState(-1);
  const suggestionListId = useId();

  function changeQuery(query: string) {
    setActiveSuggestion(-1);
    onQueryChange(query);
    querySuggestions(query);
  }

  function chooseSuggestion(place: Place) {
    setActiveSuggestion(-1);
    clearSuggestions();
    onChoose(place);
  }

  function navigateSuggestions(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Escape") {
      clearSuggestions();
      setActiveSuggestion(-1);
      return;
    }
    if (suggestions.length === 0) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveSuggestion((current) => Math.min(current + 1, suggestions.length - 1));
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveSuggestion((current) => Math.max(current - 1, 0));
    }
    if (event.key === "Enter") {
      event.preventDefault();
      chooseSuggestion(suggestions[activeSuggestion >= 0 ? activeSuggestion : 0]);
    }
  }

  return (
    <div className="here-card">
      <div className="here-card-head">
        <strong>{title}</strong>
        {result && (
          <span className="here-level" style={{ color: LEVEL_VAR[result.level] }}>
            {LEVEL_LABEL[result.level]}
          </span>
        )}
      </div>
      {state.changed && <span className="here-changed">mudou desde a última vez</span>}
      {slotKey !== "here" && (
        <div className="here-search">
          <input
            value={state.query}
            onChange={(event) => changeQuery(event.target.value)}
            onKeyDown={navigateSuggestions}
            placeholder={`Endereço de ${title.toLowerCase()}…`}
            aria-label={`Endereço de ${title}`}
            role="combobox"
            aria-autocomplete="list"
            aria-controls={suggestionListId}
            aria-expanded={suggestions.length > 0}
            aria-activedescendant={
              activeSuggestion >= 0 ? `${suggestionListId}-option-${activeSuggestion}` : undefined
            }
            autoComplete="off"
          />
          {suggestions.length > 0 && (
            <ul className="here-suggestions" id={suggestionListId} role="listbox">
              {suggestions.map((place, index) => (
                <li key={index} role="presentation">
                  <button
                    id={`${suggestionListId}-option-${index}`}
                    type="button"
                    role="option"
                    aria-selected={activeSuggestion === index}
                    onMouseEnter={() => setActiveSuggestion(index)}
                    onClick={() => chooseSuggestion(place)}
                  >
                    {place.label}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      {state.loading && <span className="here-status">Consultando…</span>}
      {!state.loading && state.status && <span className="here-status">{state.status}</span>}
      {result && (
        <>
          <ul className="here-items">
            {result.items.length === 0 ? (
              <li className="here-item-empty">Nenhum risco ativo por aqui agora.</li>
            ) : (
              result.items.map((item) => <li key={item.layer}>{item.label}</li>)
            )}
          </ul>
          {state.queriedAt && (
            <span className="here-updated">
              consultado às{" "}
              {new Date(state.queriedAt).toLocaleTimeString("pt-BR", {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </span>
          )}
        </>
      )}
    </div>
  );
}
