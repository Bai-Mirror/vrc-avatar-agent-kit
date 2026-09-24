> 🌐 English translation · [中文原文](<../../../../开发工具/SOP/55_配饰装位/骨段长度判据两步.md>)

# The “bone segment <0.5 m” criterion needs two steps, otherwise it produces false-positive STOPs

> Subpage split out of [55 · Accessory placement](../55-accessory-placement.md). Takes over that criterion's section from the main page; step 3's criterion “each bone ≤ 30cm from its parent bone” stays on the main page.

## ⚠ The “bone segment <0.5 m” criterion needs two steps, otherwise it produces **false-positive STOPs**

**The purpose of the criterion is to catch “PhysBones fly off as soon as they run”**, not “there's a long offset in the hierarchy”.
A VRCPhysBone's **root node itself doesn't participate in simulation**; only its children move —
**long bone segments above the PhysBone root are static and won't fly off.**

### Two steps

1. Measure all newly added bone segments and flag those ≥0.5 m
2. **Check each one for whether it's inside some PhysBone's simulation chain** (whether its parent is some PhysBone's `rootTransform` or a descendant of it)
   - **Inside** → real problem, must fix
   - **Not inside** → static offset, **this criterion lets it pass**

### ⚠ But “doesn't fly off” ≠ “position is right”

The second risk of a long offset is **pushing the accessory far away from its mount point**. That has to be **judged separately by world position**:

| Piece type | Criterion |
|---|---|
| Headwear / animal ears | `‖配饰根.world − Head.world‖ < 0.15 m` |
| Waist accessory / tail | `‖配饰根.world − Hips.world‖ < 0.20 m` |

**Bone-segment length can't tell whether the position is right; world position can.** Do the two criteria separately; don't mix them.

### How to read the PhysBone root (no need to open Unity)

`VRCPhysBone` references its script by GUID, **so the class name can't be found in the prefab text**.
Search for the field names **`rootTransform` / `ignoreTransforms` / `endpointPosition`** to locate the component block;
`rootTransform: {fileID: 0}` means **the root is the node the component sits on itself**.

### Example (2026-09-07 Project C · GOTHIC ROSE fox ears)

```
Head → Armature(Place in Head) → Ears_Root → Ears.001~004
                                 ↑ 1.2579 m      ↑ PhysBone attached here, root=itself
```
The 55 run triggered a STOP under the original criterion — **the behavior was entirely correct** (it hit the literal condition and stopped, without improvising).
**The criterion was written imprecisely**: it didn't say “for over-limit segments, check whether they're in the simulation chain”.
