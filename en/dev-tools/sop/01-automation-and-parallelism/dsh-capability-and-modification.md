> 🌐 English translation · [中文原文](../../../../开发工具/SOP/01_自动化执行与并行/DSH能力与改造.md)

# DSH Capability Surface and How to Modify It

> How to write a dispatch is in [DSH dispatch](dsh-delegation.md); this page covers **what mechanisms DSH has, when to use which, and how to modify it**.
> Version `0.1.2-rc.1`. DSH can be modified per task — changing configuration, adding plugins, adding MCP are routine operations, not exceptions.
>
> ⚠ **All modification actions on this page are Claude-side work and cannot be dispatched to DSH.**
> DSH runs in the `workspace-write` sandbox and cannot write to `~/.dsh`.
> (DSH itself pointed this out while reviewing this document — following it, it would get stuck.)

## 1. What the default composition already has

| Mechanism | Status | When to use |
|---|---|---|
| `compaction-basic` | ✅ Attached | Automatically compacts old history when context reaches the threshold; nothing to manage |
| `tool-subagent` (spawn) | ✅ Attached | Delegate to a subagent with a **fresh context** — use when an independent perspective is needed |
| `tool-subagent-fork` | ✅ Attached | Delegate to a subagent that **inherits the parent's completed turns** — use to continue the work |
| `tool-subagent-control` | ✅ Attached | `send_message` / `interrupt_agent` / `list_agents` |
| `tool-workflow` | ✅ Attached | Lets the model write its own orchestration scripts to fan out subagents |
| goal family (`create_goal` etc.) | ✅ Attached | One long-term goal per session, held across turns |
| `plan-mode` | ✅ Attached | `/plan` enters/exits plan mode |
| `web_search` / `web_fetch` | ✅ Attached | DeepSeek's own search |
| `ralph` | ❌ Not attached | A loop with a fixed goal + a fresh subagent per round; add it first to use |
| spill / output-retention | ❌ Not attached | Offloads huge tool outputs, returning only a preview; add when needed |

## 2. ⚠ Measured: goals in headless mode **do not** automatically continue rounds

`goal-round-driver`'s condition for continuing is “whole machine idle + goal armed + quota remaining”,
but **headless exits after one round**. Measured by giving it a goal of “create one file per round, three total”:
it created the goal, wrote `r1.txt`, then wrapped up as `aborted`; no `r2/r3`.

**So do not count on goals in headless mode for unattended long tasks.** Three options:

| Route | Suited for | Cost |
|---|---|---|
| **Claude-side looped dispatch** (current default) | Most cases | Start/stop overhead each round, but each round's context is clean and verifiable |
| Add the `ralph` tool | One unchanging goal that needs grinding over many rounds | Blocks in the foreground until done; fresh subagent each round, **the working directory is the only memory** |
| `web` / `sdk` profile | Truly persistent sessions needed | Requires a separate client; `sdk` is JSON-RPC over stdio |

> `ralph`'s design naturally fits your SOP habits: only a bounded structured handoff report passes between rounds,
> and **the working directory serves as long-term memory** — i.e. the practice of writing `_工程状态.md` to disk every round.

## 3. ⚠ Configuration precedence: the settings document overrides composition

Hit once, with a very subtle symptom: `--dump-config` shows model A, but B actually runs.

```
composition (cordis.yml + profile patch + home patch + --patch overlay)
        ↑ overridden by the layer below
settings document (~/.dsh/settings.yaml) — read at runtime, no restart needed
```

**Consequence**: any field written into `settings.yaml` makes the corresponding `--patch` override **silently ineffective**.
So the default model is deliberately written in `~/.dsh/cordis.patch.yml`, not `settings.yaml`.

⚠ **Manually switching models in the web UI writes `agent-default-model` back to settings.yaml**,
after which `dsh_task.js --model` is overridden. `dsh_task.js`'s after-the-fact verification reports this as FAIL —
when you see “the model actually used does not match the requested one”, go to `settings.yaml` and delete that section.

## 4. How to write patches (writing them backwards does not error)

```yaml
- id: 已有行的id        # override an existing row
  config: { ... }

- insert:               # add new rows
    - id: 新行id
      name: '@deepseek-ai/dsh-xxx'
      config: { ... }

- id: 要停用的行id      # disable
  disabled: true
```

Putting an override inside `insert` does not error; you get **two rows with the same id** — that is exactly the mistake I made the first time.
After editing, self-check with `dsh-vrc --profile headless --dump-config | grep -c "^- id: 那个id"`; it should be 1.

Layer order: bundle layers → profile's `cordis.patch.yml` → home's `~/.dsh/cordis.patch.yml` → `--patch`.
**The home layer applies to all three profiles at once**; put shared wiring here.

## 5. Adding an MCP server = adding capability to DSH

One configuration entry is enough; tool names become `mcp__<serverName>__<tool>`, identical in name and form to Claude Code.
**Images returned by MCP enter the conversation as images under a vision model** — so Unity/Blender screenshots can be viewed directly.

Three are attached: `UnityMCP`, `Blender`, `agy`. To add a new one, copy the form in `~/.dsh/cordis.patch.yml`.

`failOnStartupError: false` is intentional: DSH must still be able to start and do other work when Unity is not open.
The cost is that **tools silently disappear when the connection fails**; the task brief should say “if there is no X tool, report NO-X-TOOLS directly”,
so that “the tool was not attached” can be distinguished from “it lazily did not call it”.

## 6. agy integration: turning third-party falsification into a tool

`通用工具/agy_mcp_server.js` wraps agy as MCP; DSH and Claude **share the same server on both sides**.

