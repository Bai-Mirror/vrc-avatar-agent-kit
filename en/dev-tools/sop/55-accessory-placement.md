> 🌐 English translation · [中文原文](<../../../开发工具/SOP/55_配饰装位.md>)

# 55 · Accessory placement　🤖

> Accessories = halos, headwear, ears/tails, wrist cuffs, rings, necklaces and similar small pieces that **ship their own armature and must be pinned onto humanoid bones**.
> Kept separate from [50 outfits and hair](50-outfit-and-hair-assembly.md) because their attachment method, acceptance method and menu form are all different.

## Iron rule one: the pose is **computed**, not typed in

Typing Euler angles by hand is an anti-pattern at this step, for hard reasons:

- **Humanoid bones' local axes are set arbitrarily by the base avatar's author**; the eight finger bones all differ. Hand-typing inevitably yields eight sets of
  magic numbers, all of which become useless on another base avatar.
- Measured: a ring set to `Vector3.zero` lies flat on the back of the hand; `(0,0,90)` just lies flat in another direction —
  both times it “looked like tuning”, but both were blind guesses.

The table only keeps “which bone segment it goes around, at what percentage along that segment” + two fine-tuning factors defaulting to 1.0;
everything else is derived from geometry. Reference implementation: `FitBand` / `LimbWidth` / `HandBack` in `AccMountA2.cs`.

## Iron rule two: impressions can't replace criteria, but passing criteria still needs an understandable image

In the ring round, in the top view the lower half of the ring was buried in the finger and only the upper half showed, looking like “a wire standing up” —
on that basis I reported “not encircling” **two rounds in a row**. The truth was the numeric criteria: eccentricity 0.00 mm, angle 0.0° — it had encircled all along.

So both are required:

- **Provable criteria** (run automatically): distance from limb axis to hole center < inner radius, and angle between limb axis and hole axis < 12°.
- **An understandable image** (for humans): see “Acceptance viewpoints” below.

## Iron rule three: don't use MA BoneProxy — it has no effect at edit time

Measured MA 1.18.1: **BoneProxy has no effect at all at edit time**; only during the NDMF build (entering Play / uploading)
does it snap the object onto the bone. At edit time the object stays at the origin.

The consequences are serious: **“screenshot each placement for acceptance” becomes completely impossible** (offscreen rendering goes through edit time);
the first version of the halo therefore rendered under the feet, and whoever looked at the image would think the position was miscomputed.

→ Switch to **parenting directly under the bone Transform** (`<人形骨>/Mount_<名>/<配饰>`): what you see is what you get.
The cost is touching the armature hierarchy of the base avatar prefab instance — acceptable; AI-side maintainability takes priority over prefab purity.

Two accompanying notes:

- Idempotent reruns must search the **whole tree** for `Mount_*` (mounts are no longer under `_Acc`),
  and move non-copy accessories back into `_Acc` before deleting mounts, otherwise a rerun deletes the accessories.
- **Leftover BoneProxy components** from the first version **must be removed**; otherwise at build time they move the object again,
  fighting with direct parenting.

## Don't use MergeArmature either

Accessories each ship their own independent armature (`Armature_halo` / `armature.tail` / `アーマチュア`),
with bone names completely different from humanoid bones; MergeArmature maps **0 bones**.

A root containing multiple armatures (ears + tail) must be **attached separately** to their respective humanoid bones
(`armature.ear`→Head, `armature.tail`→Hips), with the scale written on the armature itself.

---

> → [The “bone segment <0.5 m” criterion needs two steps](55-accessory-placement/bone-length-criteria-two-steps.md) — first measure segments ≥0.5 m, then check each for whether it's in a PhysBone simulation chain; “doesn't fly off” ≠ “position is right”, judge that separately by world position; field names for reading the PhysBone root without opening Unity.

## Iron rule four: **positioning reference ≠ parent bone** — only bones that don't rotate on their own can be parents

