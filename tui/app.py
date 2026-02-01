#!/usr/bin/env python3
import asyncio
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Input, Label, RichLog, Static, Tree


@dataclass
class Project:
    name: str
    path: Path
    worktrees: List[str]
    is_worktree_repo: bool


@dataclass
class NodeData:
    kind: str  # "project" | "worktree"
    repo: str
    worktree: Optional[str] = None


@dataclass
class MenuState:
    node: NodeData
    options: List[str]


def projects_dir() -> Path:
    home = Path.home()
    if (home / "Projects").is_dir():
        return home / "Projects"
    return home / "projects"


def run_command(cmd: List[str]) -> str:
    try:
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    except FileNotFoundError:
        return ""
    output = (result.stdout or "") + (result.stderr or "")
    return output.strip()


def load_projects() -> List[Project]:
    root = projects_dir()
    projects: List[Project] = []
    if not root.exists():
        return projects
    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name == "dev":
            continue
        bare_dir = entry / ".bare"
        if bare_dir.is_dir():
            worktrees = [d.name for d in entry.iterdir() if d.is_dir() and d.name != ".bare"]
            projects.append(Project(entry.name, entry, sorted(worktrees), True))
        else:
            projects.append(Project(entry.name, entry, [], False))
    return projects


def summarize_line(output: str) -> str:
    for line in output.splitlines():
        line = line.strip()
        if line:
            return line
    return "(none)"


def pm_session(repo: str, is_worktree_repo: bool) -> str:
    if is_worktree_repo:
        return f"{repo}/main"
    return repo


def worktree_session(repo: str, worktree: str) -> str:
    return f"{repo}/{worktree}/pi"


def normalize_message(message: str) -> str:
    return " ".join(message.splitlines()).strip()


