# Development status

- EP-001: https://github.com/mako0120/llm-travel/issues/1
- CL-001: https://github.com/mako0120/llm-travel/issues/2
- CX-001: https://github.com/mako0120/llm-travel/issues/3

Initial implementation lives on `codex/mvp-foundation`; PR base is `codex/bootstrap`.
Claude must fetch that implementation branch or PR; the bootstrap branch intentionally contains only an empty root commit.

## Ready
Design baseline, master prompt, owner queue and copyable handoff are versioned together with code. CI runs unit/integration tests and fixed synthetic regression eval.

## Not complete
Claude authentication and review, live information providers, actual itinerary generation/optimization, Web UI, multi-user authentication, AWS deployment and full research evaluation.
No unattended Claude runner is configured. Saving this handoff does not automatically launch Claude. Once an authenticated Claude environment picks up issue #2, it should review the PR head and return findings there.

## Next executable work
Resolve CL-001 review against the exact head, then CX-002 using the prompt in backlog.md. Keep each change on its own issue/branch/PR. Do not automatically approve a rule, merge or deploy.
