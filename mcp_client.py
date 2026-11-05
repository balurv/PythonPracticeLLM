"""MCP client: lets the Groq LLM use the GitHub MCP server's tools.

Usage: uv run python mcp_client.py "list open issues in balurv/PythonPracticeLLM"
Env: GROQ_API_KEY, GITHUB_PAT, optional GROQ_MODEL.
"""

import asyncio
import json
import os
import sys
from collections.abc import Callable

import groq
from dotenv import load_dotenv
from groq import Groq
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client

load_dotenv()
URL = "https://api.githubcopilot.com/mcp/"
MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
MAX_STEPS = 10
MAX_TOOL_CHARS = 4000  # trim big tool results (file contents, issue lists) to stay under Groq's TPM cap
# Groq's free tier allows ~8k tokens/min, so only expose a few tools to the LLM.
TOOLS = set(
    os.getenv(
        "MCP_TOOLS",
        "get_me,list_issues,issue_read,issue_write,add_issue_comment,"
        "list_pull_requests,get_file_contents",
    ).split(",")
)


LocalTools = dict[str, tuple[dict, Callable[..., str]]]  # name -> (function spec, python fn)


def _tool(spec: dict) -> dict:
    return {"type": "function", "function": spec}


BAD_JSON_RETRIES = 2
BAD_JSON_HINT = (
    "Your last tool call was rejected: its arguments were not valid JSON. Call the tool again "
    'using only straight ASCII double quotes (") for keys and strings, never curly quotes.'
)


def _complete(client: Groq, messages: list[dict], tools: list[dict]):
    """One Groq call; retry when the model emits malformed tool-call JSON (Groq's tool_use_failed)."""
    for attempt in range(BAD_JSON_RETRIES + 1):
        try:
            return client.chat.completions.create(model=MODEL, messages=messages, tools=tools).choices[0].message
        except groq.BadRequestError as e:
            if "tool_use_failed" not in str(e) or attempt == BAD_JSON_RETRIES:
                raise
            print("-> malformed tool call JSON, retrying", file=sys.stderr)
            messages = messages + [{"role": "system", "content": BAD_JSON_HINT}]


async def run(session: ClientSession | None, messages: list[dict], local_tools: LocalTools | None = None) -> str:
    """Groq tool loop over GitHub MCP tools (if `session`) plus local Python tools."""
    local_tools = local_tools or {}
    tools = [_tool(spec) for spec, _ in local_tools.values()]
    if session:
        tools += [
            _tool({"name": t.name, "description": t.description or "", "parameters": t.input_schema})
            for t in (await session.list_tools()).tools
            if t.name in TOOLS
        ]
    client = Groq(timeout=60)
    messages = list(messages)

    for _ in range(MAX_STEPS):
        msg = _complete(client, messages, tools)
        if not msg.tool_calls:
            return msg.content
        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ],
        })
        for tc in msg.tool_calls:
            name, args = tc.function.name, json.loads(tc.function.arguments or "{}")
            print(f"-> {name}({tc.function.arguments})", file=sys.stderr)
            if name in local_tools:
                text = local_tools[name][1](**args)
            elif session:
                result = await session.call_tool(name, args)
                text = "\n".join(c.text for c in result.content if c.type == "text")
            else:
                text = f"Unknown tool: {name}"
            if len(text) > MAX_TOOL_CHARS:
                text = text[:MAX_TOOL_CHARS] + "\n…(truncated)"
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": text})
    return f"Stopped after {MAX_STEPS} steps."


async def ask_with_tools(messages: list[dict], local_tools: LocalTools | None = None, github: bool = True) -> str:
    """Answer `messages` with local tools, plus GitHub MCP tools when `github` is on."""
    if not github:
        return await run(None, messages, local_tools)
    headers = {"Authorization": f"Bearer {os.environ['GITHUB_PAT']}"}
    async with (
        create_mcp_http_client(headers=headers) as http,
        streamable_http_client(URL, http_client=http) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        return await run(session, messages, local_tools)


if __name__ == "__main__":
    prompt = " ".join(sys.argv[1:]) or "Who am I on GitHub?"
    print(asyncio.run(ask_with_tools([{"role": "user", "content": prompt}])))