def tmux_session_exists(session: str) -> bool:
    import shutil

    if not shutil.which("tmux"):
        return False
    result = subprocess.run(
        ["tmux", "has-session", "-t", session],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


class PromptScreen(ModalScreen[str]):
    def __init__(self, title: str, placeholder: str = "", confirm_label: str = "Submit") -> None:
        super().__init__()
        self.title = title
        self.placeholder = placeholder
        self.confirm_label = confirm_label
        self._input: Optional[Input] = None

    def compose(self) -> ComposeResult:
        yield Static(self.title, id="prompt-title")
        self._input = Input(placeholder=self.placeholder)
        yield self._input
        yield Static(f"Press Enter to {self.confirm_label}, Esc to cancel", id="prompt-help")

    def on_mount(self) -> None:
        if self._input:
            self._input.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss("")


class ActionMenuScreen(ModalScreen[str]):
    def __init__(self, title: str, options: List[str]) -> None:
        super().__init__()
        self.title = title
        self.options = options
        self._input: Optional[Input] = None

    def compose(self) -> ComposeResult:
        yield Static(self.title, id="prompt-title")
        for idx, option in enumerate(self.options, start=1):
            yield Static(f"{idx}) {option}")
        self._input = Input(placeholder="Enter number")
        yield self._input
        yield Static("Press Enter to select, Esc to cancel", id="prompt-help")

    def on_mount(self) -> None:
        if self._input:
            self._input.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss("")


class CashewApp(App):
    CSS = """
    #layout {height: 1fr;}
    #projects {width: 40%;}
    #status {width: 60%;}
    #status-log {height: 1fr;}
    #prompt-title {padding: 1 1 0 1;}
    #prompt-help {padding: 0 1 1 1; color: $text-muted;}
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("l", "refresh", "Refresh"),
        ("p", "pm_message", "Message PM"),
        ("r", "pm_review_loop", "Send review loop"),
        ("w", "pm_request_review", "Ask code review"),
        ("s", "worktree_message", "Message worktree"),
        ("c", "cleanup", "Cleanup worktree"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.projects: List[Project] = []
        self.current_node: Optional[NodeData] = None
        self.pending_cleanup: Optional[NodeData] = None
        self.modal_open = False
        self.menu_state: Optional[MenuState] = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="layout"):
            with Vertical(id="projects"):
                yield Label("Projects", id="projects-title")
                yield Tree("Projects", id="project-tree")
            with Vertical(id="status"):
                yield Label("Status", id="status-title")
                yield RichLog(id="status-log", highlight=False)
        yield Footer()

    async def on_mount(self) -> None:
        await self.action_refresh()
        tree = self.query_one("#project-tree", Tree)
        tree.focus()

    async def action_refresh(self) -> None:
        self.projects = load_projects()
        tree = self.query_one("#project-tree", Tree)
        tree.root.remove_children()
        tree.root.label = "Projects"
        if not self.projects:
            tree.root.add("(no projects found)")
            self.current_node = None
            self._set_status("No projects found.")
            return
        for project in self.projects:
            node = tree.root.add(project.name, expand=True, data=NodeData("project", project.name))
            if project.is_worktree_repo:
                for worktree in project.worktrees:
                    node.add(worktree, data=NodeData("worktree", project.name, worktree))
        tree.root.expand()
        first = tree.root.children[0] if tree.root.children else None
        if first and isinstance(first.data, NodeData):
            self.current_node = first.data
            tree.cursor_line = first.line
        else:
            self.current_node = None
            tree.cursor_line = 0
        await self._refresh_status()

    async def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        if self.modal_open or self.menu_state:
            return
        node = event.node
        if node and isinstance(node.data, NodeData):
            self.current_node = node.data
            await self._refresh_status()

    async def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        node = event.node
        if not node or not isinstance(node.data, NodeData):
            return
        self.current_node = node.data
        await self._show_action_menu()

    async def _prompt(self, title: str, placeholder: str, confirm: str) -> str:
        self.modal_open = True
        try:
            return await self.push_screen_wait(PromptScreen(title, placeholder, confirm))
        finally:
            self.modal_open = False

    async def action_pm_message(self) -> None:
        if not self.current_node:
            return
        project = self._project_for_node(self.current_node)
        if not project:
            return
        message = await self._prompt("Message PM", "message to PM", "send")
        message = normalize_message(message or "")
        if not message:
            return
        session = pm_session(project.name, project.is_worktree_repo)
        output = run_command(["dev", "send", session, message, "Enter"])
        self._set_status(output or f"Sent to {session}")

    async def action_pm_review_loop(self) -> None:
        if not self.current_node:
            return
        project = self._project_for_node(self.current_node)
        if not project:
            return
        session = pm_session(project.name, project.is_worktree_repo)
        message = "Run `dev review-loop` and follow it exactly (run `bash sleep 300` in the foreground; no scripts/nohup/background loops)."
        output = run_command(["dev", "send", session, message, "Enter"])
        self._set_status(output or f"Sent review loop to {session}")

    async def action_pm_request_review(self) -> None:
        if not self.current_node:
            return
        project = self._project_for_node(self.current_node)
        if not project:
            return
        worktree = None
        if self.current_node.kind == "worktree":
            worktree = self.current_node.worktree
        else:
            worktree = await self._prompt("Worktree name", "feature-branch", "send")
            worktree = (worktree or "").strip()
        if not worktree:
            return
        session = pm_session(project.name, project.is_worktree_repo)
        message = f"Run the code-review skill for {project.name}/{worktree}. Report back before merge."
        output = run_command(["dev", "send", session, message, "Enter"])
        self._set_status(output or f"Sent review request to {session}")

    async def action_worktree_message(self) -> None:
        if not self.current_node or self.current_node.kind != "worktree":
            self._set_status("Select a worktree to message its agent.")
            return
        session = worktree_session(self.current_node.repo, self.current_node.worktree or "")
        message = await self._prompt("Message worktree", "message to agent", "send")
        message = normalize_message(message or "")
        if not message:
            return
        output = run_command(["dev", "send-pi", session, message])
        self._set_status(output or f"Queued for {session}")

    async def action_cleanup(self) -> None:
        if not self.current_node or self.current_node.kind != "worktree":
            self._set_status("Select a worktree to clean up.")
            return
        self.pending_cleanup = self.current_node
        self._set_status(f"Cleanup {self.current_node.repo}/{self.current_node.worktree}? Press 'y' to confirm, 'n' to cancel.")

    async def on_key(self, event) -> None:
        if isinstance(self.focused, Input):
            return

        if self.menu_state:
            if event.key == "escape":
                self.menu_state = None
                await self._refresh_status()
                event.stop()
                return
            if event.key.isdigit():
                await self._handle_menu_choice(int(event.key))
                event.stop()
                return

        if self.pending_cleanup and event.key in {"y", "n"}:
            if event.key == "y":
                session = f"{self.pending_cleanup.repo}/{self.pending_cleanup.worktree}"
                output = run_command(["dev", "cleanup", session])
                self._set_status(output or f"Cleaned {session}")
                await self.action_refresh()
            else:
                self._set_status("Cleanup canceled.")
            self.pending_cleanup = None
            event.stop()
            return

        if event.key == "/":
            await self._filter_projects()
            event.stop()
            return

        if event.key == "right":
            await self._default_attach()
            event.stop()

    def _project_for_node(self, node: NodeData) -> Optional[Project]:
        for project in self.projects:
            if project.name == node.repo:
                return project
        return None

    async def _show_action_menu(self) -> None:
        if not self.current_node:
            return
        if self.menu_state:
            return
        if self.current_node.kind == "project":
            project = self._project_for_node(self.current_node)
            session = pm_session(project.name, project.is_worktree_repo) if project else ""
            pm_label = "Attach PM session"
            if session and tmux_session_exists(session):
                pm_label = "Attach PM session (running)"
            options = [pm_label, "Create new worktree"]
        else:
            repo = self.current_node.repo
            worktree = self.current_node.worktree or ""
            pi_session = f"{repo}/{worktree}/pi"
            claude_session = f"{repo}/{worktree}/claude"
            root_session = f"{repo}/{worktree}"
            pi_label = "Attach pi session (running)" if tmux_session_exists(pi_session) else "Start pi session"
            claude_label = "Attach claude session (running)" if tmux_session_exists(claude_session) else "Start claude session"
            root_label = "Attach worktree root (running)" if tmux_session_exists(root_session) else "Start worktree root"
            options = [
                pi_label,
                claude_label,
                root_label,
                "Create sub-session",
            ]
        self.menu_state = MenuState(self.current_node, options)
        lines = ["Select action:"]
        for idx, option in enumerate(options, start=1):
            lines.append(f"{idx}) {option}")
        lines.append("(Esc to cancel)")
        self._set_status("\n".join(lines))

    async def _handle_menu_choice(self, choice: int) -> None:
        if not self.menu_state:
            return
        node = self.menu_state.node
        options = self.menu_state.options
        if choice < 1 or choice > len(options):
            return
        self.menu_state = None
        if node.kind == "project":
            project = self._project_for_node(node)
            if not project:
                await self._refresh_status()
                return
            if choice == 1:
                session = pm_session(project.name, project.is_worktree_repo)
                cwd = project.path / "main" if project.is_worktree_repo else project.path
                self._open_session(session, cwd, project.is_worktree_repo, None)
            elif choice == 2:
                branch = await self._prompt("New worktree", "branch-name", "create")
                branch = (branch or "").strip()
                if branch:
                    run_command(["dev", "wt", project.name, branch])
                    await self.action_refresh()
        else:
            repo = node.repo
            worktree = node.worktree or ""
            project = self._project_for_node(node)
            project_path = project.path if project else (projects_dir() / repo)
            cwd = project_path / worktree
            is_worktree_repo = project.is_worktree_repo if project else True
            if choice == 1:
                self._open_session(f"{repo}/{worktree}/pi", cwd, is_worktree_repo, "pi")
            elif choice == 2:
                self._open_session(f"{repo}/{worktree}/claude", cwd, is_worktree_repo, "claude")
            elif choice == 3:
                self._open_session(f"{repo}/{worktree}", cwd, is_worktree_repo, None)
            elif choice == 4:
                sub = await self._prompt("Sub-session name", "name", "open")
                sub = (sub or "").strip()
                if sub:
                    self._open_session(f"{repo}/{worktree}/{sub}", cwd, is_worktree_repo, sub)
        await self._refresh_status()

    async def _default_attach(self) -> None:
        if not self.current_node:
            return
        if self.current_node.kind == "project":
            project = self._project_for_node(self.current_node)
            if not project:
                return
            session = pm_session(project.name, project.is_worktree_repo)
            cwd = project.path / "main" if project.is_worktree_repo else project.path
            self._open_session(session, cwd, project.is_worktree_repo, None)
        elif self.current_node.kind == "worktree":
            repo = self.current_node.repo
            worktree = self.current_node.worktree or ""
            project = self._project_for_node(self.current_node)
            project_path = project.path if project else (projects_dir() / repo)
            cwd = project_path / worktree
            self._open_session(f"{repo}/{worktree}/pi", cwd, True, "pi")

    async def _filter_projects(self) -> None:
        query = await self._prompt("Filter projects", "type to filter", "apply")
        query = (query or "").strip().lower()
        if not query:
            await self.action_refresh()
            return
        tree = self.query_one("#project-tree", Tree)
        tree.root.remove_children()
        filtered = []
        for project in self.projects:
            if query in project.name.lower():
                filtered.append(project)
                continue
            for wt in project.worktrees:
                if query in wt.lower():
                    filtered.append(project)
                    break
        if not filtered:
            tree.root.add("(no matches)")
            self.current_node = None
            self._set_status("No matches.")
            return
        for project in filtered:
            node = tree.root.add(project.name, expand=True, data=NodeData("project", project.name))
            if project.is_worktree_repo:
                for worktree in project.worktrees:
                    if query in project.name.lower() or query in worktree.lower():
                        node.add(worktree, data=NodeData("worktree", project.name, worktree))
        tree.root.expand()
        first = tree.root.children[0] if tree.root.children else None
        if first and isinstance(first.data, NodeData):
            self.current_node = first.data
            tree.cursor_line = first.line
            await self._refresh_status()
        else:
            self._set_status("Select a project or worktree.")

    def _auto_command(self, is_worktree_repo: bool, sub: Optional[str]) -> List[str]:
        if sub == "pi":
            return ["pi"]
        if sub == "claude":
            return ["claude", "--dangerously-skip-permissions"]
        if is_worktree_repo:
            return ["pi"]
        return ["claude", "--dangerously-skip-permissions"]

    def _open_session(self, session: str, cwd: Path, is_worktree_repo: bool, sub: Optional[str]) -> None:
        import os
        import shlex
        import shutil

        if os.environ.get("TMUX") and shutil.which("tmux"):
            command = self._auto_command(is_worktree_repo, sub)
            cmd_parts = ["tmux", "new-session", "-A", "-s", session, "-c", str(cwd)]
            cmd_parts += command
            tmux_inner = " ".join(shlex.quote(part) for part in cmd_parts)
            try:
                origin_window = (
                    subprocess.check_output(
                        ["tmux", "display-message", "-p", "#{window_id}"],
                        text=True,
                    )
                    .strip()
                )
            except Exception:
                origin_window = ""
            return_cmd = ""
            if origin_window:
                return_cmd = f"tmux select-window -t {shlex.quote(origin_window)}; "
            tmux_cmd = (
                "bash -lc '"
                "WIN=$(tmux display-message -p \"#{window_id}\"); "
                "unset TMUX; "
                f"{tmux_inner}; "
                f"{return_cmd}"
                "tmux kill-window -t \"$WIN\"'"
            )
            subprocess.run(["tmux", "new-window", tmux_cmd], check=False)
            return

        os.execvp("dev", ["dev", session])

    def _set_status(self, text: str) -> None:
        log = self.query_one("#status-log", RichLog)
        log.clear()
        log.write(text)

    async def _refresh_status(self) -> None:
        if not self.current_node:
            self._set_status("Select a project or worktree.")
            return
        self._set_status("Loading...")
        try:
            if self.current_node.kind == "project":
                await self._refresh_project_status(self.current_node)
            else:
                await self._refresh_worktree_status(self.current_node)
        except Exception as exc:
            self._set_status(f"Error: {exc}")

    async def _refresh_project_status(self, node: NodeData) -> None:
        project = self._project_for_node(node)
        if not project:
            self._set_status("Project not found.")
            return
        session = pm_session(project.name, project.is_worktree_repo)

        def collect() -> str:
            parts = [f"PM session: {session}", ""]
            if project.is_worktree_repo:
                parts.append("Worktrees:")
                for wt in project.worktrees:
                    wt_session = worktree_session(project.name, wt)
                    last_msg = summarize_line(run_command(["dev", "pi-status", wt_session, "--messages", "1"]))
                    req = summarize_line(run_command(["dev", "requirements", wt_session]))
                    parts.append(f"- {wt}: {last_msg} | req: {req}")
            else:
                parts.append("(non-worktree repo)")
            return "\n".join(parts)

        text = await asyncio.to_thread(collect)
        self._set_status(text)

    async def _refresh_worktree_status(self, node: NodeData) -> None:
        session = worktree_session(node.repo, node.worktree or "")

        def collect() -> str:
            parts = []
            parts.append(f"Worktree: {node.repo}/{node.worktree}")
            parts.append("")
            parts.append("== last message ==")
            parts.append(run_command(["dev", "pi-status", session, "--messages", "1"]))
            parts.append("")
            parts.append("== requirements ==")
            parts.append(run_command(["dev", "requirements", session]))
            parts.append("")
            parts.append("== queue ==")
            parts.append(run_command(["dev", "queue-status", session, "-m"]))
            return "\n".join(parts)

        text = await asyncio.to_thread(collect)
        self._set_status(text)


if __name__ == "__main__":
    CashewApp().run()
