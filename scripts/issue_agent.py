"""Minimal issue agent: asks Groq for the file edits that resolve a GitHub issue.

Env: GROQ_API_KEY, ISSUE_TITLE, ISSUE_BODY, optional GROQ_MODEL.
Writes the edited files into the repo and a summary (or a question) to RUNNER_TEMP.
"""

import json
import os
import subprocess
from pathlib import Path

from groq import Groq

ROOT = Path.cwd().resolve()
SKIP = {"uv.lock"}
PROTECTED = (".github/", ".git/", ".env")
MAX_BYTES = 20_000

SYSTEM = """You are a coding agent for a small Python repo.
Given the repo files and a GitHub issue, reply with JSON only, in this shape:
{"summary": "<short markdown summary of the change>",
 "files": [{"path": "<repo-relative path>", "content": "<complete new file content>"}]}
Include only files you create or change, each with its complete content.
Follow the conventions in CLAUDE.md. Keep the change minimal.
If the issue is too unclear to implement, reply {"question": "<what you need to know>"} instead."""


def repo_files() -> dict[str, str]:
    paths = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, check=True
    ).stdout.splitlines()
    files = {}
    for p in paths:
        path = ROOT / p
        if p in SKIP or p.startswith(PROTECTED) or path.stat().st_size > MAX_BYTES:
            continue
        try:
            files[p] = path.read_text()
        except UnicodeDecodeError:
            continue
    return files


def safe_path(p: str) -> Path:
    path = (ROOT / p).resolve()
    if not path.is_relative_to(ROOT) or p.startswith(PROTECTED):
        raise ValueError(f"Refusing to write {p}")
    return path


def main() -> None:
    files = repo_files()
    repo_dump = "\n\n".join(f"--- {p} ---\n{c}" for p, c in files.items())
    issue = f"# {os.environ['ISSUE_TITLE']}\n\n{os.environ.get('ISSUE_BODY', '')}"

    res = Groq().chat.completions.create(
        model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Repo files:\n\n{repo_dump}\n\nIssue:\n\n{issue}"},
        ],
        response_format={"type": "json_object"},
    )
    data = json.loads(res.choices[0].message.content)

    out = Path(os.getenv("RUNNER_TEMP", ".")) / "agent_summary.md"
    if data.get("question"):
        status = "question"
        out.write_text(data["question"])
    else:
        status = "changed"
        for f in data.get("files", []):
            path = safe_path(f["path"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f["content"])
            print(f"wrote {f['path']}")
        out.write_text(data.get("summary", ""))

    result = f"status={status}\nsummary_file={out}\n"
    if gh_out := os.getenv("GITHUB_OUTPUT"):
        with open(gh_out, "a") as fh:
            fh.write(result)
    print(result)


if __name__ == "__main__":
    main()
