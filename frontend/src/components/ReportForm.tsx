import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import { createReport, track } from "../api";
import { Feature } from "../types";

const categories = [
  ["alagamento", "Alagamento", "#3b82f6"],
  ["transito", "Trânsito", "#22c55e"],
  ["clima", "Clima", "#ef4444"],
  ["seguranca", "Segurança", "#dc2626"],
  ["outro", "Outro", "#8b8b93"],
] as const;

export function ReportForm({
  point,
  onClose,
  onCreated,
}: {
  point: { lat: number; lng: number };
  onClose: () => void;
  onCreated: (feature: Feature) => void;
}) {
  const [category, setCategory] = useState<(typeof categories)[number][0]>("alagamento");
  const [description, setDescription] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, [onClose]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      const result = await createReport({ category, description, lat: point.lat, lon: point.lng });
      track("report_created", { category });
      onCreated(result);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Erro ao enviar");
    }
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <form
        className="report-modal"
        onSubmit={submit}
        role="dialog"
        aria-modal="true"
        aria-labelledby="report-title"
      >
        <button type="button" className="close" onClick={onClose} aria-label="Fechar">
          ×
        </button>
        <p className="eyebrow">RELATO DA COMUNIDADE</p>
        <h2 id="report-title">Reportar ocorrência</h2>
        <p className="muted">
          O ponto foi marcado no mapa. O relato será publicado sem dados pessoais.
        </p>
        <fieldset className="category-field">
          <legend>Categoria</legend>
          <div className="category-segmented">
            {categories.map(([value, name, color]) => (
              <button
                className={category === value ? "category-option selected" : "category-option"}
                key={value}
                type="button"
                aria-pressed={category === value}
                onClick={() => setCategory(value)}
              >
                <span className="category-swatch" style={{ backgroundColor: color }} />
                {name}
              </button>
            ))}
          </div>
        </fieldset>
        <label className="description-label">
          Descrição
          <span className="character-count">{description.length}/280</span>
          <textarea
            required
            maxLength={280}
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="Conte o que está acontecendo"
          />
        </label>
        <p className="lgpd-note">
          Não inclua nomes, telefones ou outros dados pessoais. Relatos expiram automaticamente.
        </p>
        <div className="report-actions">
          <button className="button ghost" type="button" onClick={onClose}>
            Cancelar
          </button>
          <button className="button primary" type="submit">
            Enviar relato
          </button>
        </div>
        {message && (
          <p className="form-message" role="alert">
            {message}
          </p>
        )}
      </form>
    </div>
  );
}
