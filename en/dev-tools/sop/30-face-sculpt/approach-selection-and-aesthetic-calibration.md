> 🌐 English translation · [中文原文](../../../../开发工具/SOP/30_捏脸/路线选择与审美校准.md)

> ← [30 · Face sculpting](../30-face-sculpt.md) · [Tool choice and probing what keys mean](tools-and-key-meaning-survey.md) · [Baking and compensation](baking-and-compensation.md)

# Route selection and aesthetic calibration

Measured conclusions from the 2026-09-07 Project B_Milfy order. **They overturn this procedure's original wording that "route 1 is an option".**

## 1 · Route 1 (never going through Blender) **doesn't hold**; default to route 2

The original claim was: set blendShape weights on the SkinnedMeshRenderer on the Unity side and bake at build time with
**AAO FreezeBlendShape**, so the FBX isn't touched by a single byte and the face-tracking sha256 check passes.
**Both premises are wrong.**

### ① AAO Freeze doesn't do eye-close compensation, and sculpting the eyes requires compensation

AAO baking = `新基础 = 基础 + delta×权重` (new base = base + delta × weight), then deletes that key,
**leaving the deltas of the other 600-plus expression keys untouched**. The displacement of `eye_blink_1` was computed from the **original** eyelid position;
once face sculpting enlarges the eyes or raises the upper eyelid, the eyes can't close fully.

Measured (in Blender, the nearest distance between the upper and lower eyelid margins with the eyes closed):

| | Open-eye fissure | Closed-eye residual |
|---|---:|---:|
| Base avatar default | 16.65 mm | **7.37** (criterion zero point) |
| After sculpting (24 keys) | 19.17 | **8.76 = +18.8%** |

**The main culprits are face-shape keys like `face_eye_big` / `face_eye_height_up`** (enlarging the eyes), not eyelid keys.
→ As soon as eye size is changed, compensation is required, and compensation can only be done in Blender.

### ② "Changing the FBX makes Triturbo face tracking uninstallable" is wrong

The original comment at `FaceTrackingInstaller.cs:167`:

```csharp
//we can not find the version by sha256
//=> user do edit on the fbx
```

**The vendor specifically designed a fork flow for "the user has modified the FBX"**: on sha256 mismatch it pops up a version dropdown asking "which original version was this forked from",
records the internal id as `{版本}_fork` ({version}_fork), and then lets you choose the target `original` / `current_in_use`.
**The mismatch is an entry point, not a blocker.**

The difference between the two target paths (`BlendShapeAppender.cs`):

| Path | Lines | Validation | Use |
|---|---|---|---|
| `original` | 141-151 | Checks vertex count + `m_VerticesHash`; on mismatch `return null` | **Only valid for unmodified meshes** |
| `current_in_use` | 450-472 | Writes channels directly by control-point index, **checking neither vertex count nor hash** | Fork path |

→ **The fork route must use `current_in_use`, and it has zero validation.**
So "the re-exported FBX's vertex count and index order must match the original" has to be **verified by us**; the tool won't report errors.
Add this to the binary self-check in 30b step 5.

## 2 · One exception is allowed: **custom keys from closed-form transforms**

The hard rule at the top of the page forbids "AI sculpting vertices by feel", not "computing displacements by a closed-form formula".
When **the vendor keys genuinely lack the needed direction** (with measured evidence) **and the user explicitly agrees**, you may build a custom key.

The example in this order: the outer eye corners needed to be "rotated flat", and the vendor had no usable rotation key —
`eyelid_corner_rotate_down` has only **18 vertices**; pulled to 400 it's still barely visible, and it also shaves 2.06–2.79 mm off the upper eyelid arch;
`face_eye_height_up/down` mainly changes the eye fissure (20.57→14.92). The ceiling for vendor keys suppressing the outer-corner upturn is **−13%**.
The custom key achieved **−36%**.

### Four rules for building such a key

1. **It must be a closed-form transform** (rotation/scale/translation + mask), expressible as a formula, not per-vertex hand-tweaking.
2. **Pick the right axis for layered-card base avatars.** Milfy's eyes are dozens of layered cards spaced 0.03 mm apart.
   For an in-plane rotation around the **depth axis**, the depth component of the displacement is always 0 → the layer spacing doesn't change at all;
   **rotating around any other axis scrambles the layer order**, causing z-fighting straight away.
3. **Compute the displacement from "the blended shape at the moment the key is built"**: `新键位移 = R(当前混合) − 当前混合` (new key displacement = R(current blend) − current blend),
   so that with all other keys on, the result is an exact transform of the current face. **Rebuild it after the user changes other keys.**
4. **Two acceptance checks**: ① how many affected vertices fall within the mask's full-strength region (in this order 89.5% of the eyelid margin inside, 0 outside);
   ② verify function isn't broken using a criterion **unaffected by sampling drift** (in this order: with eyes closed, the distance from upper-eyelid vertices to the nearest lower-eyelid vertex,
   8.699/8.667/8.907 mm at rotation 0/1/2, ±2.4%).

⚠ **Don't use criteria that drift with the deformation.** In this order I first measured closure with "sampling columns fixed at the undeformed positions",
and reached the false conclusion "rotation increases the closed-eye residual from 6.13 to 6.62" — in fact the vertices had rotated out of the sampling columns.

## 3 · Aesthetic calibration: **don't start from the ceiling**

The biggest efficiency loss in this order: at the start I maxed out every axis (child 1.0, cheek_puku 1.0, three enlarging keys 1.0),
and the user **cut back every single one**, over a dozen rounds back and forth. Worse, that set of enlarging keys got welded into the baseline for the next 11 rounds;
in the eye-shape sweep I only probed upward (to 1.3) and **never tried downward**, and in the end the user cut it by 83% themselves.

**Start per axis, in opposite directions** (rationale in `<订单>/_捏脸审美校准.md`):

| Axis | Starting point |
|---|---|
| **Enlarging** (`face_eye_big` / `face_eye_height_up` / `face_child`) | **Start weak** (0.15–0.30) |
| **Curvature** (`eyelid_center_up` / `eyelid_corner_wide_1` / `lower_eyelid_flat`) | **Start at full or even extrapolated** (1.0–1.5) |

Record the user's aesthetic keywords as the calibration basis: write them as a **geometric profile** (transferable across base avatars; key values are not), not a list of key values.

## 4 · Infer aesthetics from the "difference", not the final values

**The strongest signal comes from the keys where "the AI maxed it out and the user cut it".**
Typical pattern: the AI maxes out an enlargement key, the user cuts it sharply and adds a related key themselves — such a difference states the preference directly (e.g. enlarge A, not B); the final values are whatever the user signs off on, recorded in the work log. This can't be seen from final values alone; it's only readable from the difference between "proposal vs. final".

**So archive the user's own words.** When writing the calibration document in this order, a subagent pointed out that "the original words existed only in the task brief; the project documents kept no copy" —
so `_捏脸决策原话.md` was created separately afterwards. **Round-by-round decisions and the original words are the evidentiary basis for inferring aesthetics, and they're gone when the session ends.**
