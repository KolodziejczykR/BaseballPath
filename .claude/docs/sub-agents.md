# Create custom subagents

> Source: https://code.claude.com/docs/en/sub-agents.md

> Create and use specialized AI subagents in Claude Code for task-specific workflows and improved context management.

Subagents are specialized AI assistants that handle specific types of tasks. Each subagent runs in its own context window with a custom system prompt, specific tool access, and independent permissions. When Claude encounters a task that matches a subagent's description, it delegates to that subagent, which works independently and returns results.

> **Note:** If you need multiple agents working in parallel and communicating with each other, see agent teams instead. Subagents work within a single session; agent teams coordinate across separate sessions.

Subagents help you:

* **Preserve context** by keeping exploration and implementation out of your main conversation
* **Enforce constraints** by limiting which tools a subagent can use
* **Reuse configurations** across projects with user-level subagents
* **Specialize behavior** with focused system prompts for specific domains
* **Control costs** by routing tasks to faster, cheaper models like Haiku

---

## Built-in subagents

Claude Code includes built-in subagents that Claude automatically uses when appropriate:

### Explore
A fast, read-only agent optimized for searching and analyzing codebases.
* **Model**: Haiku (fast, low-latency)
* **Tools**: Read-only tools (denied access to Write and Edit tools)
* **Purpose**: File discovery, code search, codebase exploration

When invoking Explore, Claude specifies a thoroughness level: **quick** for targeted lookups, **medium** for balanced exploration, or **very thorough** for comprehensive analysis.

### Plan
A research agent used during plan mode to gather context before presenting a plan.
* **Model**: Inherits from main conversation
* **Tools**: Read-only tools (denied access to Write and Edit tools)
* **Purpose**: Codebase research for planning

### General-purpose
A capable agent for complex, multi-step tasks that require both exploration and action.
* **Model**: Inherits from main conversation
* **Tools**: All tools
* **Purpose**: Complex research, multi-step operations, code modifications

### Other built-in agents

| Agent             | Model    | When Claude uses it                                      |
| :---------------- | :------- | :------------------------------------------------------- |
| Bash              | Inherits | Running terminal commands in a separate context          |
| statusline-setup  | Sonnet   | When you run `/statusline` to configure your status line |
| Claude Code Guide | Haiku    | When you ask questions about Claude Code features        |

---

## Quickstart: create your first subagent

1. **Open the subagents interface**: Run `/agents`
2. **Create a new user-level agent**: Select **Create new agent** → **User-level** (saves to `~/.claude/agents/`)
3. **Generate with Claude**: Select **Generate with Claude**, then describe the subagent
4. **Select tools**: Choose which tools the subagent can access
5. **Select model**: Choose which model the subagent uses
6. **Choose a color**: Pick a background color for identification
7. **Save and try it out**: Available immediately (no restart needed)

---

## Configure subagents

### Use the /agents command

The `/agents` command provides an interactive interface for managing subagents. Run `/agents` to:
* View all available subagents (built-in, user, project, and plugin)
* Create, edit, delete custom subagents
* See which subagents are active when duplicates exist

To list all configured subagents from the command line: `claude agents`

### Choose the subagent scope

| Location                     | Scope                   | Priority    | How to create                         |
| :--------------------------- | :---------------------- | :---------- | :------------------------------------ |
| `--agents` CLI flag          | Current session         | 1 (highest) | Pass JSON when launching Claude Code  |
| `.claude/agents/`            | Current project         | 2           | Interactive or manual                 |
| `~/.claude/agents/`          | All your projects       | 3           | Interactive or manual                 |
| Plugin's `agents/` directory | Where plugin is enabled | 4 (lowest)  | Installed with plugins                |

**CLI-defined subagents** example:

```bash
claude --agents '{
  "code-reviewer": {
    "description": "Expert code reviewer. Use proactively after code changes.",
    "prompt": "You are a senior code reviewer. Focus on code quality, security, and best practices.",
    "tools": ["Read", "Grep", "Glob", "Bash"],
    "model": "sonnet"
  }
}'
```

### Write subagent files

Subagent files use YAML frontmatter for configuration, followed by the system prompt in Markdown:

```markdown
---
name: code-reviewer
description: Reviews code for quality and best practices
tools: Read, Glob, Grep
model: sonnet
---

You are a code reviewer. When invoked, analyze the code and provide
specific, actionable feedback on quality, security, and best practices.
```

#### Supported frontmatter fields

| Field             | Required | Description                                                          |
| :---------------- | :------- | :------------------------------------------------------------------- |
| `name`            | Yes      | Unique identifier using lowercase letters and hyphens                |
| `description`     | Yes      | When Claude should delegate to this subagent                         |
| `tools`           | No       | Tools the subagent can use. Inherits all tools if omitted            |
| `disallowedTools` | No       | Tools to deny, removed from inherited or specified list              |
| `model`           | No       | `sonnet`, `opus`, `haiku`, or `inherit`. Defaults to `inherit`       |
| `permissionMode`  | No       | `default`, `acceptEdits`, `dontAsk`, `bypassPermissions`, or `plan`  |
| `maxTurns`        | No       | Maximum number of agentic turns before the subagent stops            |
| `skills`          | No       | Skills to load into the subagent's context at startup                |
| `mcpServers`      | No       | MCP servers available to this subagent                               |
| `hooks`           | No       | Lifecycle hooks scoped to this subagent                              |
| `memory`          | No       | Persistent memory scope: `user`, `project`, or `local`               |
| `background`      | No       | Set to `true` to always run as a background task                     |
| `isolation`       | No       | Set to `worktree` to run in a temporary git worktree                 |

