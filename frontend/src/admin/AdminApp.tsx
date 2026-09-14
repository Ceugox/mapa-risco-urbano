import { FormEvent, useCallback, useEffect, useState } from "react";
import { adminLogin, adminStats, AdminStats } from "../api";
import "../styles.css";
import "./admin.css";

const TOKEN_KEY = "mapasp_admin_token";
const RANGES: { key: string; label: string }[] = [
  { key: "24h", label: "24 horas" },
  { key: "7d", label: "7 dias" },
  { key: "30d", label: "30 dias" },
];

function fmt(value: number) {
  return value.toLocaleString("pt-BR");
}

function bucketLabel(bucket: string, range: string) {
  if (range === "24h") {
    const date = new Date(`${bucket}:00:00Z`);
    return date.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  }
  const date = new Date(`${bucket}T12:00:00Z`);
  return date.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
}

function Login({ onToken }: { onToken: (token: string) => void }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await adminLogin(password);
      onToken(result.token);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Falha no login");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="admin-login">
      <form className="admin-login-card" onSubmit={submit}>
        <a className="brand" href="/">
          MAPA<span>SP</span>
        </a>
        <p className="eyebrow">PAINEL DO ADMINISTRADOR</p>
        <h1>Acessos e uso</h1>
        <label htmlFor="admin-pass">Senha de administrador</label>
        <input
          id="admin-pass"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
        />
        {error && (
          <p className="admin-error" role="alert">
            {error}
          </p>
        )}
        <button className="button primary" type="submit" disabled={busy}>
          {busy ? "Entrando…" : "Entrar"}
        </button>
        <small>Só quem tem a senha configurada no servidor entra aqui.</small>
      </form>
    </main>
  );
}

function Kpi({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="kpi">
      <span className="kpi-label">{label}</span>
      <strong className="kpi-value">{value}</strong>
      {hint && <span className="kpi-hint">{hint}</span>}
    </div>
  );
}

function Bars({ series, range }: { series: AdminStats["series"]; range: string }) {
  const [hover, setHover] = useState<number | null>(null);
  const width = 720;
  const height = 180;
  const pad = { top: 12, right: 8, bottom: 28, left: 36 };
  const max = Math.max(1, ...series.map((point) => point.page_views));
  const innerW = width - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;
  const slot = innerW / series.length;
  const barW = Math.max(2, slot - 2);
  const ticks = [0, Math.ceil(max / 2), max];
  const labelEvery = Math.ceil(series.length / (range === "24h" ? 8 : 7));

  return (
    <div className="chart">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Visitas por período">
        {ticks.map((tick) => {
          const y = pad.top + innerH - (tick / max) * innerH;
          return (
            <g key={tick}>
              <line className="grid" x1={pad.left} x2={width - pad.right} y1={y} y2={y} />
              <text className="tick" x={pad.left - 8} y={y + 3} textAnchor="end">
                {tick}
              </text>
            </g>
          );
        })}
        {series.map((point, index) => {
          const h = (point.page_views / max) * innerH;
          const x = pad.left + index * slot + (slot - barW) / 2;
          const y = pad.top + innerH - h;
          return (
            <g
              key={point.bucket}
              onMouseEnter={() => setHover(index)}
              onMouseLeave={() => setHover(null)}
              onFocus={() => setHover(index)}
              onBlur={() => setHover(null)}
              tabIndex={0}
            >
              <rect
                className="hit"
                x={pad.left + index * slot}
                y={pad.top}
                width={slot}
                height={innerH}
              />
              <rect
                className={`bar${hover === index ? " active" : ""}`}
                x={x}
                y={y}
                width={barW}
                height={Math.max(h, point.page_views ? 2 : 0)}
                rx={2}
              />
              {index % labelEvery === 0 && (
                <text className="tick" x={x + barW / 2} y={height - 8} textAnchor="middle">
                  {bucketLabel(point.bucket, range)}
                </text>
              )}
            </g>
          );
        })}
        <line
          className="axis"
          x1={pad.left}
          x2={width - pad.right}
          y1={pad.top + innerH}
          y2={pad.top + innerH}
        />
      </svg>
      {hover !== null && series[hover] && (
        <div className="chart-tip" role="status">
          <strong>{bucketLabel(series[hover].bucket, range)}</strong>
          <span>{fmt(series[hover].page_views)} visitas</span>
          <span>{fmt(series[hover].visitors)} visitantes</span>
          <span>{fmt(series[hover].requests)} requisições</span>
          <span>{fmt(series[hover].errors)} erros</span>
        </div>
      )}
    </div>
  );
}

