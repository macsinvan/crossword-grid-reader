# Claude Code Project Setup Guide

How to set up any project for reliable results with Claude Code.

---

## Layered Protection Model

```
Layer 1: CLAUDE.md + .claude/rules/  (Advisory — Claude reads but may forget)
Layer 2: Hooks                        (Deterministic — fires every time, can block)
Layer 3: Permissions                   (Tool-level — controls what Claude can access)
```

---

## Step 1: CLAUDE.md — Keep It Short

CLAUDE.md is read at session start. If it's too long, important rules get lost during compaction.

**Rules:**
- Keep under 100 lines for critical rules
- Every line must answer: "Will Claude make a mistake without this?"
- Move detailed guidance to `.claude/rules/` or separate docs
- Use `@path/to/file.md` imports for referenced documentation

**What goes in CLAUDE.md:**
- Code style (2-3 lines)
- Key commands (build, test, run)
- Architecture constraints (the ones that MUST NOT be violated)
- Gotchas (things Claude gets wrong repeatedly)

**What goes elsewhere:**
- Detailed API docs → separate files, referenced with @imports
- File-by-file descriptions → `.claude/rules/` with path targeting
- Domain knowledge → `.claude/skills/`
- Verbose explanations → linked docs

---

## Step 2: .claude/rules/ — Targeted Rules

Rule files load based on which files Claude is editing. They stay prominent because they're loaded fresh each session.

**Structure:**
```
.claude/rules/
├── architecture.md      # Always loaded (no paths filter)
├── frontend.md          # Loads when editing frontend files
├── backend.md           # Loads when editing backend files
└── testing.md           # Loads when editing test files
```

**Syntax:** Markdown with optional YAML frontmatter:

```markdown
---
paths:
  - "static/*.js"
  - "templates/*.html"
---

# Frontend Rules

- trainer.js has ZERO state. All state on server.
- Never construct HTML strings in JS — render what the server sends.
```

**Key benefit:** Rules files survive compaction. CLAUDE.md content gets summarised; rules files are reloaded fresh.

---

## Step 3: Hooks — Deterministic Enforcement

Hooks fire at lifecycle events. Unlike CLAUDE.md, they cannot be ignored.

**Hook types:**

| Event | When | Can Block? | Use For |
|-------|------|-----------|---------|
| `PreToolUse` | Before tool runs | YES (exit 2) | Block dangerous commands, validate edits |
| `PostToolUse` | After tool succeeds | YES (exit 2) | Auto-format, validate output |
| `SessionStart` | Session begins | No | Re-inject rules after compaction |
| `Stop` | Claude finishes | No | Verify work is complete |

**PreToolUse hook to validate edits:**

`.claude/hooks/validate-edit.sh`:
```bash
#!/bin/bash
INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# Example: block state in stateless UI file
if [[ "$FILE_PATH" == *"trainer.js"* ]]; then
  NEW_CONTENT=$(echo "$INPUT" | jq -r '.tool_input.new_string // empty')
  if echo "$NEW_CONTENT" | grep -q 'this\.\w\+ =' ; then
    echo "BLOCKED: trainer.js must be stateless. No instance state (this.x = ...)." >&2
    exit 2
  fi
fi

exit 0
```

**SessionStart hook to re-inject rules after compaction:**

`.claude/hooks/reinject-on-compact.sh`:
```bash
#!/bin/bash
cat << 'EOF'
CRITICAL RULES (preserved after compaction):
- Stateless client: trainer.js renders server state, no local state
- Template-driven: all presentation in render_templates.json
- No string construction: sequencer resolves {variables}, no f-strings
- Error out, don't fallback: crash on errors, no silent defaults
EOF
exit 0
```

