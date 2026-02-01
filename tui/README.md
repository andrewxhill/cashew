# Cashew TUI

Lightweight Textual UI for Cashew sessions. It wraps existing `dev` commands and does not change session behavior.

## Requirements

- Python 3
- `textual` (`python3 -m pip install --user textual`)

## Run

```bash
cashew
```

## Keybindings

- `l` refresh projects
- `/` filter projects/worktrees
- `p` message PM (sends to `<repo>/main`)
- `r` send review-loop instructions to PM
- `w` request code review for a worktree (via PM)
- `s` message worktree agent (`dev send-pi`)
- `c` cleanup worktree (`dev cleanup`, confirms with y/n)
- `→` attach default session (PM for project, /pi for worktree)
- `q` quit

## What it shows

- Project/worktree tree (derived from `~/Projects`)
- PM session per repo (`<repo>/main`)
- Worktree last message (`dev pi-status --messages 1`)
- Requirements (`dev requirements`)
- Queue summary (`dev queue-status -m`)
