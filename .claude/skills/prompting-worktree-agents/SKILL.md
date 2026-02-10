# Prompting Worktree Agents (Socratic Loop)

Use this skill when you are orchestrating worktree agents and want them to reason before coding.

## Goal
Guide each worktree agent through a short Socratic loop so they articulate impact, constraints, and a safe plan **before** implementation.

## When to Use
- You just created worktree agents for issues.
- You need deeper reasoning or risk analysis before code changes.

## Procedure (per issue/agent)
1. **Ask the 3-part Socratic prompt** (single message):
   - **Theoretical:** “What makes a fix for this kind of issue effective in production (impact, risk, measurability)?”
   - **Framework:** “What principles/constraints apply here (data integrity, trading risk, latency, rollback, tests)?”
   - **Application:** “Now apply those to this issue: root-cause hypothesis, edge cases, acceptance criteria, and a safe implementation plan.”

2. **Wait for the agent’s response** before any implementation guidance.
   - Use the **dev command skill** to wait and read their response:
     ```bash
     dev pi-status <repo>/<worktree> --messages 1
     ```

3. **Summarize their answers back to them**, then instruct them to proceed with implementation.

## Notes
- Do **not** proceed until the agent responds.
- If the response is shallow, ask one follow-up Socratic question before proceeding.
