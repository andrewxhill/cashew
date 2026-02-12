---
name: prompting-worktree-agents
description: >
  Socratic prompting loop for worktree agents. Use this skill whenever you are
  about to send implementation instructions to a worktree agent — it ensures the
  agent reasons through the problem before writing code. Also use it when the user
  asks to "prompt the agent", "have it think first", or when you're orchestrating
  multiple worktree agents on non-trivial tasks.
---

# Prompting Worktree Agents (Socratic Loop)

Before a worktree agent touches code, walk it through three focused questions
so it understands the problem, the constraints, and has a concrete plan. This
catches bad assumptions early and produces better first attempts.

## When to Use the Full Loop vs. a Quick Prompt

**Full loop (three prompts):** Risky changes, complex features, anything touching
data integrity, multi-service coordination, or unfamiliar parts of the codebase.

**Quick version (single prompt):** Small bug fixes, straightforward refactors, or
tasks where the agent already has deep context. In this case, just ask: "Explain
your approach before you start — what are you changing, what could break, and how
will you verify it works?"

When in doubt, use the full loop. The cost is a few minutes; the cost of a bad
first attempt is much higher.

## The Three Prompts

Send these **one at a time**. Wait for the agent to respond to each before
sending the next. This forces the agent to build understanding incrementally
rather than rushing to a plan.

### 1. Understand the problem

Ground the agent in the actual code and context. Don't let it theorize — make
it look.

```bash
dev send-pi <repo>/<worktree>/pi "Before you start, read the relevant code and
explain: what is actually happening now, what should be happening instead, and
where in the codebase does this live?"
```

### 2. Identify constraints and risks

Now that the agent has context, push it to think about what could go wrong.

```bash
dev send-pi <repo>/<worktree>/pi "What constraints apply to this change?
Think about: existing tests, data integrity, other code that depends on this,
rollback safety, and edge cases that could bite us."
```

### 3. Propose a plan

Only now should the agent propose what to do.

```bash
dev send-pi <repo>/<worktree>/pi "Now propose your implementation plan: what
files you'll change, in what order, what tests you'll add or update, and how
you'll verify it works. Be specific."
```

## Between Each Prompt

Always read the agent's response before sending the next question:

```bash
dev pi-status <repo>/<worktree>/pi --messages 1
```

Acknowledge briefly (1-2 sentences), then send the next prompt. If the response
is vague or hand-wavy, ask a follow-up that forces specificity: "Which file?
Which function? What's the actual data flow?" Don't move on until the answer
is grounded in the code.

## After the Third Answer

Summarize what the agent said back to it — the problem, the constraints, and
the plan. Correct anything that's off. Only then give the go-ahead to implement.

```bash
dev send-pi <repo>/<worktree>/pi "Good. Here's what I'm hearing: [summary].
[Any corrections or additions]. Go ahead and implement this plan."
```

## Judging Response Quality

**Good signs:**
- References specific files, functions, line numbers
- Identifies concrete edge cases (not just "there might be edge cases")
- Plan has a clear order of operations
- Mentions how to verify the change works (tests, manual checks)

**Red flags:**
- Generic statements that could apply to any codebase
- "I'll handle edge cases" without naming them
- No mention of existing tests or how they're affected
- Plan jumps straight to the happy path without considering failure modes

If you see red flags, don't proceed. Ask one more targeted question to force
the agent to get specific. If it still can't, the task may need to be broken
down further or the agent needs more context.

## Best Practices

- **Always check before sending:** `dev pi-status <session> --messages 1` before
  every message. Never nudge blind.
- **Default to queued delivery:** `dev send-pi <session> "message"` with no flags.
  This queues the message for when the agent finishes its current turn. Only use
  `--steer` to interrupt genuinely off-track or unsafe work.
- **Adapt the questions to the task.** The three prompts above are templates.
  Tailor them to the specific problem — reference the issue, the module, the
  domain. Generic questions get generic answers.
