# Cashew TUI

Cashew now uses a **tmux + fzf** TUI. The left pane is a selector, the right pane shows status or attaches to the live session you choose.

## Requirements

- `tmux`
- `fzf`

## Run

```bash
cashew
```

## Usage

- Type to filter projects/worktrees/sessions.
- Move selection to update the right pane status.
- Press Enter on a session to attach it in the right pane.
- Select `new...` under a worktree to create a new sub-session.

## Notes

- The right pane is a real tmux client (nested), not an embedded terminal.
- Use `cashew` again to return to the TUI if you switch away.
