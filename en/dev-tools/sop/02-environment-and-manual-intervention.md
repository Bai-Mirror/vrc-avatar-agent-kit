> 🌐 English translation · [中文原文](../../../开发工具/SOP/02_环境准备与人工介入.md)

# 02 · Environment Preparation and Manual Intervention　🤖 + 🔒

> **The starting point of all automation. Any stage that needs Unity goes through this page first.**
> The core is two things: **confirming Unity and MCP are really usable**, and
> **when they are not, how to correctly ask a human for help** (rather than blindly trying or polling until timeout).

Creating a project from scratch and fixing a failed first compile → [Project setup and first compile](02-environment-and-manual-intervention/project-setup-and-first-compile.md) (not needed day to day).
**This machine's (this machine (Linux) Linux) paths, launch commands and Linux editor-specific pitfalls** → [This machine (Linux) Linux environment](02-environment-and-manual-intervention/b850-linux-environment.md) (read before opening Unity/Blender for the first time after changing machines).

---

## 1. Is MCP working: check along this ladder, do not skip steps

**Every rung has a clear next step. When you reach “needs a human”, stop and ask for help; do not keep trying.**

| # | Symptom | How to judge | Handling |
|---|---|---|---|
| 1 | Reports `No Unity Editor instances found` | —— | **Retry once first.** Getting this on the first call after a restart / recompile is **normal**; the client needs a beat to reconnect. ⚠ This one has been misjudged before; do not go straight to a human on this basis |
| 2 | Retry still fails | Check whether the Unity process exists | Not there → **start Unity yourself** (authorized), then return to rung 1 |
| 3 | Process exists, but calls time out | Read `play_mode.is_playing` from the editor state | `true` → **a human is in Play mode**. During Play **scripts are not compiled**, and `.cs` changes never take effect → ask the human to exit per section 3 |
| 4 | Process exists, not in Play, still not working | Check whether a domain reload / asset import is in progress | Yes → **wait**. Refresh calls timing out but completing afterwards is common; judge by the dll timestamp |
| 5 | Panel shows green `Configured`, but **there are no tools at all** | Compare the panel's `Client Project Dir` with **this session's launch directory** | Mismatch → per section 3 ask a human to change the panel and **restart the session**. This is the one most easily misjudged as “MCP is broken” |
| 6 | All of the above ruled out | —— | Ask a human per section 3, reporting what has been ruled out as well |

### About Stdio

On first use, `Transport` must be set to **Stdio** in the `Window → MCP for Unity` panel (the default is HTTP).
**Once selected it persists**; after that cold starts connect automatically, no need to click each time.

`AutoStartOnLoad` in the panel's Advanced section **only applies to HTTP**; under stdio it does nothing, so leave it alone.

---

## 2. Three things explicitly “not to do”

**① Do not hand-edit client configuration files.**
Unity rewrites them on every startup according to its own transport mode. **The Unity-side settings are authoritative.**

**② Do not click Configure next to the yellow "Transport Mismatch" text in the panel.**
It rewrites the client configuration and may wipe out the one that was working.

**③ `execute_code` only does short, idempotent reads or value sets; long, non-idempotent writes go through “menu + request file”.**
(In the old Windows machine era Roslyn was not installed and CodeDom had a BOM bug, so it was banned entirely; on this machine (Linux) codedom works and it was opened up from 2026-09-19, but with the hard restriction below.)
**After an MCP call times out (`Timeout receiving Unity response`), the same code gets sent several more times**: on 2026-09-19 in Project A one `DepCompiler.Run(apply)` timed out, and over a 4-minute round it executed **4 times** in total, growing the FX controller from 125 KB → 38 MB (4 copies of each `Decl:` layer, 28,000 transitions).
- Checkable question: “Does this code give the same result if run twice? Can it finish within a few seconds?” — only use `execute_code` if both are “yes”.
- Otherwise: write it as an Editor menu inside the project that reads `Library/…/request.json`, executes across frames, and writes `status.json` (following the request pattern of `AuditIO`); `execute_menu_item` triggers it and returns immediately, and you wait for the result by polling the status file.
- Already timed out: first check the Unity log for the same operation repeating (timestamps appearing in clusters); **do not send a second call**; after confirming it is your own generated output, stop Unity, restore the generated output with `git checkout`, and delete newly added products.

> Also: when changing component properties on a prefab instance, **you must explicitly call
> `PrefabUtility.RecordPrefabInstancePropertyModifications()`**,
> otherwise the override is lost. The component interface wrapped by MCP misses this step.

> **⚠ When shortening an array property, element overrides beyond the new length are not cleared automatically** (measured 2026-09-21 in Project B).
> After changing `sharedMaterials` from 4 to 3, the override of `m_Materials.Array.size` did become 3,
> but the override `m_Materials.Array.data[3]` was **still there**, still pointing to a material that should have been removed —
> invisible in the Inspector; only `grep <old guid> scene.unity` revealed it (1 leftover).
> It breaks judgments of “is this asset still referenced by anyone”, and may resurrect the old value if the array grows longer later.
> **Criterion**: after changing the array length, `grep -c <guid of old reference>` on the scene file should drop to 0.
> **Fix**: get all overrides with `PrefabUtility.GetPropertyModifications(root)` (389 in this case),
> filter out those where `propertyPath.StartsWith("m_Materials.Array.data[")` and point to the target asset,
> then write back with `SetPropertyModifications`. Same kind of risk: `m_BlendShapeWeights.Array.data[i]`.

