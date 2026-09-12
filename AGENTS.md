# Development rules

- Work through an Issue and a codex/* branch, then PR and CI. Never push main directly.
- This is a local synthetic-data research prototype, not a production travel service.
- Keep calculations, validation, search and statistics deterministic. Never manufacture current travel facts.
- Claude owns research interpretation and high-risk review; Codex owns implementation and verification. Never claim an unexecuted Claude review.
- Runtime must never hold GitHub write or deploy credentials.
- No personal feedback, credentials or real participant data in this public repository.
- Run `python -m unittest discover -v` and `python -m evals.run` before a PR.
- No automatic merge or production deploy. High-risk changes require review, eval and human approval.
- Pending improvement proposals must not affect retrieval.
- Reusable improvement rules must cite qualitative free-text comments only. Ratings are descriptive monitoring context and must never by themselves trigger, approve, or rank a rule.
