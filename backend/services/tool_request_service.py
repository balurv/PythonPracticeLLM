"""Missing tools: file (or find) a GitHub issue per tool and link it to the agent."""

from backend.integrations import github_issues
from backend.repositories import agent_repository


def request_missing_tools(agent: dict, tools: list[dict]) -> list[dict]:
    filed = []
    for tool in tools:
        if not isinstance(tool, dict) or not tool.get("name"):
            continue
        try:
            issue = github_issues.request_tool(tool, agent)
        except Exception as e:  # no token, no permission, GitHub down: report, don't fail the request
            filed.append({"name": tool["name"], "error": f"Could not file issue: {e}"})
            continue
        agent_repository.add_tool_request(agent["id"], tool["name"], issue["number"], issue["url"])
        filed.append({"name": tool["name"], **issue})
    return filed