---

## ⚠ Japanese/Chinese/emoji paths

The problems on the old Windows machine (Windows) of the Bash tool failing to open them and PowerShell multi-line commands garbling them **do not exist on this machine (Linux) (Linux)**; just use bash.
Two points still hold:

- **Do not hand-type non-ASCII path literals**; locate from an ASCII ancestor directory by globbing on product ID/order ID
  (`ls -d <素材库>/*<商品号>*`) — directory names in `<素材库>` are in NFD form, and hand-typed NFC strings will not match.
- **Python containing backslashes should be written to a file and then executed**; do not stuff it into an unquoted heredoc.

## 3. How to ask for help when manual intervention is needed

### ✅ 2026-09-06 user authorization: **open Unity and Blender yourself, no need to ask first**

This table used to list “starting Unity” under “things AI cannot do”, with a technical reason
(cannot launch GUI applications), but what it actually blocked was **whether to ask first**. The user has explicitly authorized starting them on your own.

**Practice**: when you find Unity / Blender not open, **just start it**, then self-check whether it reached a usable state after starting,
**and only ask for help with that one click in the panel** — do not say “please open Unity for me” any more.
When asking, make clear: the process is already up, which rung it is stuck on, and exactly what remains to be clicked.

### What AI cannot do → [Manual gate master table](00-overview/manual-checkpoints-and-asset-sources.md) (the single authoritative copy)

Relevant to this page is category B of the master table: selecting Stdio in the panel, changing `Client Project Dir` and clicking Configure, restarting the Claude Code session, exiting a Play session the user is using, restarting Unity after adding packages, SDK upload. When you hit these, ask for help using the wording below.

### Hard requirements for help-request wording

**Do not just say “MCP won't connect”.** State four things at once so the human can do it all in one go:

1. **What I am trying to do** — which step is stuck, which stage it belongs to
2. **Which rung I reached** — which item of the ladder above, and what has been ruled out
3. **What I need you to do** — down to which menu to click, which field to change, what value to enter
4. **What to tell me when done** — which confirmation is needed to continue (e.g. “what does Transport show on the panel now”)

Also state **what you will do while waiting for the human** — work that does not depend on Unity proceeds as usual;
see the parallel swim lanes in [01 · Automation and parallelism](01-automation-and-parallelism.md).

### Judging “should wait” vs “should ask a human”

- **Should wait**: domain reload, asset import, baking, first compile — there is a clear completion signal (dll timestamp, status field)
- **Should ask a human**: GUI operations **inside the panel** are needed, a session restart is needed, exiting Play is needed
- **~~Process does not exist~~ no longer belongs to “should ask a human”** — start it yourself (authorized 2026-09-06)

**Do not treat “should ask a human” as “should wait”** — you will poll until timeout;
**and do not treat “should wait” as “should ask a human”** — you will disturb someone over a normal reconnection.

---

## Deterministic steps

### Step 1 · Confirm the project exists　🤖

**Prerequisites**
- [ ] The project root path is known

**Execute**
1. Check whether `ProjectSettings/ProjectVersion.txt` exists
2. Compare the number of `locked` entries in `Packages/vpm-manifest.json` with the number of package directories under `Packages/`

**Post-condition criteria**

| Expected | How to read |
|---|---|
| `ProjectVersion.txt` exists | File system |
| The two counts are equal | Compare the two numbers above |

**STOP**
- Project does not exist → go to [Project setup and first compile](02-environment-and-manual-intervention/project-setup-and-first-compile.md), or ask where the project is

---

### Step 2 · Confirm Unity is running and not in Play　🤖

**Prerequisites**
- [ ] Step 1 passed

**Execute**
1. Read the editor state

**Post-condition criteria**

| Expected | How to read |
|---|---|
| The state can be read | Cannot read → go down the ladder in section 1 |
| `play_mode.is_playing == false` | State field |

**STOP**
- Process does not exist → **start it yourself** (authorized), then re-judge
- In Play mode → ask the human to exit per section 3

---

### Step 3 · Confirm Unity can be driven　🤖

**Prerequisites**
- [ ] Step 2 passed

**Execute**
1. Send a **read-only** call (read scene info)
2. If it fails, **retry once** (reconnection needs a beat)

**Post-condition criteria**

| Expected | How to read |
|---|---|
| The read-only call returns success | Return value |

**STOP**
- Still failing after retry → go down the ladder in section 1 rung by rung, handle per whichever rung you land on, **do not skip steps**

---

### Step 4 · Confirm scripts compile　🤖

**Prerequisites**
- [ ] Step 3 passed
- [ ] This stage needs Editor scripts to be written

**Execute**
1. Write the `.cs`
2. Trigger compilation
3. Poll the dll timestamp until it is later than the source timestamp

**Post-condition criteria**

| Expected | How to read |
|---|---|
| Timestamp of `Library/ScriptAssemblies/Assembly-CSharp-Editor.dll` > timestamp of `.cs` | File system |
| No errors starting with `CS` in the Console | Read the Console, filter by error level |

**STOP**
- dll not updating for a long time and not in Play → possibly Safe Mode; go to
  section 3 of [Project setup and first compile](02-environment-and-manual-intervention/project-setup-and-first-compile.md)
- First compile fails but due to one of those three known causes → fix per the corresponding method, **do not ask a human**