**Trigger**: when choosing the mount bone for an accessory on the face/head. **Question**: will this bone be rotated by eye gaze, face tracking, expressions or visemes? Yes → you may only use it to **compute position**, not as the **parent**.
Eye bones `eye.L/R` (rotated by VRChat eye look and face tracking), jaw `Jaw`, tongue bones, and ear/hair PhysBones all “rotate on their own”; the parent of eye-area stickers, beauty marks and cheek stickers should be **Head**.
> Measured (Project A, 09-22 the author reported “eye-area decal bound to the wrong bone”): `NewAccA2.cs` used `LeftEye` as the anchor, created `NAMount_Acc_目元_*` under `eye.L`, and also deleted the vendor's BoneProxy attached to Head;
> the sticker slid across the face with the eyeball. Fix: compute the world pose from the eye bone, then `SetParent(Head, worldPositionStays:true)`; the mount path changed, so **animation paths referencing it must be updated too**.

## Deterministic steps

### Step 1 · Confirm environment and baseline　🤖

**Preconditions**
- [ ] Environment confirmed usable per [02](02-environment-and-manual-intervention.md)
- [ ] All accessories for this order are instantiated under `_Acc`

**Execution**
1. Run the armature height self-check ([Scene corruption and recovery](troubleshooting/scene-corruption-and-recovery.md)) and record `eye.L` world y as the baseline

**Post-criteria**

| Expected | How to read |
|---|---|
| `|eye.L.y − 已知 good 值| < 0.02` | Self-check output line |

**STOP**
- 02 judges “needs a human” → ask for help per its section three

### Step 2 · Probe and classify　🤖

**Preconditions**
- [ ] Every piece has had its showcase images or vendor sample scene looked at ([Common pitfalls](55-accessory-placement/common-pitfalls.md))

**Execution**
1. Run `RingProbe.cs`: group by bone weight, per group compute the bounding box and minimum radius on the three axes
2. Classify each piece into the placement table: `环状` / `带骨架·素体专用` / `带骨架·通用` / `悬浮·抱持`

**Post-criteria**

| Expected | How to read |
|---|---|
| Each piece's type ∈ the four enum values above | “Type” column of the placement table |
| Ring pieces: all 12 sectors around the hole center have material, chosen group radius ≥ 60% of the largest ring | Probe report |

**STOP**
- Probe reports `找不到环状结构`, or the type can't be decided → hand back to a human with the grouping table

### Step 3 · Place one piece and rerun　🤖

**Preconditions**
- [ ] **Place only one piece at a time**; don't start the next until the previous one passes the criteria

**Execution**
1. Run the menu item `配饰装位` of `AccMountA2.cs` (how each kind of piece is attached is in the subpages)
2. **Run again** without changing parameters
3. Readback check + armature height self-check; if a change is invalid, revert precisely with `PrefabUtility.RevertPropertyOverride`, not the undo stack

**Post-criteria**

| Expected | How to read |
|---|---|
| Ring pieces: eccentricity < inner radius and angle < 12° | That piece's row in the placement report |
| `c.parent == mount` is true; BoneProxy count == 0 | Assert after attaching; whole-tree query by component |
| Each bone ≤ 30cm from its parent bone | Measure each one; report prints the maximum |
| Both reports identical line by line, world position difference == 0 | Diff the two reports |
| `|eye.L.y − 基线| < 0.02` | Self-check output line |

**STOP**
- The report contains `找不到环状结构` / `骨长估算`; an assertion fails; a bone segment > 30cm
- Second run misplaced → teardown of mounts used `worldPositionStays: false`; fix the script and redo
- Object has been dirtied by repeated changes → delete and re-instantiate from the prefab

### Step 4 · Render, review, decide　🎨

**Preconditions**
- [ ] The observation channel can reproduce the target phenomenon: offscreen rendering goes through edit time and doesn't simulate PhysBones ([Observation scope](troubleshooting/observation-criteria.md))

