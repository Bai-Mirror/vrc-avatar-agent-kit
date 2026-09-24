> 🌐 English translation · [中文原文](../../../../开发工具/SOP/30_捏脸/烘焙与补偿.md)

> ← [30 · Face sculpting](../30-face-sculpt.md)

# Details of blend shape baking and expression compensation

The problem this page solves: for face sculpting of the type where the user **directly sets dozens of blend shapes to certain values**, how to bake it into the base mesh without breaking expressions.
The steps and criteria are in the deterministic step table on the main page; this page has the details of how to do each step.

The first half of the SOP covers **geometric-scaling** face sculpting (a similarity transform on a whole group). The other, more common kind is
**the user directly setting dozens of blend shapes to certain values** — handled completely differently; the process is as follows.

| # | Step | Criterion |
|---|---|---|
| 1 | Keep three restore points | `*_unity_original.fbx` (the FBX before overwriting), `*_sculpted_prebake.blend` (sculpted, not baked), `*_baked.blend` (baked, not compensated) |
| 2 | Inventory the keys to bake | Non-zero and **not set by me** (e.g. `pupil_off`, which I set for effect, should be excluded; once baked in, if animation later pushes it to 100 it gets applied twice) |
| 3 | Exact-reconstruction baking | See below on this page. **Acceptance: max difference between `Basis` and `mesh.vertices` = 0mm** |
| 4 | Eye-close compensation | See below |
| 5 | Full blend shape check | `shapekey_audit.py`, see below |
| 6 | Restore material slots → export → binary self-check | See "Material slot trap" below |
| 7 | Overwrite FBX → **reassign materials + scan for empty slots** → in-engine render | See below |

### Eye-close compensation must be done per eye

The remembered formula `新键 = 新Basis + 原始位移 − ratio × eyemask × d` (new key = new Basis + original displacement − ratio × eyemask × d) is correct, but **both the coefficient and the mask must be per eye**:
for single-eye keys (`blink_L` / `ウィンク`) the closure is a diluted value averaged over both eyes, and a symmetric mask would also undo the sculpting of **the eye that isn't closed**.
How: split the upper-eyelid cluster into two by the sign of x → take each centroid as the eye center → build a smoothstep mask for each, full at 30mm / zero at 50mm → compute each ratio separately.

**How to determine closure**: on some base avatars `blink` only pushes the upper eyelid and the lower eyelid doesn't move at all (輝夜 (Kaguya) is like this: all 1166 points move downward).
In this case the remembered definition "upper eyelid moves down + lower eyelid moves up" can't get the lower eyelid, and degenerates into "the average downward movement of the upper-eyelid cluster", which is fine.

Blender shape keys store absolute coordinates while Unity BlendShapes store relative deltas, so the compensation needs on the two sides run in opposite directions (changing the base mesh in Unity naturally works; only closing-type expressions need compensation).

Eye-close compensation should cancel additively (`新delta = 旧delta − c·W·S`, new delta = old delta − c·W·S), not amplify multiplicatively; the criterion is the eyeball exposure rate (ray occlusion), not eyelid convergence (corrected 2026-09-08).

### Full blend shape check (mandatory after baking)

```bash
python 开发工具/通用工具/shapekey_audit.py <工程目录> --baked <烘焙清单.json>
```

The bake list is `{key name: bake weight 0-100}`. The tool iterates over every `.anim` in the project, takes the peak of each `blendShape.X`,
adds the baked amount, and >100 means out-of-range extrapolation. The output also includes two tables: "baked keys written in the resting expression" (double stacking) and
"baked but not driven by any animation" (safe).

> The result may be **zero out-of-range** — in this 輝夜 (Kaguya) order, of 1431 clips, none of the 46 baked keys were driven.
> Then don't change the animations just to "do something". Having checked and confirmed there's nothing is itself an output.

### Out-of-range scan scope and "it gets clamped in-game" (trigger: before leaving extrapolated values in a deliverable)

**The scan source isn't only `.anim`**; it must also cover:

- **Set values of MA ShapeChanger** (historically measured: some projects write face values via Set, and some have a foot Set of 60; panel value ≠ actual effect)
- **`m_BlendShapeWeights` in scenes / prefabs** (baked default values are also here; P1/2 have non-zero default weights)

> **Addendum (measured 2026-09-21)**: not just entering Play — **calling `nadena.dev.ndmf.AvatarProcessor.ProcessAvatar(clone)` in edit mode
> for build verification also sets `legacyClampBlendShapeWeights` to 1, and doesn't restore it automatically like exiting Play does**.
> I ran ProcessAvatar 4 times this round, and only found ProjectSettings dirty at wrap-up via `git status`.
> **Checkable question**: did I run ProcessAvatar / enter Play this round? If so, take a look with `git diff ProjectSettings/`;
> if it's a side effect, restore with `git checkout --` and don't commit it.

