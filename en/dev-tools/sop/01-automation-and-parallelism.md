> 🌐 English translation · [中文原文](../../../开发工具/SOP/01_自动化执行与并行.md)

# 01 · Automation and Parallelism　🤖

> This page answers three questions: **which steps can run without a human**, **which can be done at the same time**,
> and **how to write steps so that non-top-tier models can also follow them correctly**.
> How each stage itself is done is in the sub-tables; this page only covers orchestration.

---

## 1. Conclusion first: the boundary of parallelism is not the dependency graph, it is Unity being a single instance

A project has only **one** Unity editor instance at a time, and MCP can only drive it serially. So:

| | Can it run in parallel |
|---|---|
| Reading, judging, computing poses, writing scripts, generating lists, reviewing, writing reports | **Yes**, any number of routes |
| Any `execute_menu_item` / scene edits / baking / entering Play | **No**, must queue |

Plus three hard constraints:

- **Baking is expensive**; do not call it in loops; clear the `__Generated` clones every time
- **Scripts are not compiled during Play mode**; if you change a `.cs` and don't exit Play, it never takes effect
- **Edit `.cs` → compile → domain reload**, the MCP connection drops; it is only ready once the dll timestamp is later than the source timestamp

### The core orchestration pattern of this procedure follows from this

> **Produce lists in parallel → execute once serially → read back and verify.**

Tools are always built as **paired entry points**: `(list)` only reports without changing, `(execute)` is what touches the project.
The list half is pure computation — it can run in parallel, repeatedly, and be handed to weaker models;
the execute half only needs to queue once, and must be immediately followed by read-back verification.

This is not a new rule — existing tools were already written this way. Here it is **elevated to a principle**,
because it solves three things at once: parallelizable, reviewable, reversible.

---

## 2. Dependency graph (with practical corrections)

```
10 Order intake ──→ 15 Kickoff direction 👤 ──→ 20 Asset inventory/import
                                          │
                                          ├──→ 30 Face sculpting 🔒 ──→ 35 Face tracking
                                          │        │
                                          │        └──→ (resets material arrays, breaks armature lock)
                                          │                    ↓
                                          ├──→ 40 Textures & recoloring ───┤
                                          └──→ 50 Outfit/hair fitting ─────┤
                                                    │           │
                                                    └→ 55 Accessory placement
                                                            │
                                                            └→ 60 Menus & animator layers
                                                                    └→ 70 Regression test
                                                                            └→ 80 Performance optimization
                                                                                    └→ 90 Delivery packaging ──→ 95 Final review 🔒
```

### ⚠ 30 invalidates part of 40 and 50

Besides “35 is blocked by 30”, **30 also disrupts 40 and 50** (the 40/50 rows of the master process table are annotated accordingly, 2026-09-25):

- Swapping the FBX **resets the renderers' material arrays** → recoloring applied in 40 must be redone
- `ArmatureLockMode.BaseToMerge` syncs the outfit armature to the base avatar armature;
  after swapping the FBX it is **bound to be misaligned**, showing up as “the outfit GameObject exists but does not render at all”
  → every outfit fitted in 50 must be removed and refitted once

**So in scheduling, 30 must come before 50**, or accept reworking all of 50.
Face sculpting that only changes vertices and does not touch the armature is unaffected — but that is the minority; schedule by default as if it invalidates.

**Corollary**: 30 is the earliest manual gate on the critical path; it sets the pace of the entire order.

---

## 3. Manual gates

Which points must be done by a human (process decisions 15 / 30a-2 / 40 / 95, plus hands-on operations like panel GUI, restarting sessions, exiting Play, SDK upload, face-tracking installation, nail Execute, etc.),
why each cannot be automated, and the automatable parts that can be split out → **[Manual gate master table](00-overview/manual-checkpoints-and-asset-sources.md)** (the single authoritative copy). This page only covers how they affect orchestration.

### 30 should be split into 30a / 30b

Marking the whole stage 🔒 is overly conservative now. **Only “adjusting blend-shape values” needs a human**;
everything after is mechanical, and all criteria are numeric:

- Baking blend shapes into the base mesh (exact reconstruction, not accumulation)
- Recomputing the eye-close compensation key
- FBX export (two mandatory parameters + binary self-check before writing to disk)
- Seam split <0.3mm, `|Δy|` <2mm, Basis vs `mesh.vertices` difference 0mm
- After overwriting the FBX, **reattach materials + scan for empty material slots**
- Full `.anim` expression extrapolation out-of-range scan

After splitting 30, the manual gate shrinks from “a whole stage” to “one value adjustment + one confirmation”.

---

## 4. What can be done in parallel during manual gates

Gates are serial, but you need not idle **during** a gate. Three swim lanes:

| Lane | Stuck at 15 | Stuck at 30a | Stuck at 40 decision |
|---|---|---|---|
| **Assets** | Inventory, search the library for missing parts, unpacking completeness checks | Same as left (keep filling in parts) | — |
| **Preparation** | Read the requirements questionnaire, list suspected conflict pairs | Produce recoloring candidates, cross-model review | Plan the menu structure (needs only the outfit list, not a fitted scene) |
| **Tools** | Write probe/generator scripts for this order | Same as left | Same as left |

**Note**: while stuck at 30a, **do not touch the scene** (the commissioner may be adjusting it by hand).
The first explanation for unexpected scene state is always “a human changed it”.

---

## 5. Recommended orchestration for one order

```
[Human] 15 Set direction
   ↓
[AI parallel] 20 inventory checks ×N ──┐
[AI serial]   20 import               ─┤
[AI]          write probe scripts for this order ─┘
   ↓
[Human] 30a adjust blend-shape values
   ↓ (meanwhile AI in parallel: recoloring candidates → cross-model review; plan menu structure)
[AI] 30b bake/export/validate  →  35 face tracking
   ↓
[AI] 50 fitting  →  [AI parallel pose computation] 55 placement  →  [AI serial scene write]
   ↓
[AI] 60 menus & animator layers
   ↓
[AI parallel judgment] 70 combination regression ──→ [Human] verify platform-override changes on a real device
   ↓
[AI parallel judgment] 80 performance optimization ──→ [AI serial execution]
   ↓
[AI] 90 packaging & validation
   ↓
[Human] 95 upload & final review
```

There are only three manual points on the critical path: **15 → 30a → 95**.
Other manual interventions (40 decision, 70 real device) can overlap with AI work and do not occupy the critical path.

## Sub-page index

| Sub-page | When to consult |
|---|---|
| [Fan-out and workflow criteria](01-automation-and-parallelism/fanout-and-workflow-criteria.md) | Deciding whether to run multiple agents in parallel; checking what a stage still lacks to be fully automatic |
| [Step templates and hard gates](01-automation-and-parallelism/step-templates-and-hard-gates.md) | **Required reading before writing any step table**; the four hard gates are ones we actually stumbled on |
| [**Subagent prompts**](01-automation-and-parallelism/subagent-prompts.md) | **Required reading before dispatching subagents** — when to dispatch, the eight-section structure, four measured-effective ways of writing, three acceptance rules |
| [Subagent dispatch](01-automation-and-parallelism/subagent-dispatch.md) | Which model tier to send; the three conditions for Opus subagents; how to derive “which judgments to forbid” |
| [Lead agent interaction rules](01-automation-and-parallelism/lead-agent-interaction-rules.md) | When you've accumulated items for the user to decide: always use AskUserQuestion; do not ask in the body and end the turn (unrelated to orchestration, moved out from the end of this page) |
