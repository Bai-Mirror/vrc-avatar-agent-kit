> 🌐 English translation · [中文原文](../../../../开发工具/SOP/01_自动化执行与并行/子代理分派.md)

> ← [Step templates and hard gates](step-templates-and-hard-gates.md) · [01 · Automation and parallelism](../01-automation-and-parallelism.md)

# Subagent Dispatch: Whom to Send, Whether to Send, How to Verify

### Which model tier to send: split by “is there reasoning the tools cannot see”, not by model strength

| Task nature | Criterion | Send |
|---|---|---|
| **Enumerative** — output is a list/count, every line can be **directly confirmed** by some tool call | Listing directories, counting files, extracting fields, running existing scripts | **Haiku**, an order of magnitude cheaper |
| **Reasoning** — requires cross-file comparison, judging equivalence/compatibility/root cause | Needs “synthesizing evidence from several places” | **Sonnet** |
| **Aesthetic** — no closed-form criterion; what is needed is trade-offs and landing points | Face sculpting direction, recoloring, style convergence | **Fable** |
| **Troubleshooting** — other routes are stuck, criteria contradict each other, need to overturn an earlier route's conclusion | Root causes nested layer within layer | **Opus**, see below |

#### When to send an **Opus subagent**, and when to do it yourself

The **only benefit of sending a subagent is context isolation**: you pay for one task description + one report, and the intermediate process does not enter the main agent's context.
So whether an Opus subagent is worth it depends on whether three conditions hold **simultaneously**:

1. **Opus-level judgment is truly needed** — Sonnet would stop or go astray here
2. **Intermediate evidence is voluminous and noisy, but the conclusion compresses into a few lines** — large logs, scanning hundreds of packages, binary parsing
3. **Actions are reversible or purely read-only**

The criterion is “**cost of a wrong answer > cost of sending it**”, not “this problem is a bit hard”. Opus subagents are expensive.

**Two positive examples from 2026-09-06** (done by the main agent at the time, but should have been sent):

| Case | Shape |
|---|---|
| BlendShare compile chain | Three layers nested: missing semicolon → after fixing, 72 FBX types still not found → root cause is **UPM does not read package.json under `Assets/`**. Along the way it went through asmdef, the package cache, the previous order's `packages-lock`, and log tails — all noise; the conclusion was three lines |
| GUID forensics for a vendor material | Scanned 134 zips, compared `.meta` timestamps, traced vendor version history; the conclusion was **one GUID value** |

In that round Sonnet (the route classifying broken references) **correctly stopped at the first layer** and triggered STOP —
it did nothing wrong; that judgment was beyond its proper scope. **With STOP written correctly, weaker models will not force their way through.**

Four kinds **not to send, do yourself**:

- **Irreversible actions** — GUID fixes, baking, packaging, deleting files (the user decided “high risk, I do it”)
- **Intermediate evidence needed later** — e.g. an index table of 90 blend shapes that the main agent must keep
- **Very short tasks** — description cost exceeds the benefit
- **Needs back-and-forth confirmation with the user** — subagents cannot ask people

**One more kind worth trying (not used on this order)**: use an Opus subagent to **independently review another route's conclusion** —
its context is clean and it is not anchored by the previous route's wording, acting as an adversarial verifier.

#### When sending Haiku, you must **hard-code which kinds of judgments are forbidden** in the task description

Measured (2026-09-06 asset inventory): it reported “the two zips have identical content”, but they actually differed by 376,062 bytes.
**It never opened the zips, and could not have** — the task description asked it to judge “equivalence”.
The part where it listed filenames and byte sizes was accurate. **What failed was the description, not the model.**

Correct wording: “**report only filenames and byte sizes; do not judge whether contents are equivalent**”.

#### How to know which judgments to forbid (do not rely on experience; derive item by item)

For **each conclusion** the task asks it to give, ask:

> **“For this conclusion to hold, what action must it have **performed**?”**

