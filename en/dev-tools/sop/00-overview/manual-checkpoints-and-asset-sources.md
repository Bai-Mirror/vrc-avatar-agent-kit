> 🌐 English translation · [中文原文](../../../../开发工具/SOP/00_总表/人工卡口与素材来源.md)

# Manual gates and asset sources

> A subpage split out of the [overview](../00-overview.md): where to find assets, and **which things the user must do** and why.
> The manual gate table on this page is the **single source of truth** (on 2026-09-25 it merged three lists: section 3 of the former [01](../01-automation-and-parallelism.md) "only four places", section 3 of [02](../02-environment-and-manual-intervention.md) "6 things AI can't do", and this page's former "face tracking and nails" pair); those two pages keep only links and their own usage (01 covers how gates affect scheduling, 02 covers help-request wording and "wait or get a human").

## Asset sources

- Client asset pack: `<客户素材目录>/COMM-<订单号>_<客户名>_素材/`
- **For missing parts, first look in this machine's `<素材库>/`** (the full Booth product library); don't make the user re-download
- Archives and backups: `../../../_服务器备份名册.md`

## Manual gate master table

Symbols as in the overview: 👤 user decides · 🔒 user must do it personally · 🎨 aesthetic gate (the agent produces candidates → review → escalate only on disagreement).

### A · Process gates (on the critical path; for scheduling see sections 3–5 of [01](../01-automation-and-parallelism.md))

| Gate | Symbol | Why it can't be automated | Automatable parts that can be split off |
|---|---|---|---|
| **15 Kickoff direction** | 👤 | Requirement confirmation needs the commissioner's approval | Project setup, asset inventory, and missing-part searches can all be done first |
| **30a-2 Face sculpting finalization** | 🔒 | An aesthetic result, and the key values are set by the commissioner personally and must be reproducible; "is this face right" can only be judged by the person themselves, and rework is most costly | 30a-1 producing candidates, **30b bake/export/validation fully automated** ([01](../01-automation-and-parallelism.md) "30 should be split into 30a / 30b", [30](../30-face-sculpt.md)) |
| **40 Recoloring finalization** | 🎨 | Aesthetic; the user delegated it to review models on 2026-09-01, **escalated only when reviewers disagree** | Producing candidates, cross-model review ([40](../40-texture-and-coloring.md), [05](../05-multi-model-review.md)) |
| **95 Upload and final review** | 🔒 | VRChat SDK upload must be done by a human | Packaging, validation, writing delivery notes fully automated |

The only points on the critical path that truly stop and wait for a human are **15 → 30a-2 → 95**; 40 finalization and 70 in-headset verification can overlap with AI work.

### B · Operations the user must do personally (when encountered, ask for help using the wording in section 3 of [02](../02-environment-and-manual-intervention.md))

| Item | Why it can't be done on their behalf | When / notes |
|---|---|---|
| First time selecting Stdio in the `Window → MCP for Unity` panel | The panel is a GUI inside Unity; **even with the process running it can't be clicked** | Persists after being selected once |
| Changing the panel's `Client Project Dir` and Configure | Same as above | Restart the session after changing |
| **Restarting the Claude Code session** | Client config changes only load after a restart | — |
| Exiting the Play mode **the user is currently using** | No compilation during Play, and a person may be testing inside it | Play sessions started for audits by ourselves can be handled ourselves (09-18 authorization) |
| Restarting Unity after adding a package to `Packages/` | Refreshing and resolving packages are not enough; the dll won't appear | — |
| VRChat SDK upload | Must be done by a human | = 95 in table A |
| **Face tracking (FT Addon) installation** | The installer **clones the entire avatar**; the scene ends up with two, and the original is deactivated; **every tool that finds the avatar by name will modify the wrong object** | **Install last**, after all other work |
| **GUI Execute for nails (HoroNail etc.)** | The vendor component goes through Play-mode-trigger + self-destruct and can't be persisted; the GUI internally is a UIElements tree and can't be safely click-scripted | Outfit fitting stage |

**After face tracking is installed**: verify there is **only one live avatar root** in the scene. If you find two, stop and report; don't delete one yourself.
The face tracking copy is a **downstream product**: all model modifications are made on the **original**, and the face tracking root can be **regenerated**.

### Not gates, no need to ask first (already authorized)

- If Unity or Blender isn't open, **start it yourself** (2026-09-06); entering/exiting Play for audits and restarting a self-started Unity after a crash are also handled yourself (09-18; afterwards restore any ProjectSettings changed by Play).
- Conversely, **irreversible actions** (deleting archives, overwriting delivery packages, discarding scene changes, force-exiting Play) must be asked about first even if technically possible (workspace `CLAUDE.md`).
