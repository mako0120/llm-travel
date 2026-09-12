# Requirements and acceptance baseline

## Functional
- FR-01: structured trip conditions, mandatory activities and explicit unknowns.
- FR-02: source provenance, retrieval time, expiry and verification status; never infer factual verification from URL syntax.
- FR-03: bounded itinerary optimization with travel times and independent hard-constraint validation.
- FR-04: immutable plan revisions and exact-revision feedback.
- FR-05: descriptive statistics calculated without an LLM.
- FR-06: proposed improvement rules with evidence, explicit approval and applicability conditions.
- FR-07: retrieve relevant approved knowledge, then record which rules affected a new plan.
- FR-08: turn reviewed system improvements into issues; no runtime access to code/deployment credentials.

The first PR implements only portions of FR-02 and FR-04 through FR-06 plus basic validation. FR-01/03/07/08 end-to-end flows are outstanding.

## Nonfunctional and research
- Reject malformed/timezone-ambiguous/nonfinite inputs; persist data across restarts.
- Fixed synthetic evaluation is reproducible on Python 3.12 and 3.13. It does not estimate field effectiveness.
- Separate trips and participants when constructing held-out research evaluations.
- Record missing responses and sample counts; descriptive means are not causal effects or confidence estimates.
- Define operational latency, concurrency, availability and cost budgets before staging; no fabricated SLO is claimed.
- Future plan traces record code, model, prompt, source, dataset and rule versions.

## Security and release
- Current usage is a local single-user CLI with synthetic data only.
- Before real-data/multi-user use: authentication, per-trip authorization, participant consent, retention/deletion, encryption, audit and abuse limits.
- Never store real participant records or secrets in the public repository.
- No booking, purchase, production deploy or automatic merge in the initial slice.

## Verification boundaries
Unit tests cover structural constraints and persistence invariants. CLI tests cover the local workflow. Fixed eval tests supplied fixture consistency only. Live opening-hour accuracy, routing feasibility, price accuracy and research benefit remain unmeasured.
