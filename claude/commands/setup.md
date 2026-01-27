# Setup - Bootstrap Dev Environment

Use this skill to set up a new machine with the Cashew dev environment.

## When to Use

When the user asks to set up their dev environment, bootstrap a new machine, or says something like "set up cashew" or "configure my dev setup".

## Step 1: Ask the User

Before doing anything, ask:

1. **What should your projects folder be called?** (default: `~/projects`)
2. **What's your GitHub email?** (for SSH key)
3. **Do you want SSH remote access enabled?** (for headless servers)

Use the AskUserQuestion tool for this.

## Step 2: Install Dependencies

Based on the OS, install the required tools:

### macOS
```bash
# Install Homebrew if not present
command -v brew || /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install core tools
brew install git gh

# Install Docker Desktop
brew install --cask docker
```

### Linux (Debian/Ubuntu)
```bash
sudo apt-get update
sudo apt-get install -y git curl

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

## Step 4: Install and Configure dev Script

Download the dev script, then **edit it** to use the user's chosen projects folder:

```bash
# Download
sudo curl -fsSL https://raw.githubusercontent.com/andrewxhill/cashew/main/bin/dev -o /usr/local/bin/dev
sudo chmod +x /usr/local/bin/dev

# Edit PROJECTS_DIR to match user's choice (if not ~/projects)
sudo sed -i '' 's|PROJECTS_DIR="\$HOME/projects"|PROJECTS_DIR="\$HOME/<folder-name>"|' /usr/local/bin/dev
```

## Step 5: Install Claude Config

```bash
mkdir -p ~/.claude/commands

# Download and install - then edit to match user's folder
curl -fsSL https://raw.githubusercontent.com/andrewxhill/cashew/main/claude/global/CLAUDE.md > ~/.claude/CLAUDE.md
curl -fsSL https://raw.githubusercontent.com/andrewxhill/cashew/main/claude/commands/dev.md > ~/.claude/commands/dev.md
curl -fsSL https://raw.githubusercontent.com/andrewxhill/cashew/main/claude/commands/setup.md > ~/.claude/commands/setup.md

# Update paths in CLAUDE.md if folder isn't ~/projects
sed -i '' 's|~/projects|~/<folder-name>|g' ~/.claude/CLAUDE.md
sed -i '' 's|~/projects|~/<folder-name>|g' ~/.claude/commands/dev.md
```

## Step 6: Configure Git for SSH

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

## Step 7: (If requested) Enable SSH Remote Access

```bash
# macOS
sudo systemsetup -setremotelogin on

# Linux
sudo systemctl enable ssh && sudo systemctl start ssh
```

## Step 8: Verify Installation

```bash
docker --version
git --version
gh --version
dev --help
ssh -T git@github.com
```

## What Gets Installed

| Component | Location | Purpose |
|-----------|----------|---------|
| dev script | `/usr/local/bin/dev` | Project session manager |
| Global Claude config | `~/.claude/CLAUDE.md` | Workflow context for all sessions |
| /dev skill | `~/.claude/commands/dev.md` | Full dev documentation |
| /setup skill | `~/.claude/commands/setup.md` | This bootstrap skill |
| Projects folder | `~/<user-choice>` | Where all projects live |
