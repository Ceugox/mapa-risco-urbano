import { useEffect, useState } from "react";
import { getRiskHere, RiskHereResult } from "../api";
import { Place, searchPlaces } from "../places";

type SlotKey = "here" | "home" | "work";
type SavedPlace = { label: string; lat: number; lng: number; lastLevel?: string };
type PlacesStore = Partial<Record<"home" | "work", SavedPlace>>;

type SlotState = {
  place?: SavedPlace;
  query: string;
  suggestions: Place[];
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
  return { query: "", suggestions: [], changed: false, status: "", loading: false };
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

  async function suggest(key: "home" | "work", q: string) {
    patch(key, { query: q });
    if (q.trim().length < 3) {
      patch(key, { suggestions: [] });
      return;
    }
    const found = await searchPlaces(q);
    patch(key, { suggestions: found });
  }

  function choosePlace(key: "home" | "work", found: Place) {
    const place: SavedPlace = { label: shortLabel(found.label), lat: found.lat, lng: found.lng };
    const store = loadPlaces();
    store[key] = place;
    persistPlaces(store);
    patch(key, { place, query: place.label, suggestions: [] });
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
            onQueryChange={(q) => suggest(key as "home" | "work", q)}
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
            onChange={(event) => onQueryChange(event.target.value)}
            placeholder={`Endereço de ${title.toLowerCase()}…`}
            aria-label={`Endereço de ${title}`}
          />
          {state.suggestions.length > 0 && (
            <ul className="here-suggestions" role="listbox">
              {state.suggestions.map((place, index) => (
                <li key={index}>
                  <button type="button" onClick={() => onChoose(place)}>
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