Write that action down; **if the action is outside its tool capabilities, forbid that conclusion**,
and replace it with a substitute it can produce.

| Conclusion | Action it must have performed | Can Haiku do it? | Handling |
|---|---|---|---|
| “The two zips have identical content” | Extract and compare entry by entry | ✗ (can only list directories) | **Forbid**, replace with “report only filenames and byte sizes” |
| “These two packages are functionally equivalent” | Read README / install into a project and try | ✗ | Forbid, replace with “list each package's top-level directories” |
| “All files in this batch are present” | Traverse and compare against the list | ✓ | Keep |

**The cost of misjudging is asymmetric**:
- **Forbidding too much** → it hands back judgments it could have made, and you do one more round (**small cost**)
- **Forbidding too little** → it fabricates a conclusion, and execution-type reports are something you **tend to accept directly** (**much larger cost**)

**So err on forbidding too much.**

#### Acceptance rule: conclusions must match tool calls

> **Any conclusion in a subagent report that “could not be reached without performing that action” is not accepted; review it yourself.**
>
> Listing a directory cannot yield “the zip contents are identical”, reading filenames cannot yield “functionally equivalent”,
> a truncated log tail cannot yield the cause, a glance at a screenshot cannot yield “the bones are not misaligned”.

This is the same principle as “the **location** it points to is more credible than the **conclusion** it gives” in [05 multi-model review](../05-multi-model-review.md),
and **execution-type subagents are more dangerous** —
I naturally review review conclusions, but I tend to accept execution reports directly.

**What works**: write the **specific instances of previous fabrications** into the “reporting discipline” section of the task description.
Measured to be far more effective than abstractly writing “do not fabricate” — after adding them, subsequent routes all proactively marked uncertain items as “unverified”.

#### Subagents **do not wait for background tasks** (reproduced 3/3)

After starting batchmode / a background script, it hands back the turn; it has no polling ability. **This is not laziness; it is turn semantics.**

- The task description must hard-code “**after starting, you must poll and wait for it to exit before reading the results; do not report midway**”
- **The main agent must verify the final state itself**, and must not accept “still running”
- **Subagent interruption ≠ lost work** — first look at what is on disk, then decide whether to re-dispatch or continue

---

## Search tasks: **you list the full scope; do not let the subagent draw its own boundaries**

**Trigger moment**: dispatching exhaustive searches like “find X asset / find X file”.

**Hit before (2026-09-20, finding Milfy eye textures)**: the first sentence of my task brief was “search in the workspace `~/vrc-processing`”,
the subagent complied and returned an exhaustive list within the workspace — **the list itself was fine; the boundary was wrong**.
Only the user's remark “look in the broader asset areas” exposed it: this machine has **three** asset areas,
and the **search order had long been recorded in memory** (`<素材库>` main library → client asset packages → Baidu backup library); I just did not list them when dispatching.

**Checkable question** (ask yourself when writing the task brief):

> How many storage locations does this kind of thing have on this machine? Did I **list them all**, or only write the one I know best?

**Practice**:
1. First spend a command or two yourself to **list all storage locations** (`df -h` to see mounts, check the “resource locations” entries in memory, read the library's own `_库说明`),
   then write the task brief; in the task brief **hard-code each path**; do not write scopes like “search in the workspace” that the subagent has to interpret.
2. Mark each storage location as **read-only or not** (the archive library and client asset packages are read-only; explicitly forbid writes in the task brief).
3. For storage locations with their own index/metadata (e.g. `<素材库>/.booth-archive/manifest.json` has an `avatars` field),
   **query the index yourself before dispatching anyone** — whatever can be filtered out should not be unpacked by a subagent. This time, a single command against the manifest filtered out 3 eye-texture packages supporting Milfy.

**Trade-off**: listing the full boundary takes a few more minutes; not listing it costs a whole round of rework, and **before the rework you still believe you were "exhaustive"** —
which is worse than simply missing something, because it makes you overconfident in the conclusion.
