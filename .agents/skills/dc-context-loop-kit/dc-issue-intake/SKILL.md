---
name: dc-issue-intake
description: Use this skill whenever an agent needs to resolve a Multica issue URL, issue UUID, or issue key into live issue context before analysis or execution. This skill handles input parsing, CLI/config checks, complete paginated issue/comment fetching, attachment discovery, and producing a concise issue context package. It is useful both inside d-flow and when the user asks to "只读取/分析这个 issue", "获取 issue 上下文", or "先看看这个 Multica 任务".
---

# Multica Issue Intake

## Trigger Report

When this skill is triggered, first run the trigger script and wait for it to finish. Do not assume the current working directory. Resolve the real path from this skill package first:

1. Use `scripts/skill-trigger-webhook.js` from this skill package.
2. If no reporting script can be located, record the diagnostic and continue the intake workflow.

Use `dc-issue-intake` as the reported skill name:

```bash
node <resolved-script-path> dc-issue-intake
```

Print both success and failure logs. Continue the intake workflow even if reporting fails after the retry rules below.

If logs show `EACCES`, `EPERM`, or `fetch failed`, treat it as network permission or connectivity trouble. Before continuing the intake workflow, tell the user that reporting failed because network access appears restricted, explicitly request escalated network execution permission, and retry the same reporting command once with that permission. Do not silently swallow the failure or continue as if reporting succeeded. If the escalated retry is denied or still fails, record that result and continue the intake workflow because reporting failure must not block live issue fetching.

## Goal

Resolve one Multica issue reference, fetch the live issue context and complete comment timeline, and return a concise context package plus complete-comment coverage information for downstream skills or normal agent work.

The issue is the source of truth. Do not rely only on pasted text when the `multica` CLI can fetch live data.

## Inputs

Accept any of these forms:

- Full web URL: `http://10.1.60.43:3000/ht1-ws/issues/9b000092-8ed9-4047-9564-7f8301c4626e`
- Issue UUID: `9b000092-8ed9-4047-9564-7f8301c4626e`
- Issue key: `MUL-123`, `HT1-42`
- A sentence that contains one of the above

Use the bundled parser:

```bash
python3 <skill-dir>/scripts/parse_issue_input.py "<user input>"
```

The script prints JSON with `issue_ref`, `workspace_slug`, and `url` fields.

## CLI Prerequisites

Use the `multica` CLI for platform data:

```bash
multica config show
multica auth whoami
```

Reporting failures do not block intake. CLI configuration failures do block intake because the live issue cannot be fetched reliably. If the CLI is not configured, stop and report the missing setup instead of guessing:

- `server_url`: set with `multica config set server_url <api-url>` or pass `--server-url`.
- `workspace_id`: set with `multica config set workspace_id <workspace-id>` or pass `--workspace-id`.
- Auth token: run `multica login`.

If the user pasted a frontend URL, do not assume the API URL is the same host/port. Check local config first. If the issue cannot be fetched, report the exact failing command and error.

## Workflow

1. Parse the input.
2. Fetch the issue:

   ```bash
   multica issue get <issue_ref> --output json
   ```

3. Fetch the complete discussion history, not only the most recent threads. The `multica` comment API paginates older active threads with a paired RFC3339 timestamp cursor and root UUID cursor. Start with a bounded page size, read the `X-Multica-Next-Before` and `X-Multica-Next-Before-Id` response headers, and keep requesting older pages with both `--before` and `--before-id` until the next-cursor headers are absent. Do not treat a page returning fewer than the requested number of comments as proof that history is exhausted.

   ```bash
   multica issue comment list <issue_ref> --recent 100 --output json
   multica issue comment list <issue_ref> --recent 100 \
     --before <next-before> --before-id <next-before-id> --output json
   ```

   Preserve every returned comment, including thread replies, and deduplicate by comment UUID. Keep this complete collection available to downstream skills; the human-readable context summary may remain concise. The intake is complete only when the final page has no next cursor. If a request fails or returns an unusable cursor, report `coverage: INCOMPLETE` and do not claim that the full timeline was read.

4. Inspect the issue and comments for attachment references. If attachments are required for understanding the issue, list or download them with available Multica attachment commands or the platform tools available in the current environment.
5. Produce an internal issue context package using the Output Contract below.

## Output Contract

Return or hand off a concise issue context package. Do not execute code changes, set status, or post comments from this skill.

Use this structure for downstream handoff:

```md
## Issue Context Package

- Issue: <issue key/id and title>
- Workspace/Project: <workspace or project when available, or "Unknown">
- Status: <current status or "Unknown">
- Priority: <priority or "Unknown">
- Assignee: <assignee or "Unassigned">
- Labels: <labels or "None">

## Request / Acceptance

- User-visible Request: <what the issue asks for>
- Acceptance Criteria: <explicit criteria, inferred criteria, or "Not specified">
- Actionability: <actionable / read-only / blocked / needs clarification>

## Source Material

- Description Summary: <concise summary of the issue description>
- Discussion Summary: <relevant summary of the complete comment timeline, or "None">
- Attachments: <attachment names and whether downloaded, or "None">
- Linked Documents: <URLs, local design docs, referenced docs, or "None">
- Referenced Design Docs: <design document names/paths if already present in issue/comments, or "None">

## Constraints / Dependencies

- Constraints: <technical/product/process constraints, or "None">
- Dependencies: <linked issues, external systems, approvals, or "None">
- Blockers: <blockers, or "None">

## Intake Notes

- Commands Used:
  - `multica issue get <issue_ref> --output json`
  - `multica issue comment list <issue_ref> --recent 100 --output json` (repeat with `--before` and `--before-id` until pagination is exhausted)
- Coverage: `<FULL / INCOMPLETE>`
- Pages Read: `<number>`
- Comments Fetched: `<number>`
- First Comment: `<id and created_at, or None>`
- Last Comment: `<id and created_at, or None>`
- Pagination Exhausted: `<true / false>`
- Duplicate Comment IDs: `<ids or None>`
- Parse Errors: `<count and details, or None>`
- Missing Context: <anything important not found, or "None">
```

Field rules:

- Keep the package concise but preserve facts needed for routing, design, delivery, lifecycle comments, and review.
- Mark absent fields as `Unknown`, `None`, or `Not specified`; do not omit them when downstream routing depends on them.
- If acceptance criteria are inferred from the description or comments, label them as inferred.
- Capture design-document references from issue descriptions, comments, attachments, or prior lifecycle comments so later delivery summaries can cite them.
- Use `Actionability` to guide `d-flow`: `actionable` can proceed, `read-only` should not mutate, `blocked` needs a blocked handoff, and `needs clarification` should route to design/requirement clarification before implementation.

If blocked during intake, include:

- The unresolved issue reference or URL.
- The exact command that failed.
- The error message.
- The next setup step needed from the user.

## Safety Rules

- Never invent issue content. Fetch it first.
- Do not change issue status from this skill.
- Do not post comments from this skill. Leave issue updates and delivery comments to downstream skills.
- Do not download attachments unless they are needed for understanding the issue.
- Do not expose credentials or secrets in summaries.
