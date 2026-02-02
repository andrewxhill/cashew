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
    kind: str  # "project" | "worktree" | "session" | "new-session"
    repo: str
    worktree: Optional[str] = None
    session: Optional[str] = None
    sub: Optional[str] = None


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


def tmux_session_name(session: str) -> str:
    return session.replace("/", "_")


def tmux_session_exists(session: str) -> bool:
    import shutil

    if not shutil.which("tmux"):
        return False
    tmux_name = tmux_session_name(session)
    result = subprocess.run(
        ["tmux", "has-session", "-t", tmux_name],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def tmux_window_exists(window_name: str) -> bool:
    import shutil

    if not shutil.which("tmux"):
        return False
    result = subprocess.run(
        ["tmux", "list-windows", "-F", "#W"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False
    names = {line.strip() for line in (result.stdout or "").splitlines() if line.strip()}
    return window_name in names


def tmux_list_sessions() -> List[str]:
    import shutil

    if not shutil.which("tmux"):
        return []
    result = subprocess.run(
        ["tmux", "list-sessions", "-F", "#S"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]


def sessions_for_worktree(repo: str, worktree: str, tmux_sessions: List[str]) -> List[str]:
    prefix = f"{repo}_{worktree}"
    sessions = []
    for name in tmux_sessions:
        if not name.startswith(prefix):
            continue
        if name == prefix:
            sessions.append(f"{repo}/{worktree}")
        elif name.startswith(prefix + "_"):
            sub = name[len(prefix) + 1 :]
            sessions.append(f"{repo}/{worktree}/{sub}")
    return sorted(set(sessions))


def sessions_for_repo(repo: str, tmux_sessions: List[str]) -> List[str]:
    sessions = []
    for name in tmux_sessions:
        if name == repo:
            sessions.append(repo)
        elif name.startswith(repo + "_"):
            sub = name[len(repo) + 1 :]
            sessions.append(f"{repo}/{sub}")
    return sorted(set(sessions))


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
        tmux_sessions = tmux_list_sessions()
        for project in self.projects:
            node = tree.root.add(project.name, expand=True, data=NodeData("project", project.name))
            if project.is_worktree_repo:
                for worktree in project.worktrees:
                    wt_node = node.add(worktree, data=NodeData("worktree", project.name, worktree))
                    sessions = sessions_for_worktree(project.name, worktree, tmux_sessions)
                    for session in sessions:
                        label = session.split("/")[-1]
                        if session == f"{project.name}/{worktree}":
                            label = "root"
                        wt_node.add(
                            label,
                            data=NodeData(
                                "session",
                                project.name,
                                worktree,
                                session=session,
                                sub=None if label == "root" else label,
                            ),
                        )
                    wt_node.add(
                        "new...",
                        data=NodeData("new-session", project.name, worktree),
                    )
            else:
                sessions = sessions_for_repo(project.name, tmux_sessions)
                for session in sessions:
                    label = session.split("/")[-1]
                    node.add(
                        label,
                        data=NodeData("session", project.name, None, session=session, sub=label),
                    )
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
        if self.modal_open:
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
        await self._handle_selection()

    async def _prompt(self, title: str, placeholder: str, confirm: str) -> str:
        self.modal_open = True
        try:
            return await self.push_screen_wait(PromptScreen(title, placeholder, confirm))
        finally:
            self.modal_open = False

    def _session_from_node(self, node: NodeData) -> Optional[str]:
        if node.session:
            return node.session
        if node.kind == "session" and node.worktree:
            return f"{node.repo}/{node.worktree}"
        return None

    async def _handle_selection(self) -> None:
        if not self.current_node:
            return
        node = self.current_node
        if node.kind == "session":
            project = self._project_for_node(node)
            if not project:
                return
            session = self._session_from_node(node)
            if not session:
                return
            cwd = project.path / node.worktree if node.worktree else project.path
            self._open_session(session, cwd, project.is_worktree_repo, node.sub)
        elif node.kind == "new-session":
            project = self._project_for_node(node)
            if not project:
                return
            sub = await self._prompt("New session", "name (pi/claude/etc)", "open")
            sub = (sub or "").strip()
            if not sub:
                return
            cwd = project.path / node.worktree if node.worktree else project.path
            session = f"{node.repo}/{node.worktree}/{sub}"
            self._open_session(session, cwd, project.is_worktree_repo, sub)

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
        if self.current_node.worktree:
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
        if not self.current_node or self.current_node.kind not in {"worktree", "session", "new-session"}:
            self._set_status("Select a worktree to message its agent.")
            return
        if not self.current_node.worktree:
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
        if not self.current_node or not self.current_node.worktree:
            self._set_status("Select a worktree to clean up.")
            return
        self.pending_cleanup = self.current_node
        self._set_status(f"Cleanup {self.current_node.repo}/{self.current_node.worktree}? Press 'y' to confirm, 'n' to cancel.")

    async def on_key(self, event) -> None:
        if isinstance(self.focused, Input):
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

        if event.key == "/" and not self.modal_open:
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

    async def _default_attach(self) -> None:
        if not self.current_node:
            return
        if self.current_node.kind == "session":
            await self._handle_selection()
            return
        if self.current_node.kind == "new-session":
            await self._handle_selection()
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
        tmux_sessions = tmux_list_sessions()
        for project in filtered:
            node = tree.root.add(project.name, expand=True, data=NodeData("project", project.name))
            if project.is_worktree_repo:
                for worktree in project.worktrees:
                    if query in project.name.lower() or query in worktree.lower():
                        wt_node = node.add(worktree, data=NodeData("worktree", project.name, worktree))
                        sessions = sessions_for_worktree(project.name, worktree, tmux_sessions)
                        for session in sessions:
                            label = session.split("/")[-1]
                            if session == f"{project.name}/{worktree}":
                                label = "root"
                            wt_node.add(
                                label,
                                data=NodeData(
                                    "session",
                                    project.name,
                                    worktree,
                                    session=session,
                                    sub=None if label == "root" else label,
                                ),
                            )
                        wt_node.add("new...", data=NodeData("new-session", project.name, worktree))
            else:
                sessions = sessions_for_repo(project.name, tmux_sessions)
                for session in sessions:
                    label = session.split("/")[-1]
                    node.add(
                        label,
                        data=NodeData("session", project.name, None, session=session, sub=label),
                    )
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
            tmux_name = tmux_session_name(session)
            cmd_parts = ["tmux", "new-session", "-A", "-s", tmux_name, "-c", str(cwd)]
            cmd_parts += command
            tmux_inner = " ".join(shlex.quote(part) for part in cmd_parts)
            tmux_cmd = f"bash -lc 'unset TMUX; exec {tmux_inner}'"
            window_name = f"cashew-{tmux_name}"
            if tmux_window_exists(window_name):
                subprocess.run(["tmux", "select-window", "-t", window_name], check=False)
            else:
                subprocess.run(
                    ["tmux", "new-window", "-d", "-n", window_name, tmux_cmd],
                    check=False,
                )
                subprocess.run(["tmux", "select-window", "-t", window_name], check=False)
            subprocess.run(
                [
                    "tmux",
                    "display-message",
                    f"Opened {window_name}. Use prefix+w or `cashew` to return to the TUI.",
                ],
                check=False,
            )
            self._set_status(
                f"Opened {window_name}. Use tmux prefix+w or `cashew` to return to the TUI."
            )
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
            elif self.current_node.kind == "worktree":
                await self._refresh_worktree_status(self.current_node)
            elif self.current_node.kind == "session":
                await self._refresh_session_status(self.current_node)
            elif self.current_node.kind == "new-session":
                await self._refresh_new_session_status(self.current_node)
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

    async def _refresh_session_status(self, node: NodeData) -> None:
        session = self._session_from_node(node)
        if not session:
            self._set_status("Session not found.")
            return
        running = "yes" if tmux_session_exists(session) else "no"

        def collect() -> str:
            parts = [f"Session: {session}", f"Running: {running}", ""]
            if session.endswith("/pi"):
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

    async def _refresh_new_session_status(self, node: NodeData) -> None:
        self._set_status(
            "New session for "
            f"{node.repo}/{node.worktree}.\n"
            "Press Enter to name the sub-session (pi/claude/etc)."
        )


if __name__ == "__main__":
    CashewApp().run()
