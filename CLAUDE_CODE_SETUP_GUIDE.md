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

Control what Claude can do without asking. In `.claude/settings.json`:

```json
{
  "permissions": {
    "allow": [
      "Bash(python3 crossword_server.py)",
      "Bash(git add:*)",
      "Bash(git commit:*)",
      "Bash(git log *)",
      "Bash(git diff *)",
      "Bash(git status)"
    ],
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
- [ ] Configure `.claude/settings.json` with permissions
- [ ] Add SessionStart compact hook to preserve rules
- [ ] Test with `/hooks`, `/permissions`, `/memory`
- [ ] Commit `.claude/` directory (except settings.local.json)

---

## Key Insight

Written instructions alone are insufficient. The reliability stack is:

1. **CLAUDE.md** — what to do (advisory)
2. **Rules** — what to do per-file (advisory, but survives compaction)
3. **Hooks** — enforce it (deterministic, cannot be bypassed)
4. **Permissions** — restrict access (deterministic)

Move your most-violated rules from Layer 1 to Layer 2/3.
