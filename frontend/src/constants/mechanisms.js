// Agent tools the user can tick. Keep in sync with the backend's Mechanism literal
// (backend/schemas/agent.py) and CAPABILITIES (backend/services/prompts.py).
export const MECHANISMS = [
  { id: "rag", label: "RAG knowledge (Qdrant)" },
  { id: "memory", label: "Conversation memory (MySQL)" },
  { id: "github", label: "GitHub tools (MCP)" },
  { id: "gmail", label: "Gmail inbox, read-only" },
];
