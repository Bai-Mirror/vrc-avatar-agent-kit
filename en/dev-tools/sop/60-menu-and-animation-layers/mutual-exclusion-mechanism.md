> 🌐 English translation · [中文原文](<../../../../开发工具/SOP/60_菜单与动画层/互斥机制.md>)

# 60 · Mutual-exclusion mechanisms: catalog, failure scenarios and mandatory checks

> ← [60 · Menu and animator layers](../60-menu-and-animation-layers.md). Trigger: this order has multiple outfits/pieces at the same body part and you need to choose a mutual-exclusion tool; or at acceptance you suspect “the tool is installed but not wired up”.

The problem this page solves: **how to wire up “can't be worn together” between clothing, why an installed mutual-exclusion tool doesn't take effect, and how to catch it at acceptance.**
Look at the vendor's own grouping first for the criterion ([03 section four](../03-assembly-and-conflict-rules.md)); below is the catalog from past projects and measured failure scenarios (C §1, K #6, verified for this page).

## Mechanism catalog

| Mechanism | How to recognize | Seen in | Typical failure scenario |
|---|---|---|---|
| **ClothGroup** (VRCFury) | The menu has `ClothGroup` / `inverseToggleGroup` fields | Milfy (6 groups) | Selecting two outfits at once in the 6 groups never verified; tool only installed in a **backup prefab**; `inverseToggleGroup` all empty, relying on a shared int + advanced toggle |
| **3bitInt** | Int parameter in steps (8 steps) | Manuka (4 groups × 8 steps), H6-Shinano (3 Ints) | The active controller coexists with the original/Mod and the wrong one gets edited; the Int parameter referenced by 3bitInt isn't in the active avatar parameter table |
| Single Float driving a timeline radial | One Float plus constant tangents | Early-author, H8-Shinano | **Stops between two steps**; whether the default five pieces are hidden when the outer outfit is on was never read |
| RadialPuppet controlling outfits | Radial `RadialPuppet` | H3-Eku, H9-Sio | Layer mechanism not traced back; radial intermediate values |
| ObjectToggle with explicit inverse list | Inverse entry table | P1 | New clothing added but **inverse entries not backfilled** |
| Independent toggles per piece (no exclusion) | One Bool per piece | H1-Eku, Sio×2, Rurune, H7-Shinano outer outfit | **Two pieces on at once, suspected clipping**, body keys double-written |

## Mandatory checks (four, all statically checkable)

1. **MA MenuItem is mandatory**: looking only at `VRCExpressionsMenu` misjudges “missing items / dangling parameters” — **parse together with MA MenuItem**. Whether vendor submenus are hooked into the actual menu tree, and parameter names gaining `__MA/AutoParam/…` suffixes after build, are both judged from the post-build state (`T4 菜单导出`).
2. **ClothGroup must be in the real scene**: a tool that only exists in a backup prefab / a disabled root is equivalent to **not wired up**; confirm it references objects under the active root.
3. **Dead parameters**: clip curve paths that don't resolve (common after AAO deletes/renames) → on a baked clone, resolve “parameter → layer → clip curve path”; **0 resolvable = dead parameter** (Milfy `trace_param.txt` found 5).
4. **Layer default weight 0 is mandatory to check**: after baking, read `m_DefaultWeight` layer by layer, cross-check against all LayerControls, and list layers with **weight 0 that nobody raises**, and their controls (H3-Eku `Breast` is this type: the menu has a control, flipping it does nothing).

## What to do if it falls short

- More than **1** source turned on at the same body part in the default state means it's wired wrong: first judge “decoration or variant” per [03 section five](../03-assembly-and-conflict-rules.md), then choose the mechanism; **don't go by feel**.
- Mutual-exclusion tool installed but not wired: **don't patch with runtime logic**; go back to the wiring itself; if it can't be fixed, write “this mutual exclusion is not in effect” in the delivery notes.
- Radial intermediate values: verify at least the three steps `1/4 / 1/2 / 3/4` (see [70](../70-regression-testing.md)); two outfits both half-on at the midpoint is a defect.
