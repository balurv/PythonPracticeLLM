export default function AgentList({ agents, selectedId, error, onSelect }) {
  return (
    <aside className="card">
      <h2>Agents</h2>
      {error && <p className="error">{error}</p>}
      {agents.length === 0 && !error && <p className="hint">None yet.</p>}
      <ul>
        {agents.map((a) => (
          <li key={a.id}>
            <button className={selectedId === a.id ? "active" : ""} onClick={() => onSelect(a)}>
              {a.name}
            </button>
          </li>
        ))}
      </ul>
    </aside>
  );
}