function RankList({
  title,
  items,
  empty,
}: {
  title: string;
  items: { name: string; count: number }[];
  empty: string;
}) {
  const max = Math.max(1, ...items.map((item) => item.count));
  return (
    <section className="admin-card">
      <h2>{title}</h2>
      {items.length === 0 ? (
        <p className="admin-empty">{empty}</p>
      ) : (
        <ol className="rank">
          {items.map((item) => (
            <li key={item.name}>
              <span className="rank-name" title={item.name}>
                {item.name}
              </span>
              <span className="rank-bar" aria-hidden="true">
                <span style={{ width: `${(item.count / max) * 100}%` }} />
              </span>
              <span className="rank-count">{fmt(item.count)}</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

const NAMES: Record<string, string> = {
  mobile: "celular",
  desktop: "computador",
  unknown: "desconhecido",
  other: "outro",
};

function toItems(record: Record<string, number>) {
  return Object.entries(record)
    .map(([name, count]) => ({ name: NAMES[name] ?? name, count }))
    .sort((a, b) => b.count - a.count);
}

export function AdminApp() {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY) || "");
  const [range, setRange] = useState("7d");
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setToken("");
    setStats(null);
  }, []);

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      setStats(await adminStats(token, range));
      setError("");
    } catch (exc) {
      if (exc instanceof Error && exc.message === "unauthorized") {
        logout();
        return;
      }
      setError("Não foi possível carregar os dados agora.");
    } finally {
      setLoading(false);
    }
  }, [token, range, logout]);

  useEffect(() => {
    load();
    const timer = window.setInterval(load, 60000);
    return () => window.clearInterval(timer);
  }, [load]);

  if (!token) {
    return (
      <Login
        onToken={(value) => {
          localStorage.setItem(TOKEN_KEY, value);
          setToken(value);
        }}
      />
    );
  }

  const kpi = stats?.kpi;
  const generated = stats
    ? new Date(stats.generated_at).toLocaleTimeString("pt-BR", {
        hour: "2-digit",
        minute: "2-digit",
      })
    : "--:--";

  return (
    <div className="admin">
      <header className="admin-header">
        <div className="admin-header-inner">
          <a className="brand" href="/">
            MAPA<span>SP</span>
          </a>
          <span className="admin-tag">ADMIN</span>
          <div className="admin-ranges" role="tablist" aria-label="Período">
            {RANGES.map((item) => (
              <button
                key={item.key}
                role="tab"
                aria-selected={range === item.key}
                className={`range-tab${range === item.key ? " active" : ""}`}
                onClick={() => setRange(item.key)}
                type="button"
              >
                {item.label}
              </button>
            ))}
          </div>
          <span className="admin-updated">
            {loading ? "atualizando…" : `atualizado ${generated}`}
          </span>
          <button className="button ghost" onClick={logout} type="button">
            Sair
          </button>
        </div>
      </header>

      <main className="admin-main">
        {error && (
          <p className="admin-error" role="alert">
            {error}
          </p>
        )}

        <section className="kpi-grid" aria-label="Indicadores">
          <Kpi
            label="Visitas"
            value={kpi ? fmt(kpi.page_views) : "—"}
            hint="páginas abertas, sem bots"
          />
          <Kpi label="Visitantes" value={kpi ? fmt(kpi.visitors) : "—"} hint="únicos por dia" />
          <Kpi label="Rotas calculadas" value={kpi ? fmt(kpi.routes) : "—"} />
          <Kpi label="Relatos criados" value={kpi ? fmt(kpi.reports) : "—"} />
          <Kpi label="Chamadas de API" value={kpi ? fmt(kpi.api_calls) : "—"} />
          <Kpi
            label="Erros 5xx"
            value={kpi ? fmt(kpi.errors) : "—"}
            hint={kpi ? `${kpi.error_rate.toLocaleString("pt-BR")}% das requisições` : undefined}
          />
          <Kpi label="p95 da API" value={kpi ? `${fmt(Math.round(kpi.p95_ms))} ms` : "—"} />
          <Kpi
            label="Contas"
            value={kpi ? fmt(kpi.users_total) : "—"}
            hint={
              kpi
                ? `${fmt(kpi.reports_total)} relatos no total · ${fmt(kpi.bots)} hits de bots`
                : undefined
            }
          />
        </section>

        <section className="admin-card admin-chart">
          <div className="admin-card-head">
            <h2>Visitas por {range === "24h" ? "hora" : "dia"}</h2>
            <span className="admin-note">UTC · passe o mouse para detalhes</span>
          </div>
          {stats ? (
            <Bars series={stats.series} range={range} />
          ) : (
            <p className="admin-empty">Carregando…</p>
          )}
        </section>

        <div className="admin-grid">
          <RankList
            title="Rotas mais acessadas"
            items={(stats?.top_paths ?? []).map((item) => ({ name: item.path, count: item.count }))}
            empty="Sem acessos no período."
          />
          <RankList
            title="Ações no app"
            items={stats?.events ?? []}
            empty="Nenhum evento registrado ainda."
          />
          <RankList
            title="Origem do tráfego"
            items={stats?.referers ?? []}
            empty="Sem referenciadores (acesso direto)."
          />
          <RankList
            title="Dispositivos"
            items={stats ? toItems(stats.devices) : []}
            empty="Sem visitas no período."
          />
          <RankList
            title="Navegadores"
            items={stats ? toItems(stats.browsers) : []}
            empty="Sem visitas no período."
          />
        </div>

        <section className="admin-card">
          <h2>Erros recentes</h2>
          {!stats || stats.recent_errors.length === 0 ? (
            <p className="admin-empty">Nenhum erro 5xx no período.</p>
          ) : (
            <div className="table-wrap admin-table">
              <table>
                <thead>
                  <tr>
                    <th>Quando</th>
                    <th>Método</th>
                    <th>Rota</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {stats.recent_errors.map((item, index) => (
                    <tr key={`${item.ts}-${index}`}>
                      <td>{new Date(item.ts).toLocaleString("pt-BR")}</td>
                      <td>{item.method}</td>
                      <td>{item.path}</td>
                      <td>{item.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <p className="admin-footnote">
          Nenhum dado pessoal é guardado: o IP vira um hash diário com sal e é descartado. Registros
          expiram em 90 dias.
        </p>
      </main>
    </div>
  );
}
