> 🌐 English translation · [中文原文](../../../开发工具/SOP/30_捏脸.md)

# 30 · Face sculpting　🔒 30a manual ＋ 🤖 30b fully automatic

> ## Split into two parts; only the first part needs a human
>
> | Part | Who | Content |
> |---|---|---|
> | **30a-1 Produce candidates** | 🤖 | Read the reference images (see [12 Reading reference images](12-reference-image-reading.md)) → adjust **vendor blend shape values** to assemble 2–3 mutually exclusive candidates → render a set of images for each. ⚠ **Don't start from the ceiling**: enlarging keys start from 0.15–0.30, curvature keys start at full; the two directions run opposite ([calibration](30-face-sculpt/approach-selection-and-aesthetic-calibration.md) §3) |
> | **30a-2 Settle the shape** | 🔒 **Human** | Choose from the candidates, or give adjustment amounts. "Is this face right" can only be judged by the person themselves; rework here is the most costly |
> | **30b Implement** | 🤖 **Fully automatic** | Baking, eye-close compensation, full blend shape check, export, binary self-check, reassigning materials after overwriting the FBX — all mechanical actions, **every criterion is a number** |

> → [Route decided: default to Blender](30-face-sculpt/approach-selection-and-aesthetic-calibration.md) — both premises of route 1 "never going through Blender" are wrong: AAO Freeze doesn't do eye-close compensation (measured +18.8%), and a modified FBX can still have face tracking installed (fork via `current_in_use` has zero validation; vertex count and index order must be verified yourself).

> ## 🚫 Hard rule: face sculpting adjusts only **vendor blend shape values**; free-form vertex editing is forbidden
>
> → [The basis for the hard rule and its exceptions](30-face-sculpt/hard-rules-basis-and-exceptions.md) — the measured basis of the mesh-editing failure, why facial-feature scaling geometry isn't used by default, and the exception and four rules for building closed-form custom keys when vendor keys genuinely lack a direction.
>
> | | Allowed | Forbidden |
> |---|---|---|
> | Shaping method | Adjust the **values** of the vendor's built-in face blend shapes | The AI deciding on and applying vertex displacements itself to "sculpt" |
> | Moving the mesh | **Local repair** of unsmooth vertices/mesh after baking | **Resetting the whole mesh** back to the original (throwing away the sculpting with it) |
>
> The vendor has already encoded "which directions of deformation are reasonable" into those keys — **borrow its hand; don't invent deformations yourself.**
>
> **Applied to the plan**: every item in a face sculpting plan must be expressible as **a specific vendor blend shape name + value**.
> Anything that can't be ("only achievable by moving the mesh") is **cut outright; don't put it in the candidates for the user to choose**.
>
>
> ### ✅ But **extrapolation beyond 0–1 is allowed** (the author, 2026-09-06)
>
> The vendor limiting the slider to 0–1 is **its UI constraint, not a mathematical boundary of the deformation**.
> The negative direction gives you a reverse deformation for free.
>
> **Order: widen the slider first, then assign value. Reverse it and it silently clamps back** (no error).
> **Criterion**: read back `value` after assigning; `abs(读回 − 目标) > 1e-6` (read-back − target) means it was clamped.
> ⚠ The scales on the two sides differ by 100×: **Blender 0–1 / Unity 0–100**; values moved across must be converted.
> ⚠ Before writing >100 on the Unity side, confirm that **Legacy Clamp BlendShape Weights** in Player Settings **is off**.
>
> **The three costs of extrapolation, slider value ranges, why shape-type keys shouldn't be extrapolated**
> → [Tool choice and probing what keys mean](30-face-sculpt/tools-and-key-meaning-survey.md)
>
> → For the full derivation of the closed-form key exception and its four rules, see [The basis for the hard rule and its exceptions](30-face-sculpt/hard-rules-basis-and-exceptions.md).

> → Scheduling: swapping the FBX invalidates part of 50 Assembly and 40 Recoloring, so **30 comes before 50**, and the scene isn't touched during 30a — the canonical statement is at the [top of 50](50-outfit-and-hair-assembly.md).

## Which tool to use: **follow the question, not the existing scaffolding**

