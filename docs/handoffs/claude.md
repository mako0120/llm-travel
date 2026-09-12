# Claude execution prompt — CL-001

Status: ready for pickup; not executed. Local Claude Code is currently unauthenticated.

## Role
Research-methodology and high-risk design reviewer for mako0120/llm-travel.

## Context
Read the master prompt in docs/master-prompt.md, architecture.md and backlog.md.
The current slice is an offline Python prototype using synthetic input, deterministic validation, SQLite persistence, feedback statistics and explicitly approved reusable rules.

## Goal
Review research claims, evidence requirements, rule generalization and validator limits. Identify acceptance criteria for the next implementation PR.

## Input
The pull request and its exact head commit, tests and eval output. No real participant dataset is available. Mark missing evidence explicitly.

## Constraints
Do not invent literature, user study results, source verification or a successful review. Distinguish design proposal, implemented behavior and verified behavior. Do not duplicate implementation.

## Expected output
Return JSON: {"task_id":"CL-001","reviewed_commit":"...","status":"changes_requested|reviewed","findings":[{"severity":"high|medium|low","file":"...","issue":"...","acceptance_criteria":"..."}],"research_hypotheses":[],"missing_inputs":[]}.
Save the review in a separate review branch and PR or post it on the associated GitHub issue. Never include participant data.

## Acceptance criteria
Address feedback-selection bias, correlated participants, held-out trips, unknown provenance, stale data, approval authority, and invalid numeric/time input. Make no claim of novelty without primary-source literature review.

## Do not do
Implement features, merge PRs, provision AWS, change secrets, deploy, or approve rules on behalf of a human.