**Execution**
1. Run `AccShots.cs` (four per piece) and `HeadShots.cs` (six views + isolated shot for head pieces); combination images go to [70](70-regression-testing.md), measured in delivery state
2. Per [05](05-multi-model-review.md), feed normal viewpoints (full-body front / three-quarter / back / head close-up), not face-hugging close-ups
3. For `flare` (±1) and shape key weights (0 / 100), render two comparison images each; a human chooses; write back into the placement table

**Post-criteria**

| Expected | How to read |
|---|---|
| `Renderer.bounds` intersects the skinned vertex bbox | Print both boxes side by side |
| Images per piece == 4, head pieces +7; no all-black images | Count per piece; non-zero pixel fraction > 0 |
| Models agree; “floating / clipping / misplaced” count == 0 | 05 output merged per object |
| `flare` and shape key weights written back into the placement table | Corresponding columns non-empty |

**STOP**
- All black, or “log all green but image empty” → check for same-name meshes and bounds drift; don't adjust the position
- Models contradict each other → re-feed with normal viewpoints; don't adjudicate by looking at images yourself
- Something is pointed out → first suspect the reference surface and author intent (common pitfalls); fix one thing, then go back to step 3

---

## Ring finger radial (user convention)

- One radial switches **which finger it's worn on**: 0–7 = left little, left ring, left middle, left index, right index, right middle, right ring, right little
  (no thumbs). **This radial doesn't handle on/off**; default 6 = right ring finger.
- One copy per finger for all eight, each with its own `FitBand`; the radial switches “which copy is active”.
- ≥2 accessories in the same position (two kinds of halos, two necklaces…) → **switch from a Toggle to a radial**:
  0=off, 1=accessory 1, 2=accessory 2… See [60 Menu and animator layers](60-menu-and-animation-layers.md).

## Acceptance viewpoints (`AccShots.cs`)

Framed by the accessory's **own bounding box** — AvatarPortrait's hand close-ups are framed by **bones**, and an accessory that's slightly off runs out of frame.

| View | What to look at |
|---|---|
| **Along the axis** | Looking down the limb: whether the ring encircles the limb cross-section is obvious at a glance |
| Side | Fit between ring and limb, decoration orientation. **Pick the side facing away from the palm center**, otherwise the neighboring finger blocks it squarely |
| Top | Overall impression |
| **solo** | Base avatar fully hidden, only this piece kept. Indispensable for pieces buried in hair/clothing (headwear measured: all three images were just hair) |

## Acceptance checklist

- [ ] Probe has run; every accessory's armature structure and mesh grouping is on record
- [ ] Every piece in the placement report is `✓ 套住` (“✓ encircled”), with no `找不到环状结构` or `骨长估算`
- [ ] Idempotent: running `配饰装位` twice in a row gives identical hierarchy and coordinates
- [ ] No leftover BoneProxy in the scene
- [ ] Every accessory has along-axis / side / top / solo images, no clipping, no misplacement
- [ ] Combination screenshots with every outfit (see [70](70-regression-testing.md))
- [ ] Delete the probe script and the entire `Assets/Editor/AvatarGen/` before delivery

## Subpage index

- [Ring-part pose solving](55-accessory-placement/ring-part-pose-solving.md) — rings / wrist cuffs / headwear and other pieces that ring a limb: how to compute the pose, the four points forced out by review
- [Rigged accessories](55-accessory-placement/rigged-accessories.md) — ears/tails and other packages with their own armature: how to attach, idempotency, fixing bone-segment length
- [Common pitfalls](55-accessory-placement/common-pitfalls.md) — hit by every piece: showcase images, scaling, reference surfaces, criteria contamination, same-name meshes, mirroring, shape keys, bounds, same-frame shots
- [Bend test after adding bones to the body](55-accessory-placement/adding-body-bones-bend-test.md) — newly inserted bones like the tongue: test renders must include that pose's blend shapes and linear skinning; measure self-intersection/creases before looking at images; bend radius lower bound
- [Rebinding the armature and occupancy](55-accessory-placement/rebinding-armature-and-occupancy.md) — which copy to change when rebinding an armature; when judging “is this spot occupied”, **occlusion ≠ occupancy**