| Nature of the question | Where to go |
|---|---|
| **Geometric quantities** — which vertices does this key move and where, is the eye tail raised or lowered relative to the inner corner | **Read vertex displacements in Blender**, seconds, gives numbers |
| **Things only doable in Blender** — baking, per-eye compensation, FBX export and binary self-check | **Blender** |
| **Look** — does this set of values look good, can the differences between several sets be seen | **Unity renders + multi-model review** |

```bash
blender.exe -b --factory-startup --python 开发工具/通用工具/bl_tilt.py -- <fbx> out.json
```

**Two hard criteria**:
- **When choosing keys, look at strength before names** — vendors provide several keys in the same direction, differing in strength by more than 2×;
  in a differentiated plan each group's `实测倾斜量 × 数值/100` (measured tilt × value/100) **must differ by a visible order of magnitude**, otherwise the renders are indistinguishable
- **Key names aren't necessarily trustworthy** — measured: `eyelid_turi2` (吊り目, upturned eyes) reads from vertices as **drooping downward**

Cost comparison, two pitfalls in the statistical method, existing practice → **[Tool choice and probing what keys mean](30-face-sculpt/tools-and-key-meaning-survey.md)**
Create `<订单>/_捏脸/` at order intake.

## What the Agent can do during 30a

| Can do | Can't do |
|---|---|
| **Adjust vendor blend shape values to assemble candidates and render them** | **Edit vertices/mesh itself to shape** (hard rule, see top of page) |
| Back up restore points, binary self-checks before and after export | Make the **final call** on "which way the face shape goes" |
| Quantitative acceptance (seam splitting / depth change / expression extrapolation) | Judge likeness on the user's behalf |
| Write the transform as a re-runnable script so the user only changes coefficients | — |
| Project-wide expression extrapolation scan and correction after baking | — |
| **Parallel lanes**: produce recoloring candidates, plan the menu structure, fill in assets | Touch the scene |

---

## Deterministic steps (30b, fully automatic)

### Step 1 · Keep restore points　🤖

**Preconditions**
- [ ] 30a has been handed back, and the human has explicitly said "it's finalized"

**Execute**
1. Keep three restore points: the FBX before overwriting, the sculpted-but-unbaked blend, and the baked-but-uncompensated blend

**Post-criteria**

| Expected | How to read |
|---|---|
| All three files exist and are non-empty | File system |

**STOP**
- Any restore point missing → stop and fill it in before continuing. FBX is binary and not in version control; when something goes wrong it's the only thing you can rely on

---

### Step 2 · Inventory the keys to bake and bake them　🤖

**Preconditions**
- [ ] Step 1 passed

**Execute**
1. List keys that are non-zero and **not set by yourself** (keys you set for effect, once baked in, get pushed up again by animations — double application)
2. Bake with **exact reconstruction** (not accumulation)

**Post-criteria**

| Expected | How to read |
|---|---|
| Max difference between `Basis` and `mesh.vertices` **== 0 mm** | Compare after baking |
| Number of bake list entries == number inventoried in step 1 | Compare the two numbers |

---

### Step 3 · Eye-close compensation (**per eye**)　🤖

**Preconditions**
- [ ] Step 2 passed

**Execute**
1. Split the upper-eyelid cluster into two by the sign of x → take each centroid as the eye center
2. Build a smoothstep mask for each, full at 30mm / zero at 50mm → **compute each ratio separately**

**Post-criteria**

| Expected | How to read |
|---|---|
| After a single-eye key (`blink_L` / `ウィンク`) acts, the sculpting of **the eye that isn't closed** is unchanged | Compare vertex displacements |

**STOP**
- A symmetric mask undoes the sculpting of the eye that isn't closed as well — if this happens, the eyes weren't separated

---

### Step 4 · Full blend shape check　🤖

**Preconditions**
- [ ] Step 3 passed

**Execute**
1. Iterate over every `.anim` in the project, take the peak of each `blendShape.X`, and add the baked amount

> ⚠ **If blend shapes were extrapolated (t outside 0–1), this step must be re-run**; you can't carry over the previous round's scan results —
> as the baked amount grows, the number of out-of-range entries grows with it.

