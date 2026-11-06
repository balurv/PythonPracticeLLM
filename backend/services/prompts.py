"""Agent capability catalog and the LLM prompts built from it.

To ship a new tool: add it to CAPABILITIES, the Mechanism literal (schemas/agent.py),
chat_service.chat(), and the frontend's constants/mechanisms.js.
"""

# Every tool an agent can be given. A capability not listed here gets a GitHub issue instead.
CAPABILITIES = {
    "rag": "search knowledge text the user pasted for this agent",
    "memory": "remember earlier messages in this conversation",
    "github": "GitHub: read the user's profile, list/read/create issues, comment, list pull requests, read repo files",
    "gmail": "Gmail, read-only: search the user's inbox and read emails (receipts, bookings...); cannot send or delete",
}
CATALOG = "\n".join(f"- {k}: {v}" for k, v in CAPABILITIES.items())

DECIDE = f"""You are an agent orchestrator. Given a user's agent request and up to 3 existing
agents (with similarity scores), decide whether an existing agent already fits the request.
Reuse only if its purpose and skills clearly match; otherwise create a new agent.

Agents are an LLM that can reason and write, plus only these tools:
{CATALOG}
If the request needs access to something none of these provide (e.g. reading an email inbox,
browsing the web, a calendar, a bank or payments API), list each missing tool in "missing_tools"
with a full specification for the dev team who will build it. Otherwise use [].
Always check this, for both reuse and create: reusing an agent does not give it new tools.

Reply with JSON only:
{{"action": "reuse", "agent_id": <id>, "reason": "<one sentence>", "missing_tools": [...]}}
or
{{"action": "create", "name": "<short agent name>", "system_prompt": "<instructions for the new
agent: role, skills, requirements, tone; 3-6 sentences>", "reason": "<one sentence>", "missing_tools": [...]}}

Each missing tool: {{"name": "<snake_case_tool_name>", "purpose": "<what it does and why the agent
needs it>", "inputs": ["<param: type, meaning>"], "output": "<what it returns>",
"acceptance_criteria": ["<testable criterion>"], "security_notes": ["<credentials, read-only, privacy>"]}}"""

NO_TOOL_RULE = """HARD RULE: you can only act through the tools listed under "Your tools".
If a request needs any other access (email, web, files, calendar, bank, APIs...), do NOT write code,
scripts, setup guides or API instructions for it, even if the user asks for code. Instead call the
`request_tool` function with a full specification: it files a GitHub issue in the project's own repo
(already configured, never ask the user for an owner or repository) so the dev team can build it.
Tool and capability requests must always go through `request_tool`, never through GitHub tools like
`issue_write` (those are only for the user's own GitHub tasks).
Then reply briefly that the capability isn't available yet and share the issue link it returns.
Always use "Your tools" first. If one of them returns an error, tell the user the error; don't file a
request for a tool you already have. If a capability is only listed under "Requested tools", share that link. You may still help with
any part that needs no new tool."""

REMINDER = (
    "Reminder: follow the HARD RULE. No code or how-to for capabilities outside your tools; "
    "use request_tool (never issue_write; repo is preconfigured) and share the issue link. "
    "If the capability is listed as built but not enabled, tell the user to enable it instead."
)

REQUEST_TOOL_SPEC = {
    "name": "request_tool",
    "description": "File a GitHub issue asking the dev team to build a tool this agent lacks. "
    "The repository is preconfigured. Always use this (not issue_write) for tool requests. "
    "Returns the issue link.",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "snake_case tool name, e.g. email_inbox_reader"},
            "purpose": {"type": "string", "description": "what it does and why the user needs it"},
            "inputs": {"type": "array", "items": {"type": "string"}, "description": "param: type, meaning"},
            "output": {"type": "string", "description": "what the tool returns"},
            "acceptance_criteria": {"type": "array", "items": {"type": "string"}},
            "security_notes": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["name", "purpose"],
    },
}