### Choose a model

* **Model alias**: `sonnet`, `opus`, or `haiku`
* **inherit**: Use the same model as the main conversation (default)

### Control subagent capabilities

#### Permission modes

| Mode                | Behavior                                                           |
| :------------------ | :----------------------------------------------------------------- |
| `default`           | Standard permission checking with prompts                          |
| `acceptEdits`       | Auto-accept file edits                                             |
| `dontAsk`           | Auto-deny permission prompts (explicitly allowed tools still work) |
| `bypassPermissions` | Skip all permission checks                                         |
| `plan`              | Plan mode (read-only exploration)                                  |

#### Enable persistent memory

The `memory` field gives the subagent persistent storage across conversations:

| Scope     | Location                                      | Use when                                                   |
| :-------- | :-------------------------------------------- | :--------------------------------------------------------- |
| `user`    | `~/.claude/agent-memory/<name-of-agent>/`     | Should remember learnings across all projects              |
| `project` | `.claude/agent-memory/<name-of-agent>/`       | Knowledge is project-specific and shareable via VCS        |
| `local`   | `.claude/agent-memory-local/<name-of-agent>/` | Knowledge is project-specific but should not be in VCS     |

#### Disable specific subagents

```json
{
  "permissions": {
    "deny": ["Task(Explore)", "Task(my-custom-agent)"]
  }
}
```

### Define hooks for subagents

**In the subagent's frontmatter:**

```yaml
---
name: code-reviewer
description: Review code changes with automatic linting
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "./scripts/validate-command.sh $TOOL_INPUT"
  PostToolUse:
    - matcher: "Edit|Write"
      hooks:
        - type: command
          command: "./scripts/run-linter.sh"
---
```

**In `settings.json`** for project-level hooks:

```json
{
  "hooks": {
    "SubagentStart": [
      {
        "matcher": "db-agent",
        "hooks": [
          { "type": "command", "command": "./scripts/setup-db-connection.sh" }
        ]
      }
    ]
  }
}
```

---

## Work with subagents

### Automatic delegation

Claude automatically delegates tasks based on descriptions. Include "use proactively" in your description for automatic delegation. You can also request a specific subagent explicitly:

```
Use the test-runner subagent to fix failing tests
Have the code-reviewer subagent look at my recent changes
```

### Foreground vs background

* **Foreground**: blocks the main conversation until complete
* **Background**: runs concurrently. Press **Ctrl+B** to background a running task.

### Common patterns

* **Isolate high-volume operations**: delegate tests, docs, logs to subagents
* **Run parallel research**: spawn multiple subagents for independent investigations
* **Chain subagents**: use subagents in sequence for multi-step workflows

### When to use subagents vs main conversation

**Main conversation** when:
* Frequent back-and-forth needed
* Multiple phases share context
* Quick, targeted changes
* Latency matters

**Subagents** when:
* Task produces verbose output
* Need specific tool restrictions
* Work is self-contained

---

## Example subagents

### Code reviewer

```markdown
---
name: code-reviewer
description: Expert code review specialist. Use immediately after writing or modifying code.
tools: Read, Grep, Glob, Bash
model: inherit
---

You are a senior code reviewer ensuring high standards of code quality and security.

When invoked:
1. Run git diff to see recent changes
2. Focus on modified files
3. Begin review immediately

Review checklist:
- Code is clear and readable
- No duplicated code
- Proper error handling
- No exposed secrets
- Good test coverage

Provide feedback by priority: Critical → Warnings → Suggestions
```

### Debugger

```markdown
---
name: debugger
description: Debugging specialist for errors, test failures, and unexpected behavior.
tools: Read, Edit, Bash, Grep, Glob
---

You are an expert debugger specializing in root cause analysis.

When invoked:
1. Capture error message and stack trace
2. Identify reproduction steps
3. Isolate the failure location
4. Implement minimal fix
5. Verify solution works
```

### Data scientist

```markdown
---
name: data-scientist
description: Data analysis expert for SQL queries and data insights.
tools: Bash, Read, Write
model: sonnet
---

You are a data scientist specializing in SQL and data analysis.
Write optimized SQL queries, analyze results, and present findings clearly.
```

### Database query validator

```markdown
---
name: db-reader
description: Execute read-only database queries.
tools: Bash
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "./scripts/validate-readonly-query.sh"
---

You are a database analyst with read-only access. Execute SELECT queries to answer questions about the data.
```

---

## Next steps

* Distribute subagents with plugins to share across teams or projects
* Run Claude Code programmatically with the Agent SDK for CI/CD
* Use MCP servers to give subagents access to external tools and data