**The scan source isn't only `.anim`**: add ShapeChanger **Set values** and `m_BlendShapeWeights` in scenes/prefabs. **Review item**: values outside 0–100 get clamped by `legacyClamp` (Play convention = 1) → [Baking and compensation](30-face-sculpt/baking-and-compensation.md).

**Post-criteria**

| Expected | How to read |
|---|---|
| Number of out-of-range extrapolations (>100) == 0, or each has been recomputed | Audit tool output |
| Number of "baked keys written in the resting expression" == 0 | Same as above (this is double stacking) |

> The result may well be **zero out-of-range**. Having checked and confirmed there's nothing is itself an output —
> don't change the animations just to "do something".

---

### Step 5 · Restore material slots → export → binary self-check　🤖

**Preconditions**
- [ ] Step 4 passed

**Execute**
1. **Restore the material slots to the vendor's original** (custom materials temporarily swapped in to see the face clearly must not be exported along)
2. Export the FBX
3. Do a binary count comparison against the vendor original

**Post-criteria**

| Expected | How to read |
|---|---|
| **Number of occurrences of vendor material names == original** | Binary self-check |
| Counts of `UnitScaleFactor` / `LimbNode` / `PoseNode` / `BlendShapeChannel` match the original | Same as above |

**STOP**
- If the counts don't match, don't overwrite. **Static validation can't catch a corrupted bind pose**; we rolled back once because of it

---

### Step 6 · Fixed actions after overwriting the FBX　🤖

**Preconditions**
- [ ] Step 5 passed

**Execute**
1. Overwrite the FBX
2. **Re-run every "assign materials" tool**
3. Run an empty-material-slot scan
4. If 50 has already been done: uninstall and reinstall each outfit once (`BaseToMerge` misaligns the jacket)

**Post-criteria**

| Expected | How to read |
|---|---|
| Number of empty material slots == 0 | Scan report |
| Each outfit **is visible** when turned on alone (not "object present but not rendering") | Render confirmation |

**STOP**
- Typical symptoms of skipping this step: **the face gets the eye material**, the jacket GameObject is present but doesn't render at all

## Acceptance (by numbers, not by eye)

The wrap-up gate of stage 30: four numerical criteria — **seam splitting, depth change `|Δy|`, expression extrapolation, post-export binary self-check** → for the criteria table and how-to see [Baking and compensation · Acceptance](30-face-sculpt/baking-and-compensation.md).

## Don't misjudge

Jaggies in the Blender preview are mostly an illusion — FBX import sets materials to **HASHED** (random dithered transparency),
so edges inevitably look fuzzy at low resolution. To tell real from fake, either raise the resolution and add samples, or look directly at Unity's lilToon render.

## Subpage index

| Subpage | When to consult |
|---|---|
| [Facial-feature scaling geometry](30-face-sculpt/facial-feature-scaling-geometry.md) | Doing **geometric-scaling** face sculpting; eye interpenetration / white specks / thickened eyeliner |
| [Baking and compensation](30-face-sculpt/baking-and-compensation.md) | How-to details for each 30b step: exact reconstruction, per-eye compensation, full check, material slot trap |
| [Attributing and fixing face sculpting bumps](30-face-sculpt/bump-artifact-diagnosis-and-fix.md) | Wrinkles/bumps appear on the face after sculpting: first rule out the two wrong paths of normals and curvature, locate with the three metrics of self-intersection + rotation + area collapse, fix with local synchronized displacement across layers |
| [**Route selection and aesthetic calibration**](30-face-sculpt/approach-selection-and-aesthetic-calibration.md) | **Consult before starting** — why Blender is required; the four rules for custom closed-form keys; don't start values from the ceiling |
| [**Tool choice and probing what keys mean**](30-face-sculpt/tools-and-key-meaning-survey.md) | **Consult before doing anything** — Blender or Unity; how to measure a key's true direction and strength in seconds; the mechanism and cost of extrapolation |
| [Face tracking](30-face-sculpt/facial-tracking.md) | Stage 35: the active root after face tracking is installed, shared materials between FT/native roots, large BlendShare files, component differences between the two roots, the parameter-bit ledger |
