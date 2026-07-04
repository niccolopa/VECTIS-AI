## graphify (optional tooling)

This project ships a pre-generated knowledge graph under `graphify-out/` (god nodes, community structure, cross-file relationships). It is a **convenience, not a requirement** — the codebase is fully navigable without it.

- If the `graphify` CLI happens to be on your PATH, you may use it to orient quickly: `graphify query "<question>"`, `graphify path "<A>" "<B>"`, `graphify explain "<concept>"`. `graphify-out/wiki/index.md` and `graphify-out/GRAPH_REPORT.md` are plain files you can read directly for navigation.
- If `graphify` is **not** installed, ignore it and use normal code search (ripgrep/grep, file reads). **Do not install it or spend time troubleshooting its absence** — chasing a missing graphify has stalled sessions in this repo before. The graph files are static docs; a stale graph is harmless.
- After changing code, `graphify update .` refreshes the graph *if* you have the CLI. Skip it otherwise.
