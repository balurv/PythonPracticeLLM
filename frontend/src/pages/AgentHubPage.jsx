import { useEffect, useState } from "react";
import { listAgents } from "../api/agents.js";
import AgentChat from "../components/AgentChat.jsx";
import AgentForm from "../components/AgentForm.jsx";
import AgentList from "../components/AgentList.jsx";

// Agent hub: agent list (left), request form + chat with the selected agent (right).
export default function AgentHubPage() {
  const [agents, setAgents] = useState([]);
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState("");

  const load = () => listAgents().then(setAgents).catch((e) => setError(e.message));
  useEffect(() => { load(); }, []);

  return (
    <div className="layout">
      <AgentList agents={agents} selectedId={selected?.id} error={error} onSelect={setSelected} />
      <main>
        <AgentForm onDone={(agent) => { setSelected(agent); load(); }} />
        {selected && <AgentChat key={selected.id} agent={selected} />}
      </main>
    </div>
  );
}