> ⚠ **Pending falsification (E-未核-08)**: whether `legacyClamp` (`PlayerSettings.legacyClampBlendShapeWeights`) is always 1 in edit mode in **projects without AAO**, whether a force-killed Play leaves 1 on disk, and whether `GetBlendShapeWeight()` returns the value before or after truncation — **none are empirically confirmed** (`G_legacyClamp结论.md`, 2026-09-18 only checked Project A). **Don't use it as settled yet.**
> **The only confirmed facts**: with AAO installed and Enabled, the clamp flag is 0 in edit mode (extrapolation can be previewed) and 1 in Play (consistent with the VRChat client); the client clamps blend shapes to 0–100 (SDK 3.5.1 release notes).

- **Review item**: whenever >100 / <0 extrapolated values are left in a deliverable, first ask "what does it look like under the Play convention (`legacyClamp`=1)" — **judge by rendering in Play**; don't take the edit-mode preview as the client's result.
- **Trade-off**: extrapolation is a great way to get reverse deformations for free, at the cost of "looks good in the editor, the excess isn't visible in the client"; the two sides are asymmetric, so at minimum list the out-of-range entries and judge each one; **if you can't meet it, fall back to a plan within the 100 limit**; don't rely on "it should be fine".

### Index-based weight overrides after deleting keys: don't casually restore the ones writing 0 (2026-09-19 Project B)
- **Trigger**: after baking deleted blend shapes (Project B went 668→644), when cleaning up prefab overrides in the scene written by **index**, such as `m_BlendShapeWeights.Array.data[N]`.
- **Ask**: "what's the source prefab's value at this index?" — the vendor prefab's default weights are also stored by index, and after deleting keys the same index points to **a different key**.
- Example: 2 overrides remained in Project B's scene (448 and 498, both writing 0). After restoring they became `mouth_〇=70` and `tooth_yaeba_short_R=45` — exactly the vendor's factory `mouth_Λ=70` and `mouth_narrow=45` landing misaligned on the new indices; those two 0 overrides were **deliberately suppressing the misaligned defaults**, and have been restored.
- **How to do it**: before restoring, read each `PrefabUtility.GetCorrespondingObjectFromSource(smr).GetBlendShapeWeight(N)`; keep the 0 override where the source value is non-zero (or change the prefab source). Acceptance = all weights on the face mesh are 0 (or equal to the finalized values), not "number of overrides is 0".

## Acceptance (by numbers, not by eye)

| Metric | Threshold | How to compute |
|---|---|---|
| Seam splitting | Should not grow significantly after the transform | For cross-card vertex pairs originally <0.3 mm apart, measure the distance after the transform |
| Depth change | Max `\|Δy\|` < 2 mm | Beyond that it may poke through the face skin |
| Expression extrapolation | Curve peak + baked amount ≤ 100 | Iterate every `.anim` in the project; the fix is to change the written value to `100 − 烘焙量` (100 − baked amount); for multi-keyframe curves scale the whole curve proportionally |

**After exporting the FBX, a binary self-check is mandatory**: compare counts such as `UnitScaleFactor` / `LimbNode` / `PoseNode` / `BlendShapeChannel`
against the vendor original. **Static validation can't catch a corrupted bind pose** — this order rolled back once because of it.

## Pitfalls in export and self-check

### The material slot trap (I fell in; the user spotted it at a glance)

**Before export, the material slots must be restored to the vendor's original.** Custom materials temporarily swapped in to see the face clearly in Blender,
once exported along with it, misalign the material array on the Unity side — this time on 輝夜 (Kaguya), Body's three slots were replaced with two custom materials,
and as a result **the face got the eye material**. The original material datablocks are usually still sitting in `bpy.data.materials`; just point back to them.

Add one item to the binary self-check: **the number of occurrences of the vendor material names equals the original**.
In the wrong version the `Model` node count also differs (1986 vs. 1987 in the original), because one slot was merged away.

Two things you **must** do after overwriting the FBX (swapping the FBX resets the `sharedMaterials` of renderers in the scene):
re-run every "assign materials" tool, and run an empty-material-slot scan.

Two FBX export parameters that must be changed: `apply_scale_options='FBX_SCALE_UNITS'` (the default `FBX_SCALE_NONE` is the number-one killer), `mesh_smooth_type='OFF'`; the `add_leaf_bones` operator defaults to True and must be turned off explicitly.

When overwriting the FBX, don't change a single field of the Unity-side `.meta`; overwrite only the `.fbx` itself; don't copy or rename materials in Blender (that creates extra `.001` materials).

File size is not a reliable sentinel (the successful 26.3MB build and the 16.5MB original are both normal); use the binary self-check.

### Don't draw conclusions from geometric criteria you improvised yourself

This round I wrote a criterion for "does the eyeball show when the eyes are closed" (highest point of the eyeball cluster − lowest point of the upper-eyelid cluster),
and it measured +36mm — larger than the whole eye; the two clusters simply aren't comparable points.
For any geometric criterion you set up on the spot, first verify it against a state with a **known answer** before using it; if it fails verification, don't draw conclusions from it —
render directly and hand it to human eyes and Gemini. Related: [The shape of a criterion](../troubleshooting/observation-criteria/shape-of-a-criterion.md).
