# Extend Claude Code — Features Overview

> Source: https://code.claude.com/docs/en/features-overview.md

> Understand when to use CLAUDE.md, Skills, subagents, hooks, MCP, and plugins.

---

## Overview

Extensions plug into different parts of the agentic loop:

* **CLAUDE.md** — persistent context Claude sees every session
* **Skills** — reusable knowledge and invocable workflows
* **MCP** — connects Claude to external services and tools
* **Subagents** — run their own loops in isolated context, returning summaries
* **Agent teams** — coordinate multiple independent sessions with shared tasks and messaging
* **Hooks** — run outside the loop as deterministic scripts
* **Plugins** — package and distribute features

## Match features to your goal

| Feature           | What it does                                               | When to use it                                    | Example                                        |
| ----------------- | ---------------------------------------------------------- | ------------------------------------------------- | ---------------------------------------------- |
| **CLAUDE.md**     | Persistent context loaded every conversation               | Project conventions, "always do X" rules          | "Use pnpm, not npm. Run tests before committing." |
| **Skill**         | Instructions, knowledge, and workflows Claude can use      | Reusable content, reference docs, repeatable tasks | `/review` runs your code review checklist       |
| **Subagent**      | Isolated execution context that returns summarized results | Context isolation, parallel tasks, specialized workers | Research task that returns only key findings   |
| **Agent teams**   | Coordinate multiple independent Claude Code sessions       | Parallel research, new features, debugging        | Spawn reviewers for security, perf, tests       |
| **MCP**           | Connect to external services                               | External data or actions                          | Query DB, post to Slack, control browser        |
| **Hook**          | Deterministic script that runs on events                   | Predictable automation, no LLM involved           | Run ESLint after every file edit                |

**Plugins** bundle skills, hooks, subagents, and MCP servers into a single installable unit.

---

## Compare similar features

### Skill vs Subagent

| Aspect          | Skill                                          | Subagent                                           |
| --------------- | ---------------------------------------------- | -------------------------------------------------- |
| **What it is**  | Reusable instructions, knowledge, or workflows | Isolated worker with its own context               |
| **Key benefit** | Share content across contexts                  | Context isolation; only summary returns            |
| **Best for**    | Reference material, invocable workflows        | Tasks reading many files, parallel work            |

They combine: subagents can preload skills (`skills:` field). Skills can run in isolated context (`context: fork`).

### CLAUDE.md vs Skill

| Aspect                    | CLAUDE.md                    | Skill                                   |
| ------------------------- | ---------------------------- | --------------------------------------- |
| **Loads**                 | Every session, automatically | On demand                               |
| **Can trigger workflows** | No                           | Yes, with `/<name>`                     |
| **Best for**              | "Always do X" rules          | Reference material, invocable workflows |

**Rule of thumb:** Keep CLAUDE.md under ~500 lines. Move reference content to skills.

### Subagent vs Agent team

| Aspect            | Subagent                                 | Agent team                                          |
| ----------------- | ---------------------------------------- | --------------------------------------------------- |
| **Context**       | Results return to the caller             | Fully independent                                   |
| **Communication** | Reports back to the main agent only      | Teammates message each other directly               |
| **Coordination**  | Main agent manages all work              | Shared task list with self-coordination             |
| **Token cost**    | Lower                                    | Higher (each is a separate Claude instance)         |

### MCP vs Skill

| Aspect         | MCP                                  | Skill                                     |
| -------------- | ------------------------------------ | ----------------------------------------- |
| **What it is** | Protocol for external services       | Knowledge, workflows, reference material  |
| **Provides**   | Tools and data access                | Knowledge, workflows                      |

They work together: MCP provides the connection, a skill teaches Claude how to use it.

---

## How features layer

* **CLAUDE.md files**: additive — all levels contribute content
* **Skills and subagents**: override by name (managed > user > project)
* **MCP servers**: override by name (local > project > user)
* **Hooks**: merge — all registered hooks fire for matching events

---

## Combine features

| Pattern                | How it works                                                          |
| ---------------------- | --------------------------------------------------------------------- |
| **Skill + MCP**        | MCP provides connection; skill teaches how to use it                  |
| **Skill + Subagent**   | Skill spawns subagents for parallel work                              |
| **CLAUDE.md + Skills** | CLAUDE.md for always-on rules; skills for on-demand reference         |
| **Hook + MCP**         | Hook triggers external actions through MCP                            |

---

## Context cost by feature

| Feature         | When it loads             | Context cost                                 |
| --------------- | ------------------------- | -------------------------------------------- |
| **CLAUDE.md**   | Session start             | Every request                                |
| **Skills**      | Session start + when used | Low (descriptions every request)             |
| **MCP servers** | Session start             | Every request                                |
| **Subagents**   | When spawned              | Isolated from main session                   |
| **Hooks**       | On trigger                | Zero (unless hook returns context)           |
