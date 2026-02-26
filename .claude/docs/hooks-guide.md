# Automate workflows with hooks

> Source: https://code.claude.com/docs/en/hooks-guide.md

> Run shell commands automatically when Claude Code edits files, finishes tasks, or needs input.

Hooks are user-defined shell commands that execute at specific points in Claude Code's lifecycle. They provide deterministic control over behavior, ensuring certain actions always happen.

---

## Set up your first hook

1. Type `/hooks` in the Claude Code CLI
2. Select `Notification` event
3. Set matcher to `*` for all notification types
4. Add your command (e.g., macOS notification):
```
osascript -e 'display notification "Claude Code needs your attention" with title "Claude Code"'
```
5. Choose `User settings` (applies to all projects)

---

## What you can automate

### Get notified when Claude needs input

```json
{
  "hooks": {
    "Notification": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "osascript -e 'display notification \"Claude Code needs your attention\" with title \"Claude Code\"'"
          }
        ]
      }
    ]
  }
}
```

### Auto-format code after edits

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "jq -r '.tool_input.file_path' | xargs npx prettier --write"
          }
        ]
      }
    ]
  }
}
```

### Block edits to protected files

Create `.claude/hooks/protect-files.sh`:

```bash
#!/bin/bash
INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

PROTECTED_PATTERNS=(".env" "package-lock.json" ".git/")

for pattern in "${PROTECTED_PATTERNS[@]}"; do
  if [[ "$FILE_PATH" == *"$pattern"* ]]; then
    echo "Blocked: $FILE_PATH matches protected pattern '$pattern'" >&2
    exit 2
  fi
done
exit 0
```

Register it:
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/protect-files.sh"
          }
        ]
      }
    ]
  }
}
```

### Re-inject context after compaction

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "compact",
        "hooks": [
          {
            "type": "command",
            "command": "echo 'Reminder: use Bun, not npm. Run bun test before committing.'"
          }
        ]
      }
    ]
  }
}
```

---

## How hooks work

### Hook events

| Event                | When it fires                                           |
| :------------------- | :------------------------------------------------------ |
| `SessionStart`       | When a session begins or resumes                        |
| `UserPromptSubmit`   | When you submit a prompt                                |
| `PreToolUse`         | Before a tool call executes. Can block it               |
| `PermissionRequest`  | When a permission dialog appears                        |
| `PostToolUse`        | After a tool call succeeds                              |
| `PostToolUseFailure` | After a tool call fails                                 |
| `Notification`       | When Claude Code sends a notification                   |
| `SubagentStart`      | When a subagent is spawned                              |
| `SubagentStop`       | When a subagent finishes                                |
| `Stop`               | When Claude finishes responding                         |
| `TeammateIdle`       | When a teammate is about to go idle                     |
| `TaskCompleted`      | When a task is marked complete                          |
| `ConfigChange`       | When a config file changes during session               |
| `WorktreeCreate`     | When a worktree is being created                        |
| `WorktreeRemove`     | When a worktree is being removed                        |
| `PreCompact`         | Before context compaction                               |
| `SessionEnd`         | When a session terminates                               |

### Hook types

* `"type": "command"` — runs a shell command (most common)
* `"type": "prompt"` — sends to a Claude model for yes/no decision
* `"type": "agent"` — spawns a subagent that can read files and run tools

### Input and output

Hooks receive event-specific JSON on stdin. Example `PreToolUse` input:

```json
{
  "session_id": "abc123",
  "cwd": "/Users/sarah/myproject",
  "hook_event_name": "PreToolUse",
  "tool_name": "Bash",
  "tool_input": { "command": "npm test" }
}
```

Exit codes:
* **Exit 0**: action proceeds. stdout added to context for some events.
* **Exit 2**: action blocked. stderr becomes Claude's feedback.
* **Other**: action proceeds. stderr logged but not shown to Claude.

### Filter with matchers

Without a matcher, hooks fire on every event occurrence. Matchers use regex to filter:

```json
{
  "matcher": "Edit|Write",
  "hooks": [{ "type": "command", "command": "prettier --write ..." }]
}
```

### Configure hook location

| Location                          | Scope         | Shareable |
| :-------------------------------- | :------------ | :-------- |
| `~/.claude/settings.json`        | All projects  | No        |
| `.claude/settings.json`          | Single project| Yes       |
| `.claude/settings.local.json`    | Single project| No        |
| Plugin `hooks/hooks.json`        | Plugin scope  | Yes       |
| Skill/agent frontmatter          | While active  | Yes       |

---

## Prompt-based hooks

For decisions requiring judgment, use `type: "prompt"`:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "prompt",
            "prompt": "Check if all tasks are complete. If not, respond with {\"ok\": false, \"reason\": \"what remains\"}."
          }
        ]
      }
    ]
  }
}
```

## Agent-based hooks

When verification requires inspecting files or running commands:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "agent",
            "prompt": "Verify that all unit tests pass. Run the test suite and check the results.",
            "timeout": 120
          }
        ]
      }
    ]
  }
}
```

---

## Troubleshooting

* **Hook not firing**: Check `/hooks`, verify matcher case-sensitivity, confirm correct event type
* **Hook error**: Test manually: `echo '{"tool_name":"Bash"}' | ./my-hook.sh`
* **Stop hook runs forever**: Check `stop_hook_active` field and exit 0 if true
* **JSON validation failed**: Wrap echo statements in shell profile with `if [[ $- == *i* ]]`
* **Debug**: Toggle verbose mode with `Ctrl+O` or run `claude --debug`
