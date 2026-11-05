---
description: Switch to the main branch and pull the latest code
allowed-tools: Bash(git status:*), Bash(git checkout main), Bash(git pull:*), Bash(git log:*)
---

Switch to `main` and pull the latest code from `origin`:

1. Run `git status --short`. If there are uncommitted changes, stop and ask me whether to commit, stash, or discard them. Never discard them yourself.
2. Run `git checkout main`.
3. Run `git pull origin main`.
4. Show the result with `git log --oneline -3`.
