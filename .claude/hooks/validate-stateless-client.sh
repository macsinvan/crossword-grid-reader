#!/bin/bash
# PostToolUse hook: validate trainer.js remains stateless after edits
INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# Only check trainer.js
if [[ "$FILE_PATH" != *"trainer.js"* ]]; then
  exit 0
fi

# Check for instance state patterns (this.foo = value assignments that aren't method definitions)
if grep -n 'this\.[a-z].*=' "$FILE_PATH" | grep -v 'this\.render\|this\.submit\|this\.build\|function\|=>\|==\|!=\|innerHTML\|style\.' | grep -v '^\s*//' > /tmp/stateless_violations.txt 2>/dev/null; then
  if [ -s /tmp/stateless_violations.txt ]; then
    echo "WARNING: Possible state in trainer.js (stateless architecture). Check these lines:" >&2
    cat /tmp/stateless_violations.txt >&2
  fi
fi

exit 0