**Register in `.claude/settings.json`:**
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [{ "type": "command", "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/validate-edit.sh" }]
      }
    ],
    "SessionStart": [
      {
        "matcher": "compact",
        "hooks": [{ "type": "command", "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/reinject-on-compact.sh" }]
      }
    ]
  }
}
```

---

## Step 4: Permissions — Tool Access Control

Control what Claude can do without asking. Two files:

- **`.claude/settings.json`** — shared (committed to repo), for deny/ask rules
- **`.claude/settings.local.json`** — personal (gitignored), for allow rules

### Use Broad Wildcards, Not Exact Commands

**The most common mistake:** using exact command strings like `"Bash(git status)"` or `"Bash(python3 crossword_server.py)"`. This causes "Allow this session" to not stick — every slight variation (different flags, arguments, paths) is a new command that doesn't match your rule.

**Pattern format:** `Bash(command:*)` — the `:*` wildcard matches ALL arguments to that command.

**Bad — exact commands (you'll get prompted constantly):**
```json
"Bash(git status)",
"Bash(git add -A)",
"Bash(git commit -m \"fix\")",
"Bash(python3 crossword_server.py)"
```

**Good — broad wildcards (one rule covers all variations):**
```json
"Bash(git:*)",
"Bash(python3:*)"
```

### Recommended Setup

**`.claude/settings.local.json`** (personal, gitignored — your "allow" rules):
```json
{
  "permissions": {
    "allow": [
      "Bash(python3:*)",
      "Bash(git:*)",
      "Bash(gh:*)",
      "Bash(curl:*)",
      "Bash(ls:*)",
      "Bash(pip:*)",
      "Bash(pip3:*)",
      "Bash(kill:*)",
      "Bash(pkill:*)",
      "Bash(ps:*)",
      "Bash(grep:*)",
      "Bash(find:*)",
      "Bash(xargs:*)",
      "Bash(cd:*)",
      "Bash(lsof:*)",
      "Bash(sleep:*)",
      "Bash(source:*)"
    ]
  }
}
```

**`.claude/settings.json`** (shared, committed — your "deny" and "ask" rules):
```json
{
  "permissions": {
    "deny": [
      "Read(./.env)",
      "Bash(rm -rf *)"
    ],
    "ask": [
      "Bash(git push *)"
    ]
  }
}
```

### Cleaning Up Accumulated Permissions

When you click "Allow" during a session, Claude saves the **exact command** to `settings.local.json`. Over time this accumulates dozens of one-off entries like:
```json
"Bash(git log --oneline -5)",
"Bash(git log --oneline -10)",
"Bash(git status)",
"Bash(git diff HEAD~1)"
```

**Fix:** Periodically replace these with broad wildcards. One `"Bash(git:*)"` replaces all git-related entries. Check your `settings.local.json` and consolidate.

---

## Step 5: Verify Your Setup

In a Claude Code session:
- `/hooks` — shows registered hooks
- `/permissions` — shows allow/deny/ask rules
- `/memory` — shows loaded CLAUDE.md and rules files
- `claude --debug` — shows hook execution in real time

---

## Step 6: Setup Checklist

For any new project:

- [ ] Run `/init` to generate starter CLAUDE.md
- [ ] Trim CLAUDE.md to critical rules only (<100 lines)
- [ ] Create `.claude/rules/` with path-targeted rules
- [ ] Create `.claude/hooks/` with validation scripts
- [ ] Configure `.claude/settings.json` with deny/ask permissions
- [ ] Create `.claude/settings.local.json` with broad wildcard allow rules (`Bash(git:*)` not `Bash(git status)`)
- [ ] Add SessionStart compact hook to preserve rules
- [ ] Test with `/hooks`, `/permissions`, `/memory`
- [ ] Commit `.claude/` directory (except settings.local.json)

---

## Key Insights

Written instructions alone are insufficient. The reliability stack is:

1. **CLAUDE.md** — what to do (advisory)
2. **Rules** — what to do per-file (advisory, but survives compaction)
3. **Hooks** — enforce it (deterministic, cannot be bypassed)
4. **Permissions** — restrict access (deterministic)

Move your most-violated rules from Layer 1 to Layer 2/3.

**Permissions tip:** Always use `Bash(command:*)` wildcard patterns for allow rules. Exact command strings like `Bash(git status)` don't match `git status -s` — you'll get prompted for every variation. One `Bash(git:*)` covers all git commands.
