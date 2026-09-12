# Architecture decision record: initial research slice

Status: provisional development baseline authorized by the user's request to automate development. Production, research ethics and high-risk review remain separate gates.

## Objective and boundary
Close the loop from travel plan to actual feedback, deterministic analysis, proposed improvement and reuse. Keep system-code improvement in a separate GitHub control plane.
Current scope is local single-user synthetic-data validation and persistence. No network server, authentication claim, live routing, LLM calls, booking or safety guarantee.

## Runtime
CLI → domain validator → SQLite repository → version-linked feedback → statistics → pending rule → explicit operator approval → metadata matching.
The validator checks supplied evidence timestamps; it cannot establish that a URL's contents are true. Provider contracts distinguish `unconfigured`, `unavailable`, `invalid`, and `available`; a trip-ready validation requires explicitly verified and non-expired evidence at time of use. Fixture providers never fetch URLs. The bounded deterministic optimizer only selects candidates with supplied verified fixture evidence and never relaxes hard constraints.

## Target
Modular Python backend with provider adapters; PostgreSQL for multi-user persistence; independent optimizer and validator; web UI after API contracts. SQL retrieval precedes any vector index. Solver receives verified travel-time matrices and hard constraints; infeasibility is returned explicitly.
AWS Lambda versus Fargate and RDS versus alternatives remain benchmark/cost decisions. No resources are provisioned. GitHub Actions deployment will use environment-scoped OIDC roles.

## Data
Plan revisions are immutable. Feedback references a plan and revision. Rules have conditions, problem, improvement, evidence and approval status. Current SQLite storage is a local prototype, not the final PostgreSQL migration or retention system.
Future provenance includes code/prompt/model/dataset/retrieval/optimizer versions, source snapshots, trace ID and per-trip cost. PII stays outside GitHub; retention and research consent must be resolved before real data.

## Control plane
Issue → codex/* branch → PR → CI and fixed eval → Claude high-risk review → human approval → merge → staging → production gate.
Bootstrap exception: empty commit on codex/bootstrap establishes a PR base without pushing main. Default branch can be renamed to main after bootstrap review; normal changes remain PR-only.
Feedback text is untrusted data and cannot grant development or deployment permissions.

## Failure and cost
Malformed or stale plans are rejected by the CLI save path. Missing external integrations remain unconfigured. No fabricated fallback. Local prototype makes zero paid API calls. Production budgeting must account for fixed hosting/database costs, per-trip provider costs and log retention.

## Gates still open
Research population, consent/retention, region/transport, budget cap, provider licensing, source verification, authorization, full JSON contracts, optimizer evaluation, Claude review and production approval.
