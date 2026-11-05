"""MCP client: lets the Groq LLM use the GitHub MCP server's tools.

Usage: uv run python mcp_client.py "list open issues in balurv/PythonPracticeLLM"
Env: GROQ_API_KEY, GITHUB_PAT, optional GROQ_MODEL.
"""

import asyncio
import json
import os
import sys

from dotenv import load_dotenv
from groq import Groq
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client

load_dotenv()
URL = "https://api.githubcopilot.com/mcp/"
MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
MAX_STEPS = 10
# Groq's free tier allows ~8k tokens/min, so only expose a few tools to the LLM.
TOOLS = set(
    os.getenv(
        "MCP_TOOLS",
        "get_me,list_issues,issue_read,issue_write,add_issue_comment,"
        "list_pull_requests,get_file_contents",
    ).split(",")
)


async def run(session: ClientSession, prompt: str) -> str:
    tools = [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description or "",
                "parameters": t.input_schema,
            },
        }
        for t in (await session.list_tools()).tools
        if t.name in TOOLS
    ]
    client = Groq()
    messages = [{"role": "user", "content": prompt}]

    for _ in range(MAX_STEPS):
        msg = client.chat.completions.create(
            model=MODEL, messages=messages, tools=tools
        ).choices[0].message
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
            print(f"-> {tc.function.name}({tc.function.arguments})", file=sys.stderr)
            result = await session.call_tool(
                tc.function.name, json.loads(tc.function.arguments or "{}")
            )
            text = "\n".join(c.text for c in result.content if c.type == "text")
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": text})
    return f"Stopped after {MAX_STEPS} steps."


async def main(prompt: str) -> None:
    headers = {"Authorization": f"Bearer {os.environ['GITHUB_PAT']}"}
    async with (
        create_mcp_http_client(headers=headers) as http,
        streamable_http_client(URL, http_client=http) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        print(await run(session, prompt))


if __name__ == "__main__":
    asyncio.run(main(" ".join(sys.argv[1:]) or "Who am I on GitHub?"))
