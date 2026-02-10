# Setup - Bootstrap Dev Environment

Use this skill to set up a new machine with the Cashew dev environment.

## When to Use

When the user asks to set up their dev environment, bootstrap a new machine, or says something like "set up cashew" or "configure my dev setup".

## Step 1: Ask the User

Before doing anything, ask:

1. **What should your projects folder be called?** (default: `~/projects`)
2. **What's your GitHub email?** (for SSH key)
3. **Do you want SSH remote access enabled?** (for headless servers)
4. **Install the optional Repo Quality Rails Setup skill?** (installs the quality-gates skill content)

Use the AskUserQuestion tool for this.

## Step 2: Install Dependencies

Based on the OS, install the required tools:

### macOS
```bash
# Install Homebrew if not present
command -v brew || /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install core tools
brew install git gh tmux

# TUI dependency (optional)
python3 -m pip install --user textual

# Cashew TUI launcher (optional)
sudo curl -fsSL https://raw.githubusercontent.com/andrewxhill/cashew/main/bin/cashew -o /usr/local/bin/cashew
sudo chmod +x /usr/local/bin/cashew

# Install Docker Desktop
brew install --cask docker
```

### Linux (Debian/Ubuntu)
```bash
sudo apt-get update
sudo apt-get install -y git curl tmux python3-pip

# TUI dependency (optional)
python3 -m pip install --user textual

# Cashew TUI launcher (optional)
sudo curl -fsSL https://raw.githubusercontent.com/andrewxhill/cashew/main/bin/cashew -o /usr/local/bin/cashew
sudo chmod +x /usr/local/bin/cashew

# GitHub CLI
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt-get update && sudo apt-get install -y gh

# Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
```

## Step 3: Create Projects Directory

```bash
mkdir -p ~/<folder-name-from-step-1>
```

## Step 4: Install dev + Cashew TUI

Clone the repo and symlink the binaries so updates are instant:

```bash
# Clone cashew (worktree-based repo)
mkdir -p ~/<folder-name-from-step-1>/cashew
cd ~/<folder-name-from-step-1>
git clone --bare git@github.com:andrewxhill/cashew.git cashew/.bare
cd cashew
GIT_DIR=.bare git worktree add main main

# Symlink binaries
sudo ln -sf ~/<folder-name-from-step-1>/cashew/main/bin/dev /usr/local/bin/dev
sudo ln -sf ~/<folder-name-from-step-1>/cashew/main/bin/cashew /usr/local/bin/cashew

# Install fzf (required for Cashew TUI)
if ! command -v fzf >/dev/null 2>&1; then
  if command -v brew >/dev/null 2>&1; then
    brew install fzf
  elif command -v apt-get >/dev/null 2>&1; then
    sudo apt-get install -y fzf
  fi
fi
```

## Step 5: Install Claude Config (Append Cashew Block)

Append Cashew's global context block to the end of the user's `~/.claude/CLAUDE.md` (do **not** overwrite). Only add it if the block isn't already present:

```bash
mkdir -p ~/.claude/commands

CASHEW_ROOT=~/<folder-name-from-step-1>/cashew/main
CASHEW_BLOCK=$CASHEW_ROOT/claude/global/CLAUDE.md
TARGET=~/.claude/CLAUDE.md

if ! grep -q "BEGIN CASHEW GLOBAL CONTEXT" "$TARGET" 2>/dev/null; then
  {
    echo ""
    echo "<!-- BEGIN CASHEW GLOBAL CONTEXT -->"
    sed "s|<cashew-root>|$CASHEW_ROOT|g" "$CASHEW_BLOCK"
    echo "<!-- END CASHEW GLOBAL CONTEXT -->"
  } >> "$TARGET"
fi

# Symlink commands and skills from the repo
ln -sf ~/<folder-name-from-step-1>/cashew/main/claude/commands/dev.md ~/.claude/commands/dev.md
ln -sf ~/<folder-name-from-step-1>/cashew/main/.claude/skills/setup ~/.claude/skills/setup
ln -sf ~/<folder-name-from-step-1>/cashew/main/claude/skills/prompting-worktree-agents ~/.claude/skills/prompting-worktree-agents

# Optional: Repo Quality Rails Setup skill (only if user opted in)
ln -sf ~/<folder-name-from-step-1>/cashew/main/claude/skills/repo-quality-rails-setup ~/.claude/skills/repo-quality-rails-setup
```

## Step 6: Install Pi Message Queue Extension

The message-queue extension lets `dev send-pi` deliver messages to running pi agents. Install it globally so it loads in every pi session:

```bash
# Requires pi to be installed: npm install -g @mariozechner/pi-coding-agent
pi install ~/<folder-name-from-step-1>/cashew/main/pi/extensions/message-queue.ts

# Verify
pi list
# Should show: message-queue.ts under "User packages"
```

## Step 7: Configure Git for SSH (if needed)

```bash
# Generate SSH key if needed
[ -f ~/.ssh/id_ed25519 ] || ssh-keygen -t ed25519 -C "<user-email>" -f ~/.ssh/id_ed25519 -N ""

# Start agent and add key
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519

# Configure git to always use SSH for GitHub
git config --global url."git@github.com:".insteadOf "https://github.com/"

# Show the public key for user to add to GitHub
echo "Add this SSH key to GitHub:"
cat ~/.ssh/id_ed25519.pub
echo ""
echo "Or run: gh auth login && gh ssh-key add ~/.ssh/id_ed25519.pub"
```

## Step 8: (If requested) Enable SSH Remote Access

```bash
# macOS
sudo systemsetup -setremotelogin on

# Linux
sudo systemctl enable ssh && sudo systemctl start ssh
```

## Step 9: Verify Installation

```bash
docker --version
git --version
gh --version
tmux -V
fzf --version
dev --help
cashew
pi list          # should show message-queue.ts
ssh -T git@github.com
```

## What Gets Installed

| Component | Location | Purpose |
|-----------|----------|---------|
| dev script | `/usr/local/bin/dev` | Project session manager (symlink to repo) |
| cashew launcher | `/usr/local/bin/cashew` | tmux + fzf TUI launcher (symlink to repo) |
| Global Claude config | `~/.claude/CLAUDE.md` | Cashew block appended (idempotent) |
| /dev skill | `~/.claude/commands/dev.md` | Full dev documentation (symlink to repo) |
| /setup skill | `~/.claude/skills/setup/` | This bootstrap skill (symlink to repo) |
| /prompting-worktree-agents skill | `~/.claude/skills/prompting-worktree-agents/` | Socratic prompting loop for worktree agents |
| /repo-quality-rails-setup skill | `~/.claude/skills/repo-quality-rails-setup/` | Optional quality rails setup skill (from cashew/claude/skills) |
| Pi message-queue | `pi list` (user package) | Enables `dev send-pi` to deliver messages to pi agents |
| Projects folder | `~/<user-choice>` | Where all projects live |
