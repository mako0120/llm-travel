# Epic and task queue

GitHub issues are the operational queue. This file records scope and owner boundaries.

| ID | Owner | Priority | Dependency | Objective / output | Acceptance / test | Risk | Effort |
|---|---|---|---|---|---|---|---|
| EP-001 | ChatGPT | P0 | none | Research foundation and deterministic vertical slice | Reproducible CI and documented limits | medium | 2 days |
| CX-001 | Codex | P0 | EP-001 | Validator, SQLite, feedback statistics, approved-rule lookup, CLI | Unit and fixed regression eval pass | high | 1 day |
| CL-001 | Claude | P0 | CX-001 | Research and high-risk review of exact PR commit | Structured findings and acceptance criteria | high | 1 day |
| HU-001 | Human | P0 | CL-001 | Select region, transport, budget and consent policy | Recorded decisions before real-data use | high | 0.5 day |
| CX-002 | Codex | P1 | CL-001 | Provider contracts and optimizer with fixture travel matrix | Infeasible input and timeout tests; no invented routes | high | 2 days |
| CX-003 | Codex | P1 | CX-002, HU-001 | Authenticated API and web flow | Ownership, E2E and accessibility checks | high | 3 days |
| CX-004 | Codex | P2 | CX-003 | AWS cost comparison and staging IaC | Cost ceiling, OIDC and rollback reviewed | high | 2 days |

## Codex next-task prompt
Repository: mako0120/llm-travel. Issue: CX-002 (create/link before changes).
Objective: implement provider-neutral source and route contracts and a bounded deterministic optimizer using only explicitly marked fixtures until a provider is configured.
Input: approved CL-001 findings, architecture decisions and current domain interfaces.
Files/components: travel/providers, travel/optimizer, tests, evals.
Architecture rules: no provider SDK in domain, no LLM numeric calculation, no relaxing hard constraints silently.
Implementation requirements: output selected activities and versioned provenance; explicit infeasible/unconfigured/timeout states.
Tests: independent validator accepts successful results, impossible budget/time rejected, stale data excluded, solver timeout bounded.
Security: no arbitrary URL fetching, no credentials committed, no real participant fixtures.
Definition of done: tests and eval pass; limits and benchmarks recorded; Claude review requested.
PR requirements: linked issue, exact validation results, risk and rollback; no direct main push or automatic merge.
