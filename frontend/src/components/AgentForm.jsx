import { useState } from "react";
import { orchestrateAgent } from "../api/agents.js";
import { MECHANISMS } from "../constants/mechanisms.js";

export default function AgentForm({ onDone }) {
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
      const data = await orchestrateAgent({
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
