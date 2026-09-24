> 🌐 English translation · [中文原文](../../../../开发工具/SOP/30_捏脸/工具与键义探查.md)

> ← [30 · Face sculpting](../30-face-sculpt.md)

# Tool choice and probing what keys mean

## Which tool to use: **follow the question, not the existing scaffolding**

> Measured 2026-09-06: for the same question (does each of ten blend shapes move the eye tail up or down),
> **the Unity route** dispatched a subagent for 11 batchmode renders + crops + review, over twenty minutes,
> and still got "descriptions of images", one of which conflicts with the numerical conclusion and remains unresolved to this day;
> **one Blender headless script ran in 4.4 seconds** and directly gave the displacement amounts and directions.

| Nature of the question | Where to go |
|---|---|
| **Geometric quantities** — which vertices does this key move, in which direction, by how much, is the eye tail raised or lowered relative to the inner corner | **Read vertex displacements in Blender** (`通用工具/bl_keyprobe.py`, `bl_tilt.py`) |
| **Things only doable in Blender** — baking, per-eye compensation, FBX export and binary self-check | **Blender** |
| **Look** — does this set of values look good, can the differences between several sets be seen | **Unity renders + multi-model review** |

```bash
blender.exe -b --factory-startup --python 开发工具/通用工具/bl_tilt.py -- <fbx> out.json
```
**No GUI needed, no MCP plugin needed**, seconds.

### Trade-off: **what to do when it's both geometry and look**

Most questions are mixed. How to do it: **first use geometric quantities to pin down everything that can be pinned down, and only send what remains for review.**

| Question | Nature | What to use |
|---|---|---|
| Where does this key move vertices, and by how much | **Geometric** | Read displacements in Blender, seconds |
| Is the change in this direction visible on the finished product | **Look** | Must render + review |

This order tripped on both sides:
- **Treating look as geometry** → the candidate table computed nice estimated tilt values, but when rendered the client couldn't see any difference
- **Treating geometry as look** → the probe round spent twenty-plus minutes rendering to ask a question Blender could compute in 4.4 seconds

**The costs of misjudging are asymmetric**: treating geometry as look is merely **slow** (a wasted round);
treating look as geometry **produces a self-consistent plan whose effect nobody can see**, which is only exposed when it reaches the client.
**So when unsure, compute geometry first (cheap), then use it to design the render verification (expensive).**

### Create `<订单>/_捏脸/` at order intake
The previous order had a complete set of seven `.blend` iterations in that directory (`sculpted_prebake` → `prebake_backup` →
`baked` → `baked_compensated` + normal-fix version). **Don't wait until 30b to remember it.**

### ⚠ When choosing keys, **look at strength before names**

Vendors often provide several keys in the same direction, **differing in strength by more than 2×**. Measured (Shinano):
the strongest upturn `eyelid_turi1` is +0.00223, while `eyelid_tail_up`, originally used for upturn in the candidate table, is only +0.00124,
and the values given were 15–30 — **effectively almost no effect; the eye-tail differences between the three candidate groups were never actually produced**.

**Criterion**: in a differentiated plan, each group's `measured tilt × value/100` must **differ from the others by at least a visible order of magnitude**,
otherwise the plan table looks different but renders indistinguishably.

Two pitfalls in blend shape displacement statistics: ① lateral displacement can't be averaged across the left and right eyes (the signs are opposite; averaging cancels to 0); ② inner/outer percentiles must be taken within each eye separately, not by splitting both eyes' vertices at the median of |x|. After the fix, the left and right eye tilt values are identical — the symmetry serves as a sanity self-check.

### ⚠ Key names aren't necessarily trustworthy
Measured: `eyelid_turi2` (turi = 吊り目, upturned eyes, should raise the eye tail) reads **−0.00100 from vertices, drooping downward**.
⚠ This conflicts with the "look at the render" conclusion and is **unresolved** — the handling is to **route around it**, using `eyelid_turi1`, whose direction is undisputed.


---

## Extrapolating beyond 0–1: mechanism and cost

### ✅ But **extrapolation beyond 0–1 is allowed** (added by the author 2026-09-06)

The vendor limiting the slider to 0–1 is **its UI constraint, not a mathematical boundary of the deformation**.
Shape keys are linear interpolation; t = 1.5 or −0.5 both hold — **the negative direction gives you a reverse deformation for free**.

| Property | Default | Adjustable range |
|---|---|---|
| `slider_min` | 0.0 | [−10, 10] |
| `slider_max` | 1.0 | [−10, 10] |
| `value` | 0.0 | Clamped within `[slider_min, slider_max]` |

**Order: widen the slider first, then assign value. Reverse it and it silently clamps back** (no error).
**Criterion**: read back `value` after assigning; `abs(读回 − 目标) 1e-6` (read-back − target) means it was clamped. Don't just check that the assignment raised no error.

**The three costs of extrapolation, all settled in the compensation stage**:
① linear extrapolation can break the shape (bumps/self-intersection/normal flips) → local repair; **repair, not reset**;
② the number of out-of-range `.anim` entries grows with extrapolation → **once you've extrapolated you must rescan all `.anim`**; you can't carry over the previous round;
③ the compensation amount is computed from the **actual displacement**, so the formula in [Baking and compensation](baking-and-compensation.md) needn't change; t1 is naturally absorbed.
