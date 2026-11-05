import { useEffect, useState } from "react";

const MECHANISMS = [
  { id: "rag", label: "RAG knowledge (Qdrant)" },
  { id: "memory", label: "Conversation memory (MySQL)" },
  { id: "github", label: "GitHub tools (MCP)" },
];

async function api(path, body) {
  const res = await fetch(`/api${path}`, {
    method: body ? "POST" : "GET",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : `Request failed (${res.status})`);
  return data;
}

function AgentForm({ onDone }) {
  const empty = { name: "", requirements: "", skills: "", knowledge: "", mechanisms: [] };
  const [form, setForm] = useState(empty);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const toggle = (id) =>
    setForm({
      ...form,
      mechanisms: form.mechanisms.includes(id)
        ? form.mechanisms.filter((m) => m !== id)
        : [...form.mechanisms, id],
    });

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setResult(null);
    try {
      const data = await api("/orchestrate", {
        name: form.name || null,
        requirements: form.requirements,
        skills: form.skills.split(",").map((s) => s.trim()).filter(Boolean),
        knowledge: form.knowledge || null,
        mechanisms: form.mechanisms,
      });
      setResult(data);
      setForm(empty);
      onDone(data.agent);
    } catch (err) {
      setResult({ error: err.message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="card" onSubmit={submit}>
      <h2>Describe an agent</h2>
      <p className="hint">The orchestrator reuses a matching agent or creates a new one.</p>
      <input placeholder="Name (optional)" value={form.name} onChange={set("name")} />
      <textarea
        required
        rows={3}
        placeholder="Requirements: what should this agent do?"
        value={form.requirements}
        onChange={set("requirements")}
      />
      <input placeholder="Skills, comma-separated (e.g. python, fastapi)" value={form.skills} onChange={set("skills")} />
      <textarea
        rows={3}
        placeholder="Knowledge (optional): facts or docs the agent should know"
        value={form.knowledge}
        onChange={set("knowledge")}
      />
      <fieldset>
        <legend>Mechanisms</legend>
        {MECHANISMS.map((m) => (
          <label key={m.id}>
            <input type="checkbox" checked={form.mechanisms.includes(m.id)} onChange={() => toggle(m.id)} />
            {m.label}
          </label>
        ))}
      </fieldset>
      <button disabled={busy}>{busy ? "Thinking…" : "Find or create agent"}</button>
      {result?.error && <p className="error">{result.error}</p>}
      {result?.agent && (
        <p className={`banner ${result.action}`}>
          <strong>{result.action === "reuse" ? "Reused" : "Created"} “{result.agent.name}”</strong>
          {result.reason && ` — ${result.reason}`}
          {result.knowledge_chunks > 0 && ` (${result.knowledge_chunks} knowledge chunk(s) added)`}
        </p>
      )}
      {result?.tool_requests?.length > 0 && (
        <div className="banner missing">
          <strong>Missing tools: filed for the dev team</strong>
          <ul>
            {result.tool_requests.map((t) => (
              <li key={t.name}>
                <code>{t.name}</code>{" "}
                {t.url ? (
                  <a href={t.url} target="_blank" rel="noreferrer">
                    issue #{t.number}{t.created ? "" : " (already open)"}
                  </a>
                ) : (
                  <span className="error">{t.error}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </form>
  );
}

function Chat({ agent }) {
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setError("");
    api(`/agents/${agent.id}/messages`).then(setMessages).catch((e) => setError(e.message));
  }, [agent.id]);

  async function send(e) {
    e.preventDefault();
    const message = text.trim();
    if (!message) return;
    setText("");
    setError("");
    setMessages((m) => [...m, { role: "user", content: message }]);
    setBusy(true);
    try {
      const { reply } = await api("/ask", { message, agent_id: agent.id });
      setMessages((m) => [...m, { role: "assistant", content: reply }]);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card chat">
      <h2>{agent.name}</h2>
      <p className="hint">
        {agent.mechanisms.length ? agent.mechanisms.join(" · ") : "no mechanisms"}
        {agent.skills.length > 0 && ` | skills: ${agent.skills.join(", ")}`}
      </p>
      {agent.tool_requests?.length > 0 && (
        <p className="hint">
          Tools requested, not available yet:{" "}
          {agent.tool_requests.map((t, i) => (
            <span key={t.issue_number}>
              {i > 0 && ", "}
              <a href={t.issue_url} target="_blank" rel="noreferrer">{t.name} (#{t.issue_number})</a>
            </span>
          ))}
        </p>
      )}
      <div className="messages">
        {messages.length === 0 && <p className="hint">No messages yet.</p>}
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>{m.content}</div>
        ))}
        {busy && <div className="msg assistant">…</div>}
      </div>
      {error && <p className="error">{error}</p>}
      <form className="send" onSubmit={send}>
        <input placeholder="Message this agent" value={text} onChange={(e) => setText(e.target.value)} />
        <button disabled={busy}>Send</button>
      </form>
    </section>
  );
}

export default function App() {
  const [agents, setAgents] = useState([]);
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState("");

  const load = () => api("/agents").then(setAgents).catch((e) => setError(e.message));
  useEffect(() => { load(); }, []);

  return (
    <div className="layout">
      <aside className="card">
        <h2>Agents</h2>
        {error && <p className="error">{error}</p>}
        {agents.length === 0 && !error && <p className="hint">None yet.</p>}
        <ul>
          {agents.map((a) => (
            <li key={a.id}>
              <button className={selected?.id === a.id ? "active" : ""} onClick={() => setSelected(a)}>
                {a.name}
              </button>
            </li>
          ))}
        </ul>
      </aside>
      <main>
        <AgentForm onDone={(agent) => { setSelected(agent); load(); }} />
        {selected && <Chat key={selected.id} agent={selected} />}
      </main>
    </div>
  );
}
