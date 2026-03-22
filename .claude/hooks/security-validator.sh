#!/bin/bash
# .claude/hooks/security-validator.sh
# PreToolUse hook — blocks dangerous commands and sensitive file access during development.
# Receives JSON via stdin from Claude Code with tool_name and tool_input.

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name')
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
CONTENT=$(echo "$INPUT" | jq -r '.tool_input.content // empty')

# ── Block destructive Bash commands ───────────────────────────────────────────
if [ "$TOOL_NAME" = "Bash" ]; then
  # Block destructive commands
  if echo "$COMMAND" | grep -iE '(rm\s+-rf\s+/|dd\s+if=|mkfs|:\(\)\{|DROP\s+TABLE|TRUNCATE\s+TABLE)' > /dev/null 2>&1; then
    echo "BLOCKED: Destructive command not allowed: $COMMAND" >&2
    exit 2
  fi

  # Block force-push to main/master
  if echo "$COMMAND" | grep -iE 'git\s+push.*--force.*(main|master)' > /dev/null 2>&1; then
    echo "BLOCKED: Force-push to main/master not allowed" >&2
    exit 2
  fi

  # Block commands that dump env vars
  if echo "$COMMAND" | grep -iE '(printenv|env\s*$|echo\s+\$[A-Z_]*KEY|echo\s+\$[A-Z_]*SECRET|echo\s+\$[A-Z_]*PASSWORD)' > /dev/null 2>&1; then
    echo "BLOCKED: Dumping environment variables not allowed" >&2
    exit 2
  fi

  # Block curl/wget to unknown hosts (potential data exfiltration)
  if echo "$COMMAND" | grep -iE '(curl|wget)\s+' > /dev/null 2>&1; then
    # Allow known hosts only
    if ! echo "$COMMAND" | grep -iE '(localhost|127\.0\.0\.1|egain\.com|aha\.io|googleapis\.com|anthropic\.com|openai\.com|api\.github\.com)' > /dev/null 2>&1; then
      echo "BLOCKED: HTTP requests to unknown hosts not allowed. Add host to allowlist in security-validator.sh" >&2
      exit 2
    fi
  fi
fi

# ── Block sensitive file access ───────────────────────────────────────────────
if [ -n "$FILE_PATH" ]; then
  # Block reading .env files (contain API keys)
  if echo "$FILE_PATH" | grep -iE '\.env(\.local|\.dev|\.prod)?$' > /dev/null 2>&1; then
    echo "BLOCKED: Cannot read .env files — contains API keys" >&2
    exit 2
  fi

  # Block reading credentials/secrets files
  if echo "$FILE_PATH" | grep -iE '(credentials|secrets|\.pem|\.key|id_rsa)' > /dev/null 2>&1; then
    echo "BLOCKED: Cannot access credential files" >&2
    exit 2
  fi

  # Block reading terraform state (contains secrets)
  if echo "$FILE_PATH" | grep -iE 'terraform\.tfstate' > /dev/null 2>&1; then
    echo "BLOCKED: Cannot read terraform state — may contain secrets" >&2
    exit 2
  fi
fi

# ── Block writing secrets into code ───────────────────────────────────────────
if [ -n "$CONTENT" ]; then
  # Check if content being written contains API key patterns
  if echo "$CONTENT" | grep -iE '(sk-[a-zA-Z0-9]{20,}|AKIA[0-9A-Z]{16}|ghp_[a-zA-Z0-9]{36})' > /dev/null 2>&1; then
    echo "BLOCKED: Content appears to contain an API key or secret" >&2
    exit 2
  fi
fi

exit 0
