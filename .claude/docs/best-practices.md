# Best Practices for Claude Code

> Source: https://code.claude.com/docs/en/best-practices.md

> Tips and patterns for getting the most out of Claude Code, from configuring your environment to scaling across parallel sessions.

Most best practices are based on one constraint: **Claude's context window fills up fast, and performance degrades as it fills.** Track context usage continuously with a custom status line.

---

## Give Claude a way to verify its work

> **💡 Tip:** Include tests, screenshots, or expected outputs so Claude can check itself. This is the single highest-leverage thing you can do.

| Strategy                              | Before                                  | After                                                                                          |
| ------------------------------------- | --------------------------------------- | ---------------------------------------------------------------------------------------------- |
| **Provide verification criteria**     | "implement a function that validates email addresses" | "write a validateEmail function with test cases. run the tests after implementing" |
| **Verify UI changes visually**        | "make the dashboard look better"        | "[paste screenshot] implement this design. take a screenshot and compare"                      |
| **Address root causes, not symptoms** | "the build is failing"                  | "the build fails with this error: [paste]. fix it and verify the build succeeds"              |

---

## Explore first, then plan, then code

> **💡 Tip:** Separate research and planning from implementation to avoid solving the wrong problem.

1. **Explore**: Enter Plan Mode. Claude reads files without making changes.
2. **Plan**: Ask Claude to create a detailed implementation plan. Press `Ctrl+G` to edit the plan in your editor.
3. **Implement**: Switch back to Normal Mode. Let Claude code and verify.
4. **Commit**: Ask Claude to commit with a descriptive message and create a PR.

Skip planning for small, clear-scoped tasks (typos, log lines, renames).

---

## Provide specific context in your prompts

> **💡 Tip:** The more precise your instructions, the fewer corrections you'll need.

| Strategy                    | Before                               | After                                                                                       |
| --------------------------- | ------------------------------------ | ------------------------------------------------------------------------------------------- |
| **Scope the task**          | "add tests for foo.py"               | "write a test for foo.py covering the edge case where the user is logged out. avoid mocks." |
| **Point to sources**        | "why does the API have a weird api?" | "look through the git history and summarize how its API came to be"                         |
| **Reference existing patterns** | "add a calendar widget"          | "look at how existing widgets are implemented. HotDogWidget.php is a good example."         |
| **Describe the symptom**    | "fix the login bug"                  | "users report login fails after session timeout. check src/auth/. write a failing test"     |

---

## Configure your environment

### Write an effective CLAUDE.md

Run `/init` to generate a starter CLAUDE.md file. Include Bash commands, code style, and workflow rules.

| ✅ Include                                            | ❌ Exclude                                          |
| ---------------------------------------------------- | -------------------------------------------------- |
| Bash commands Claude can't guess                     | Anything Claude can figure out by reading code     |
| Code style rules that differ from defaults           | Standard language conventions                      |
| Testing instructions and preferred test runners      | Detailed API documentation (link instead)          |
| Repository etiquette (branch naming, PR conventions) | Information that changes frequently                |
| Architectural decisions specific to your project     | Long explanations or tutorials                     |
| Common gotchas or non-obvious behaviors              | Self-evident practices                             |

CLAUDE.md files can import additional files using `@path/to/import` syntax.

Locations: `~/.claude/CLAUDE.md` (global), `./CLAUDE.md` (project), parent directories, child directories.

### Configure permissions

Use `/permissions` to allowlist safe commands or `/sandbox` for OS-level isolation.

### Use CLI tools

Tell Claude Code to use CLI tools like `gh`, `aws`, `gcloud`, `sentry-cli`.

### Connect MCP servers

Run `claude mcp add` to connect external tools like Notion, Figma, or your database.

### Set up hooks

Hooks run scripts automatically at specific points in Claude's workflow. Unlike CLAUDE.md instructions which are advisory, hooks are deterministic.

### Create skills

Create `SKILL.md` files in `.claude/skills/` to give Claude domain knowledge and reusable workflows.

```markdown
---
name: api-conventions
description: REST API design conventions for our services
---
# API Conventions
- Use kebab-case for URL paths
- Use camelCase for JSON properties
- Always include pagination for list endpoints
```

Skills can also define repeatable workflows invoked with `/skill-name`.

### Create custom subagents

Define specialized assistants in `.claude/agents/` that Claude can delegate to.

### Install plugins

Run `/plugin` to browse the marketplace.

---

## Communicate effectively

### Ask codebase questions

Ask Claude the same questions you'd ask another engineer:
* How does logging work?
* How do I make a new API endpoint?
* What edge cases does `CustomerOnboardingFlowImpl` handle?

### Let Claude interview you

For larger features, have Claude interview you first:

```
I want to build [brief description]. Interview me in detail using the AskUserQuestion tool.
Ask about technical implementation, UI/UX, edge cases, concerns, and tradeoffs.
Keep interviewing until we've covered everything, then write a complete spec to SPEC.md.
```

---

## Manage your session

### Course-correct early and often

* **`Esc`**: Stop Claude mid-action
* **`Esc + Esc`** or **`/rewind`**: Open rewind menu
* **`"Undo that"`**: Revert changes
* **`/clear`**: Reset context between unrelated tasks

After two failed corrections, `/clear` and start with a better prompt.

### Manage context aggressively

* Use `/clear` frequently between tasks
* Run `/compact <instructions>` for selective compaction
* Use `Esc + Esc` → **Summarize from here** for partial compaction
* Customize compaction in CLAUDE.md

### Use subagents for investigation

```
Use subagents to investigate how our authentication system handles token
refresh, and whether we have any existing OAuth utilities I should reuse.
```

### Rewind with checkpoints

Every action creates a checkpoint. Double-tap `Escape` or run `/rewind`.

### Resume conversations

```bash
claude --continue    # Resume the most recent conversation
claude --resume      # Select from recent conversations
```

Use `/rename` to give sessions descriptive names.

---

## Automate and scale

### Run headless mode

```bash
claude -p "Explain what this project does"
claude -p "List all API endpoints" --output-format json
claude -p "Analyze this log file" --output-format stream-json
```

### Run multiple Claude sessions

* **Desktop app**: Manage multiple local sessions visually
* **Claude Code on the web**: Run on secure cloud infrastructure
* **Agent teams**: Automated coordination with shared tasks

**Writer/Reviewer pattern**: One session implements, another reviews with fresh context.

### Fan out across files

```bash
for file in $(cat files.txt); do
  claude -p "Migrate $file from React to Vue. Return OK or FAIL." \
    --allowedTools "Edit,Bash(git commit *)"
done
```

### Safe Autonomous Mode

Use `claude --dangerously-skip-permissions` only in sandboxed environments. Prefer `/sandbox` for OS-level isolation with better security.

---

## Avoid common failure patterns

| Pattern | Fix |
| ------- | --- |
| **Kitchen sink session** (mixing unrelated tasks) | `/clear` between tasks |
| **Correcting over and over** | After 2 failures, `/clear` and write better initial prompt |
| **Over-specified CLAUDE.md** | Ruthlessly prune. Convert to hooks if needed |
| **Trust-then-verify gap** | Always provide verification (tests, scripts, screenshots) |
| **Infinite exploration** | Scope narrowly or use subagents |

---

## Develop your intuition

Pay attention to what works. Notice prompt structure, context provided, and mode when Claude produces great output. Over time, you'll know when to be specific vs open-ended, when to plan vs explore, and when to clear vs accumulate context.
