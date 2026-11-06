import { api } from "./client.js";

// POST /orchestrate: reuse a matching agent or create a new one.
export const orchestrateAgent = (request) => api("/orchestrate", request);

export const listAgents = () => api("/agents");

export const getAgentMessages = (agentId) => api(`/agents/${agentId}/messages`);

// POST /ask with agent_id: chat with one agent. Resolves to { reply }.
export const sendAgentMessage = (agentId, message) => api("/ask", { message, agent_id: agentId });
