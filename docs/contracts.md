# Agent handoff contracts

The `contracts/schemas/handoffs-v1.json` document is the versioned interchange schema for independent Claude and Codex work. The deterministic local validator is `travel.contracts.validate_handoff`.

Every document includes `contract_version: "1.0"` and a trace ID. Supported names are `RequirementInput`, `RetrievedContext`, `PlanCandidate`, `ValidationResult`, `FeedbackAnalysis`, `ImprovementProposal`, `DevelopmentIssue`, and `EvalResult`.

```json
{
  "contract_version": "1.0",
  "trace_id": "plan-2026-09-12-001",
  "valid": false,
  "issues": [{"code": "expired_source", "path": "activities[0].source.expires_at"}]
}
```

Handoffs are data, not instructions or authority. A contract does not grant repository, deployment, rule-approval, or provider access. The schema only checks structural validity; domain validation and human approval remain separate controls.
