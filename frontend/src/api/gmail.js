import { api } from "./client.js";

// { connected, connect_url }
export const getGmailStatus = () => api("/gmail/status");
