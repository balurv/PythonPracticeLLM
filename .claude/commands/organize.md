---
description: Audit and reorganize project files into the backend/frontend layer layout (uses the project-organizer agent)
argument-hint: [audit]
---

Use the `project-organizer` subagent to organize this repository. Arguments: $ARGUMENTS

If the arguments contain "audit", ask it to report misplaced files and layer violations only, without moving anything. Otherwise let it audit, move, fix references and verify. Relay its table of moves and its verification results to me.