| Tool | Purpose |
|---|---|
| `mcp__agy__agy_review` | Multi-model cross-falsification. `mode`: `fast` single-model quick review / `panel` 3 models / `wide` 5 models |
| `mcp__agy__agy_ask` | Single strong-model Q&A (interpretation/comparison/trade-offs); can mount read-only directories and context files |

**Why make it a tool** (user decision 2026-09-08):
once context gets long, calling agy gets forgotten; **this is not a memory problem but a structural problem of “it is not in the tool list”**.
Once it is a tool, the model sees it every turn. To make it harder, use `dsh-hooks-claude-code`
to force-trigger with hooks at fixed gates — that is a deterministic action, not dependent on the model's discipline.

⚠ Three usage constraints (all written into the tool descriptions, visible to the model):
- Images hit agy's ~185s internal timeout → the server **automatically downscales images with a long side >1600px proportionally**
- agy refuses wording like “vulnerability scan/security audit” → always write “quality review”
- **Review models misidentify objects** (measured: took an earring for a leftover halo piece) → the location it points to is more credible than its conclusion; review each item yourself

Measured: DSH called `agy_review` at the fast tier, returned 3 blockers in 72 seconds, correctly identified.

## 7. Not yet used, but worth knowing

- **`fork`-type subagents**: inherit the parent's completed turns. Suited for “another model continuing to look at the same pile of evidence”.
- **`session-reference`**: cross-session snapshot references; can feed another session's conclusions in as context.
- **`schedule`**: persistent in-session reminders (`schedule_create` / `list` / `delete`).
- **`repeat-tool-reminder`**: detects repeated identical tool calls and reminds it to change approach.
- **`spill`**: offloads huge tool outputs to storage, keeping only a preview and a retrieval locator in context — worth adding when scanning large projects.

## Environment facts

Sync this section whenever the environment changes.

| Item | Value |
|---|---|
| Version | `@deepseek-ai/dsh@0.1.2-rc.1`, installed in isolation at `~/.local/opt/dsh-0.1.2-rc.1`, command `dsh-vrc`. ⚠ The global `dsh` (~/.npm-global) is a different version used by the dsh.service web frontend, home directory `~/harness/home`; do not mix them |
| Config root | `~/.dsh`; credentials `~/.dsh/.credentials.yaml` (**not in environment variables**) |
| **Default model** | The `agent-default-model` row in **`~/.dsh/cordis.patch.yml`** → `deepseek-flash`, effort `high` (image dispatches are overridden by dsh_task.js `--model vision`). ⚠ **Not** settings.yaml; reason in section 3 |
| Shared wiring | `~/.dsh/cordis.patch.yml` — MCP: `UnityMCP` / `Blender` / `agy`, applies to all three profiles |
| profile | `headless` (main dispatch workhorse) · `sdk` (JSON-RPC, backup) |
| Web service | On this machine (Linux) it is the systemd user service `dsh.service` (global dsh, `~/harness/home`), **not the one used for model editing**; model-editing dispatches only go through headless |
| Skills directory | `~/.dsh/skills`. Format `<name>/SKILL.md` or `<name>.md`; **must have YAML frontmatter with name + description**, otherwise silently dropped |
| Sandbox | `workspace-write`, `workspaceRoot` = the cwd passed in; `DSH_PERMISSION_MODE` can override |

⚠ **Do not add `--offline` to UnityMCP**: when the uv cache lacks a wheel it “fails closed”,
the log floods with `Failed to download`, and the tools silently disappear. Without it, it fills the cache from the network automatically.

---

Related: [DSH dispatch](dsh-delegation.md), [Subagent prompts](subagent-prompts.md), [05 multi-model review procedure](../05-multi-model-review.md).

## DSH dispatching DSH (nested dispatch): `~/.dsh` is read-only inside the sandbox (09-22 H-03 wrap-up)

**Trigger**: the task brief has DSH itself run `dsh_task.js` again (e.g. opening a vision sub-session per part).
**Phenomenon**: the outer DSH's sandbox mounts `~/.dsh` read-only, and the inner `dsh_task.js` cannot start (profile EROFS). DSH can get it running by working around with `HOME=<临时目录> DSH_BIN=<dsh 绝对路径>`, but the wrap-up verification fails to claim the session in the real `~/.dsh` ⇒ judged FAIL (false FAIL).
**Practice**: the nested-dispatch task brief spells out this workaround and requires it to **manually read `<临时>/.dsh/sessions/**.zstd` to verify the model and `read_image`** and paste that into the report; during acceptance look at this verification, not just the exit code.
**Trade-off**: nested dispatch saves Claude usage (vision sessions are opened by DSH itself), at the cost of one extra manual verification step.
Addendum (H-04 three-route measurement): `dsh_task.js` clears the child process's `DSH_HOME`, so besides redirecting `HOME` you must also set `DSH_BIN` explicitly (otherwise `os.homedir()` changes and points to the wrong binary); credentials are copied into the shadow HOME, **which must be deleted at task wrap-up**.
Addendum (fixed 09-22 22:40, re-verified in H-05): the root cause of the false FAIL was that `dsh_task.js` looked for sessions by the inherited `DSH_HOME` while the child process wrote sessions under the shadow `HOME`; it now claims by the child process's `$HOME/.dsh/sessions`, and in H-05 nested claiming succeeded 28/28 ([DSH execution notes](../50-outfit-and-hair-assembly/part-understanding-and-menu-layout/dsh-execution-points.md)). The manual verification above is downgraded to a fallback for when verification still reports exit code 2.

> → [Sandbox limits](dsh-capability-and-modification/sandbox-limits.md) — background processes started by DSH are killed with the session (long batch jobs are started by Claude); there is no GPU in the sandbox (renders/GPU work run by Claude outside the sandbox); `/tmp` in bash is a new empty directory per command (put intermediate products in the workspace).
