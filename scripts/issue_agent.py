"""Minimal issue agent: asks Groq for the file edits that resolve a GitHub issue.

Env: GROQ_API_KEY, ISSUE_TITLE, ISSUE_BODY, optional GROQ_MODEL.
Writes the edited files into the repo and a summary (or a question) to RUNNER_TEMP.

Files come back as plain-text blocks, not JSON: models often break JSON
escaping when a string holds a whole code file.

Groq's free tier allows ~8k tokens/min, so the repo isn't sent whole: a small
first call picks the files the issue needs (from CLAUDE.md and the file list),
then the coding call gets only those, within FILE_BUDGET.
"""

import os
import re
import subprocess
from pathlib import Path

from groq import Groq

ROOT = Path.cwd().resolve()
SKIP = {"uv.lock", ".mcp.json"}
# Never sent to the model or written by it. .claude/ and scripts/ are skipped to
# keep the prompt small enough for Groq's free tier (~8k tokens/min).
PROTECTED = (".github/", ".git/", ".claude/", "scripts/")
ENV_TEMPLATE = ".env.example"  # the only env file the agent may read or edit (no secrets in it)
MAX_BYTES = 20_000
FILE_BUDGET = 18_000  # chars of file content in the coding call (~4.5k tokens)
ALWAYS = ("CLAUDE.md",)  # conventions + architecture map, always sent
FILE_RE = re.compile(r"<<<FILE (.+?)>>>\n(.*?)\n?<<<END>>>", re.DOTALL)
EDIT_RE = re.compile(r"<<<EDIT (.+?)>>>\n<<<OLD>>>\n(.*?)\n<<<NEW>>>\n(.*?)\n?<<<END>>>", re.DOTALL)

SYSTEM = """You are a coding agent for a small Python repo.
Given the repo files and a GitHub issue, reply in exactly this format:

SUMMARY:
<short markdown summary of the change>

To CREATE a new file, give its complete content:
<<<FILE path/relative/to/repo.py>>>
<complete file content>
<<<END>>>

To CHANGE an existing file, never rewrite it; give a find-and-replace edit:
<<<EDIT path/relative/to/repo.py>>>
<<<OLD>>>
<exact lines copied from the current file, enough to be unique>
<<<NEW>>>
<replacement lines>
<<<END>>>

Use as many blocks as needed. Do not use code fences.
Follow the conventions in CLAUDE.md. Keep the change minimal.
If the issue is too unclear to implement, reply with only: QUESTION: <what you need to know>"""


def is_protected(p: str) -> bool:
    name = Path(p).name
    is_secret_env = (name == ".env" or name.startswith(".env.")) and name != ENV_TEMPLATE
    return p.startswith(PROTECTED) or is_secret_env


def repo_files() -> dict[str, str]:
    paths = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, check=True
    ).stdout.splitlines()
    files = {}
    for p in paths:
        path = ROOT / p
        if p in SKIP or is_protected(p) or path.stat().st_size > MAX_BYTES:
            continue
        try:
            files[p] = path.read_text()
        except UnicodeDecodeError:
            continue
    return files


PICK = """You plan a code change for a small Python repo. Given CLAUDE.md, the list of repo
files with sizes, and a GitHub issue, list the existing files a developer must read or edit
to resolve the issue, most important first. Reply with only the paths, one per line.
Only list files from the list. Leave out files that aren't needed."""


def groq() -> Groq:
    # Extra retries: the SDK waits out 429s, e.g. when the pick call used part of this minute's tokens.
    return Groq(max_retries=5)


def complete(system: str, user: str) -> str:
    res = groq().chat.completions.create(
        model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        reasoning_effort="low",
    )
    return res.choices[0].message.content or ""


def pick_files(files: dict[str, str], issue: str) -> tuple[dict[str, str], list[str]]:
    """Ask the model which files matter, then keep them in order within FILE_BUDGET."""
    listing = "\n".join(f"- {p} (~{len(c) // 4} tokens)" for p, c in files.items())
    claude_md = files.get("CLAUDE.md", "")
    reply = complete(PICK, f"CLAUDE.md:\n{claude_md}\n\nRepo files:\n{listing}\n\nIssue:\n{issue}")
    wanted = [*ALWAYS, *(line.strip().lstrip("-* `").rstrip("`") for line in reply.splitlines())]

    chosen, skipped, used = {}, [], 0
    for p in dict.fromkeys(wanted):  # dedupe, keep order
        if p not in files or p in chosen:
            continue
        if used + len(files[p]) > FILE_BUDGET:
            skipped.append(p)
            continue
        chosen[p] = files[p]
        used += len(files[p])
    print(f"files sent: {', '.join(chosen)}" + (f"; too big to fit: {', '.join(skipped)}" if skipped else ""))
    return chosen, skipped


def safe_path(p: str) -> Path:
    path = (ROOT / p).resolve()
    if not path.is_relative_to(ROOT) or is_protected(p):
        raise ValueError(f"Refusing to write {p}")
    return path


def main() -> None:
    files = repo_files()
    issue = f"# {os.environ['ISSUE_TITLE']}\n\n{os.environ.get('ISSUE_BODY', '')}"
    chosen, skipped = pick_files(files, issue)

    repo_dump = "\n\n".join(f"<<<FILE {p}>>>\n{c}\n<<<END>>>" for p, c in chosen.items())
    others = [p for p in files if p not in chosen]
    note = f"\n\nOther existing files (not shown, do not edit or recreate them): {', '.join(others)}"
    if skipped:
        note += f"\nNeeded but too large to show: {', '.join(skipped)}. Prefer new files over editing these."
    reply = complete(SYSTEM, f"Repo files:\n\n{repo_dump}{note}\n\nIssue:\n\n{issue}")

    out = Path(os.getenv("RUNNER_TEMP", ".")) / "agent_summary.md"
    new_files = FILE_RE.findall(reply)
    edits = EDIT_RE.findall(reply)
    if not new_files and not edits:
        status = "question"
        out.write_text(reply.removeprefix("QUESTION:").strip() or "The agent returned no changes.")
    else:
        status = "changed"
        for p, content in new_files:
            path = safe_path(p.strip())
            if path.exists():
                raise ValueError(f"{p} already exists; the model must use an EDIT block")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content.rstrip("\n") + "\n")
            print(f"created {p.strip()}")
        for p, old, new in edits:
            path = safe_path(p.strip())
            text = path.read_text()
            if text.count(old) != 1:
                raise ValueError(f"Edit for {p} does not match exactly one place:\n{old}")
            path.write_text(text.replace(old, new, 1))
            print(f"edited {p.strip()}")
        summary = re.split(r"<<<(?:FILE|EDIT) ", reply, maxsplit=1)[0]
        out.write_text(summary.replace("SUMMARY:", "", 1).strip())

    result = f"status={status}\nsummary_file={out}\n"
    if gh_out := os.getenv("GITHUB_OUTPUT"):
        with open(gh_out, "a") as fh:
            fh.write(result)
    print(result)


if __name__ == "__main__":
    main()
