import { useEffect, useState } from "react";
import { getAgentMessages, sendAgentMessage } from "../api/agents.js";
import { getGmailStatus } from "../api/gmail.js";
import Linkify from "./Linkify.jsx";

export default function AgentChat({ agent }) {
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [gmail, setGmail] = useState(null);
  const usesGmail = agent.mechanisms.includes("gmail");

  useEffect(() => {
    setError("");
    getAgentMessages(agent.id).then(setMessages).catch((e) => setError(e.message));
  }, [agent.id]);

  // Recheck when the tab regains focus, i.e. after the user comes back from Google's consent page.
  useEffect(() => {
    if (!usesGmail) return;
    const check = () => getGmailStatus().then(setGmail).catch(() => {});
    check();
    window.addEventListener("focus", check);
    return () => window.removeEventListener("focus", check);
  }, [usesGmail]);

  async function send(e) {
    e.preventDefault();
    const message = text.trim();
    if (!message) return;
    setText("");
    setError("");
    setMessages((m) => [...m, { role: "user", content: message }]);
    setBusy(true);
    try {
      const { reply } = await sendAgentMessage(agent.id, message);
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
      {gmail && !gmail.connected && (
        <p className="banner missing">
          This agent needs read-only access to your Gmail.{" "}
          <a href={gmail.connect_url} target="_blank" rel="noreferrer">Connect Gmail</a>
        </p>
      )}
      <div className="messages">
        {messages.length === 0 && <p className="hint">No messages yet.</p>}
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}><Linkify text={m.content} /></div>
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
