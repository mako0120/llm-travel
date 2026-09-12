# MVP data contracts

All examples below are **synthetic**. `example.org` is placeholder provenance, not a fetched tourism source. Prices, travel durations and schedules are invented test data. Currency is an application convention (JPY in the current domestic prototype); there is no currency conversion.

## Plan input

`validate_plan(plan, now=None)` returns a list of `{code, path, message}` issues. Empty means supplied data passed these deterministic checks; it does not certify real-world feasibility. `now` defaults to current UTC and can be frozen to an aware datetime for evaluation. Input is not modified. Unknown extra fields are currently tolerated.

| Field | Contract |
| --- | --- |
| `start`, `end` | ISO datetime strings with an explicit timezone; end follows start |
| `budget` | Finite, nonnegative number; booleans rejected |
| `required_activity_ids` | Array of nonempty strings; every ID must occur in activities; empty array allowed |
| `activities` | Nonempty array of activity objects |
| `activities[].id` | Unique nonempty string |
| `activities[].start`, `.end` | Aware ISO datetimes, positive duration, inside plan bounds, ordered with no overlap |
| `activities[].cost` | Finite nonnegative number; summed costs cannot exceed budget |
| `activities[].transit_minutes` | Finite nonnegative number; required travel **before** this activity, fitting the gap from previous activity end or plan start |
| `activities[].source.url` | HTTP(S) URL with hostname; only URL syntax is checked |
| `activities[].source.expires_at` | Aware ISO datetime strictly after validation reference time |
| `activities[].source.verification_status` | Optional in ordinary validation; `verified` or `unverified`. Missing is unverified. `validate_trip_ready` requires `verified`. |

```json
{
  "start": "2026-09-13T09:00:00+09:00",
  "end": "2026-09-13T18:00:00+09:00",
  "budget": 5000,
  "required_activity_ids": ["synthetic-museum"],
  "activities": [{
    "id": "synthetic-museum",
    "start": "2026-09-13T10:00:00+09:00",
    "end": "2026-09-13T11:00:00+09:00",
    "cost": 1500,
    "transit_minutes": 60,
    "source": {
      "url": "https://example.org/synthetic-museum",
      "expires_at": "2026-09-14T00:00:00Z"
    }
  }]
}
```

The example passes at frozen `now=2026-09-12T00:00:00Z`; its provenance expires and is intentionally rejected after expiry. Storage `Repository.create_plan(plan)` adds `id` (UUID when omitted/empty) and an increasing `version`; supplied version is replaced. Reusing an ID creates a new immutable revision. Storage does **not** run domain validation itself: callers must validate before saving. Stored documents may include additional application metadata.

Current checks do not cover real opening hours, origin/destination coordinates, return travel, actual route availability, weather, currency consistency, reservations or independent source verification. `validate_trip_ready(plan, use_at)` rechecks expiry and requires explicitly verified evidence at presentation time; `verified` is a provider assertion that must eventually be backed by a source policy or retrieved snapshot.

## Feedback

`Repository.add_feedback(plan_id, version, ratings, comment)` requires an existing exact plan revision. `version` is a positive integer (not boolean). `ratings` is a nonempty object with nonempty string keys and integer values 1–5 (booleans rejected). `comment` is a string, including empty. Example method arguments:

```json
{
  "plan_id": "synthetic-plan",
  "version": 1,
  "ratings": {"satisfaction": 4, "travel_comfort": 3},
  "comment": "Synthetic observation: allow a longer break."
}
```

Returned feedback adds generated `id` and UTC `created_at`. Feedback is tied to the original revision even when later versions exist. Comments are data, never executable instructions.

`summarize_ratings(ratings)` accepts a list or tuple of finite numbers in [1,5], rejects booleans and invalid values with `ValueError`, and returns `count`, `mean`, `median`, `stdev` (population standard deviation). For an empty list the count is 0 and the three statistics are null. This analytics helper permits fractional scores; persisted feedback currently requires integer scores. Do not pool different rating dimensions without an explicitly justified analysis.

## Improvement rules

`Repository.propose_rule(condition, problem, improvement, evidence)` requires a nonempty object with nonempty string keys for `condition`, nonempty strings for `problem` and `improvement`, and truthy JSON-serializable `evidence`. Condition values must be JSON-serializable. Evidence structure and referenced feedback existence are **not yet enforced**. Recommended synthetic input:

```json
{
  "condition": {"region": "synthetic-region", "transport": "walk"},
  "problem": "Synthetic feedback reports insufficient rest.",
  "improvement": "Add a rest break after two visits.",
  "evidence": [{"feedback_id": "synthetic-feedback", "note": "Synthetic reference only"}]
}
```

The returned record adds generated `id`, `status: "pending"`, UTC `created_at`, and `approved_at: null`. `approve_rule(id)` changes status to `approved` and sets UTC `approved_at`. This is a local operator action; the repository does not authenticate a human approver. Applications must supply that boundary before shared deployment. There is no rejected/expired rule state yet.

`find_rules(metadata)` returns only approved rules whose every condition key exists in metadata with exactly matching Python type and value. Extra metadata keys are allowed; no fuzzy or semantic matching occurs. Evidence is retained as context, not treated as verified causality. Rule application is a caller responsibility.

## Fixed evaluation

Run `python -m evals.run`. `evals/datasets/validator.json` contains synthetic plans, a frozen reference time, and exact expected issue-code sets. The command exits 1 for any regression and prints JSON with `constraint_case_accuracy`, the proportion of cases with exact issue-code agreement. This metric measures this fixed constraint test suite only; it is not actual route/price accuracy, travel satisfaction, scientific validation, or production readiness.
