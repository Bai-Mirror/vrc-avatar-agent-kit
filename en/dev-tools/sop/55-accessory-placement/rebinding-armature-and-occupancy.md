> 🌐 English translation · [中文原文](<../../../../开发工具/SOP/55_配饰装位/重挂骨架与占用.md>)

> ← [55 · Accessory placement](../55-accessory-placement.md)

# Rebinding the armature and the “occupancy” judgment

This page covers two judgments that are easy to get wrong: **when rebinding an armature, is what you're changing the copy the mesh is actually bound to**;
and **when judging whether a spot is occupied, occlusion is not occupancy**.
Both belong to the class “looks completely right statically, gives itself away once it moves or the outfit changes”.

## ⚠ When rebinding an armature: **what you change must be the copy the mesh is actually bound to**

### Trigger
**When you're about to change the mount point of an accessory already attached in the scene, or adjust its armature position.**

### Question
**“Do the `m_RootBone` / `m_Bones` of the four SkinnedMeshRenderers point to the Transforms I'm about to change?”**

### What to do if you get it wrong
Find the copy the mesh is actually bound to by **fileID** (not by name), and **change that one**;
delete or disable the other copy. **Don't rebind `m_Bones`** — rebinding is far more dangerous than reparenting.

### Evidence (2026-09-07 Project C · GOTHIC ROSE fox ears)

After the prefab was unpacked into loose GameObjects, one “re-mount” created **two structurally identical armature branches**:

| | Active | Parent | Is the mesh bound to it |
|---|---|---|---|
| Branch A | **0 (disabled)** | Head (old mount, with 1.2579 m offset) | **Yes** |
| Branch B | 1 | Base avatar root (new mount, correct position) | No |

Result: **the mesh followed the disabled A and floated beside the head; the correctly positioned B drove nothing.**
And the world-position criteria measured B — **both distance criteria passed, yet the image was wrong.**

> The executing run **judged correctly on its own** that “only one copy is actually referenced by the mesh”, but **disabled the wrong one**.
> This was caused by **identification and action using different identifiers** (identification used `m_Bones`, action used names).

### Two rules that follow

1. **After unpacking, always operate by fileID.** Once loose, same-name nodes appear in pairs
   (in this case each of the 14 bone nodes had two same-name copies); selecting by name is bound to go wrong.
2. **For operations like “rebinding the armature”, the criteria must include “did the mesh follow”** —
   world positions only prove the **bones** are in place, not that the **mesh** follows the bones.
   The only criterion is the **render**: bones right but mesh didn't follow is the most typical failure state of this kind of operation.

### How to check from the scene YAML (no need to open Unity)

```python
# 1) !u!1 GameObject block -> m_Name / m_IsActive
# 2) !u!4 Transform block  -> m_GameObject / m_Father
# 3) !u!137 SkinnedMeshRenderer block -> m_RootBone / m_Bones (all Transform fileIDs)
# Look up 3's fileIDs in 2 and walk the parent chain to learn which copy the mesh is bound to and whether that copy is active
```

---

## ⚠ Occlusion ≠ occupancy: bone weights and bounding boxes can't see “openings”

### Trigger
**When you need to judge “is this accessory covered by that clothing / footwear” (toenails hidden with shoes and socks, a necklace covered by a collar, earrings buried in a hairstyle).**

### Question
**“Am I using an occupancy criterion (weight fraction / bounding box overlap), or did I actually look?”**

### What to do if you get it wrong
**Force the occluded object visible + render a close-up**: occluded object `enabled = true`, occluder displayed as usual, camera aimed at the occluded object. If it's visible, it isn't covered.
Cheap, decisive, no threshold tuning — “is it visible” is a closed question, and that's what the render answers, not aesthetics.

### Evidence (toenails × five sets of footwear)

Two geometric criteria were set in advance; **both failed**:

| Footwear | Toe-bone weight fraction | Bounding box overlap | Actual shot |
|---|---:|---:|---|
| Peep-toe heels | 7.31% | 100% | **Big toe exposed, nail clearly visible** |
| Footed stockings | 22.26% | 100% | Toe tips opaque → truly covered |
| Closed shoes | 19.01% | 100% | Truly covered |
| Peep-toe flats | **N/A** (16 meshes `isReadable=false`) | 100% | **Open toe, nail exposed** |
| Closed boots | 10.50% | 100% | Truly covered |

- Bounding boxes have **no discriminating power at all**: 5/5 report 100% (uppers / straps / lace near the toe bones fool it into full)
- Weights with a 1% threshold pass all five → by the criterion, toenails would be hidden in all five sets, **two of which are wrong**
- `sharedMesh.isReadable=false` can't read weights: report N/A honestly; **don't substitute bounding box alone**

### Boundaries
- **Does not overturn** using occupancy + layer depth for “clipping mutual exclusion” — clipping really is an occupancy problem; it only overturns using occupancy to judge **occlusion**; handle the two separately
- The “covered → hide” gate hooks onto the shoe / sock **part** toggles ([60 · Layers by occlusion state](../60-menu-and-animation-layers/layer-order-and-override.md)), and **each pair of shoes is judged individually**, not all at once by whole outfit
- Both directions are visible defects (wrongly hidden = something the client bought disappears; wrongly kept = nail tips poke through the shoe), **there's no conservative default**; only a per-pair render decides
