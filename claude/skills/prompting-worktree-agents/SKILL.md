# Prompting Worktree Agents (Socratic Loop)

Use this skill when you are orchestrating worktree agents and want them to reason before coding.

## Goal
Guide each worktree agent through a short Socratic loop so they articulate impact, constraints, and a safe plan **before** implementation.

## When to Use
- You just created worktree agents for issues.
- You need deeper reasoning or risk analysis before code changes.

## Procedure (per issue/agent)
1. **Send three separate Socratic prompts (one at a time).** Do **not** send them as a single combined message.
   - **Theoretical:** “What makes a fix for this kind of issue effective in production (impact, risk, measurability)?”
   - **Framework:** “What principles/constraints apply here (data integrity, trading risk, latency, rollback, tests)?”
   - **Application:** “Now apply those to this issue: root-cause hypothesis, edge cases, acceptance criteria, and a safe implementation plan.”

2. **Wait after each prompt.** Use the **dev command skill** to read their response before sending the next question:
   ```bash
   dev pi-status <repo>/<worktree> --messages 1
   ```
   Acknowledge briefly (1–2 sentences), then send the next question.

3. **After the third answer**, summarize their responses back to them and only then instruct them to proceed with implementation.

## Best Practices
- **Follow-up vs steer:** use `dev send-pi <session> "..."` (follow-up/queued) for non-urgent guidance; use `dev send-pi <session> --enter "..."` (steer) only to interrupt unsafe or off-track work.
- **Check before nudging:** always read the last message with `dev pi-status <session> --messages 1` before sending anything.
- **If responses are shallow:** ask one additional Socratic question, then proceed.
