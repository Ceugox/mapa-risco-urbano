import { useState } from "react";

type Contact = { name: string; phone: string };

const KEY = "riscosp-contatos";
const MAX = 3;

const PHONES = [
  { n: "190", l: "Polícia Militar" },
  { n: "180", l: "Violência contra a mulher" },
  { n: "192", l: "SAMU" },
  { n: "193", l: "Bombeiros" },
];

function loadContacts(): Contact[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) || "[]");
  } catch {
    return [];
  }
}

function message(safe: boolean, lat?: number, lng?: number) {
  const loc = lat != null ? `\nMinha localização: https://maps.google.com/?q=${lat},${lng}` : "";
  return encodeURIComponent(
    safe ? `Cheguei bem!${loc}` : `EMERGENCIA — preciso de ajuda agora.${loc}`,
  );
}

export function EmergencyPanel() {
  const [contacts, setContacts] = useState<Contact[]>(loadContacts);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [status, setStatus] = useState("");

  function save(next: Contact[]) {
    setContacts(next);
    localStorage.setItem(KEY, JSON.stringify(next));
  }

  function add() {
    const digits = phone.replace(/\D/g, "");
    if (!name.trim() || digits.length < 10 || contacts.length >= MAX) return;
    save([
      ...contacts,
      { name: name.trim(), phone: digits.startsWith("55") ? digits : `55${digits}` },
    ]);
    setName("");
    setPhone("");
  }

  function send(safe: boolean) {
    if (!contacts.length) {
      setStatus("Cadastre um contato de confiança primeiro.");
      return;
    }
    setStatus("Obtendo localização…");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setStatus(safe ? "Abrindo WhatsApp…" : "Abrindo WhatsApp com sua localização…");
        contacts.forEach((c, i) =>
          window.setTimeout(
            () =>
              window.open(
                `https://wa.me/${c.phone}?text=${message(safe, pos.coords.latitude, pos.coords.longitude)}`,
                "_blank",
              ),
            i * 300,
          ),
        );
      },
      () => {
        setStatus("Sem GPS — mensagem enviada sem localização.");
        contacts.forEach((c, i) =>
          window.setTimeout(
            () => window.open(`https://wa.me/${c.phone}?text=${message(safe)}`, "_blank"),
            i * 300,
          ),
        );
      },
      { enableHighAccuracy: true, timeout: 8000 },
    );
  }

  return (
    <section id="emergencia" className="section container emergency">
      <div className="section-intro">
        <p className="eyebrow">PROTEÇÃO PESSOAL</p>
        <h2>Emergência</h2>
        <p className="muted">
          Aviso imediato para quem você confia. Contatos ficam só no seu aparelho — nada vai para o
          servidor.
        </p>
      </div>

      <div className="emergency-grid">
        <div className="panic-card">
          <button className="panic-button" onClick={() => send(false)}>
            PÂNICO
          </button>
          <p className="muted">
            Envia sua localização para seus contatos via WhatsApp. Em risco imediato, ligue{" "}
            <a href="tel:190">190</a>.
          </p>
          {status && (
            <p className="emergency-status" role="status">
              {status}
            </p>
          )}
          <button className="button secondary" onClick={() => send(true)}>
            Avise que cheguei bem
          </button>
        </div>

        <div className="contacts-card">
          <h3>Rede de confiança</h3>
          <ul className="contact-list">
            {contacts.length === 0 && <li className="empty">Nenhum contato ainda.</li>}
            {contacts.map((c) => (
              <li key={c.phone}>
                <span>
                  {c.name} <small>· +{c.phone}</small>
                </span>
                <button
                  className="button ghost remove-contact"
                  onClick={() => save(contacts.filter((x) => x.phone !== c.phone))}
                >
                  remover
                </button>
              </li>
            ))}
          </ul>
          {contacts.length < MAX && (
            <div className="contact-form">
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Nome"
                size={4}
                aria-label="Nome do contato"
              />
              <input
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="(11) 99999-0000"
                inputMode="tel"
                size={8}
                aria-label="Telefone do contato"
              />
              <button className="button secondary" onClick={add} aria-label="Adicionar contato">
                +
              </button>
            </div>
          )}
          <p className="muted">Até {MAX} contatos · WhatsApp abre para você confirmar o envio.</p>
        </div>

        <div className="phones-card">
          <h3>Canais oficiais</h3>
          <div className="phone-grid">
            {PHONES.map((p) => (
              <a key={p.n} className="phone-card" href={`tel:${p.n}`}>
                <b>{p.n}</b>
                <span>{p.l}</span>
              </a>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
