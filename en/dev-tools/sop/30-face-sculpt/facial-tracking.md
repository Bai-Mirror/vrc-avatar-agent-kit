> 🌐 English translation · [中文原文](../../../../开发工具/SOP/30_捏脸/面部追踪.md)

# 35 Five mandatory checks for face tracking (FT)

> ← [30 · Face sculpting](../30-face-sculpt.md)　Where stage 35 "face tracking" in the stage table lands (stage 35 in the [00 Master table](../00-overview.md) stage table points to this page)

The problem this page solves: after face tracking is installed, how to judge each of five kinds of problems — **roots, materials, large files, parameter bits, and component differences between the two roots**.
The installation itself is a **manual gate for the user** (the installer clones the whole avatar); for the reasoning and scheduling see [Manual gates and asset sources](../00-overview/manual-checkpoints-and-asset-sources.md).

## 1. Keep only one **active** root (trigger: after face tracking is installed, before any acceptance)

The face-tracking installer **clones the whole avatar**: the scene then has two, and the original is disabled; **every tool that finds the avatar by name will modify the wrong object**.

- **Criterion**: counting per [03 · Conventions for "how many avatar roots"](../03-assembly-and-conflict-rules.md) (scene roots / scene-wide descriptors / active root / including backup prefabs), **active roots == 1**; if you find two, stop and report.
- **If you can't meet it**: **don't delete on your own** — deleting the wrong root loses the live version; let the user decide.
- **Reversibility**: the face-tracking copy is a **downstream product**; all model changes are made on the **original**, and the face-tracking root can be regenerated.

## 2. Check **whether the FT root and the native root share materials/textures** (trigger: before changing materials/colors)

Disabling the other root **doesn't eliminate its cost** — if the two roots share materials/textures, disabling saves only the renderer, less than expected.

- **Criterion**: iterate over both roots' materials and compare the **asset paths / GUIDs** of `sharedMaterials`; for shared ones, reverse-check with "does changing one place change both roots at once".
- **If you can't meet it**: if you can't tell, treat them as "shared" (change materials via copies), and mark "unverified" in the work log.

## 3. Check large `BlendShare` files separately (trigger: when fingerprint/review tools skip large files)

Historically measured: **in one project a >30 MB BlendShare was skipped by the fingerprint tool, and the face sculpting went unchecked**.

- **Criterion**: `find <工程>/Assets -name '*.blendshape' -o -name '*BlendShare*'` to list everything; those `>30 MB` go on a separate list, and a human confirms which root/which face each corresponds to.
- **If you can't meet it**: a tool skipping something doesn't mean "there is none", it means "not checked" — **write it into the "unchecked" list**; don't treat an empty result as a conclusion.

## 4. Keep a **parameter-bit ledger** (trigger: face tracking is being added to an avatar that already has a pile of toggles)

Face tracking consumes parameter and PhysBone budget; calculate before installing, don't find out at 60/80 that you're over the limit.

| Budget | Limit | What to count first |
|---|---|---|
| Parameters | 256 bit (Int/Float 8 each, Bool 1) | Existing parameter usage + items added by face tracking (SDK-synced parameters) |
| PhysBone | 256 total | Bone chains the face-tracking root will attach + those already attached |

- **Criterion**: write both numbers into the parameter-bit ledger (suggested in `建档.md` or `菜单结构.md`), **reconciled against measured values** (see [60](../60-menu-and-animation-layers.md)); if headroom ≤0, cut features or use VRCFury `UnlimitedParameters`.
- **If you can't meet it**: when over the limit, don't delete controls yourself; let the user cut.

## 5. **Are the components of the two roots consistent** (trigger: the face-tracking root is the delivery root and review runs only on it)

A cloned face-tracking root may **differ** from the native root: in Project D Velvet China, the body-shrink ShapeChanger was "removed" on the face-tracking root by a prefab override (still present on the native root); after merging, 8 keys were deleted by AAO as unwritten, and the sleeves clipped when bending the elbow (09-19; the baseline was like this). T1 only runs on the delivery root, and in the data it shows up as "present in the writer list, but the read value is never non-zero".

- **Criterion**: for each prefab instance in both roots, compare `PrefabUtility.GetRemovedComponents` and the component type list; every non-empty `m_RemovedComponents:` entry in the scene text must have a stateable reason.
- **If you can't meet it**: treat removals without a stateable reason as "cloning/slip of the hand"; restore them, then do a key 0/100 bent-joint comparison (stop the Animator, rotate bones by hand, render only the body + that piece) before deciding.
