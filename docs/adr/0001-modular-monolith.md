# ADR 0001: Modular monolith control plane

**Accepted.** Use one FastAPI deployment with strict modules and a separate worker. This minimizes distributed failure modes while preserving a future extraction boundary. Split a module only when workload, team ownership or security requires it.
