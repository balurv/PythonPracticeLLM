---
paths:
  - "frontend/**"
---

# Frontend conventions (Vite + React, plain JS)
- `src/api/`: every backend call lives here. `client.js` has the `api()` fetch wrapper (prefix `/api`, proxied to :8000); one file per backend area (`agents.js`, `gmail.js`). Components never call `fetch` or `api()` directly.
- `src/pages/`: one component per screen; owns page-level state and composes components.
- `src/components/`: reusable UI pieces; get data and callbacks through props or the `api/` functions.
- `src/constants/`: static lists shared across components (e.g. `mechanisms.js`, kept in sync with the backend's `Mechanism`).
- `src/styles/`: CSS.
- File names: components and pages in PascalCase `.jsx`; everything else camelCase `.js`.
