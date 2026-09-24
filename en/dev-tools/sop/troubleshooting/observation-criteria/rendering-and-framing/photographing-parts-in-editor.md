> 🌐 English translation · [中文原文](../../../../../../开发工具/SOP/问题定位/观测口径/渲染与取景/编辑器里给局部拍照.md)

> ← [Rendering and framing](../rendering-and-framing.md) · [00 · Master table](../../../00-overview.md)

# Taking comparable photos of a part (eyes/hands/accessories) in the Editor (2026-09-21, Project B)

**Trigger**: you need to repeatedly render the same part in the Editor (without entering Play), for A/B or frame-by-frame sequences.

The benefit of not entering Play is that ProjectSettings aren't touched and there's no domain reload wait; the cost is three pitfalls you can't dodge even once.

## 1 · Skinning is stale → always `BakeMesh` into a static mesh before rendering

In edit mode, `Camera.Render()` renders **the previous frame's skinning result**. Within one synchronous block,
the two images from "change blend shape weight → Render" will be **pixel-for-pixel identical**, looking like "the change didn't take effect".

```csharp
var baked = new Mesh();
smr.BakeMesh(baked, true);                  // useScale=true
var proxy = new GameObject("__Proxy");
proxy.transform.SetPositionAndRotation(smr.transform.position, smr.transform.rotation);
proxy.transform.localScale = Vector3.one;   // scale is already baked into the vertices
proxy.AddComponent<MeshFilter>().sharedMesh = baked;
proxy.AddComponent<MeshRenderer>().sharedMaterials = smr.sharedMaterials;
```
To change blend shape state, `SetBlendShapeWeight` again → `BakeMesh` once more; **don't** expect Render to keep up.
(Don't swap the mesh by changing an existing renderer's `sharedMesh`: bind poses/bone order won't match, and the whole face will disappear.)

## 2 · Isolate with a free layer + `cullingMask`; don't turn off other people's renderers

```csharp
int layer = -1;
for (int i = 31; i >= 8; i--) if (string.IsNullOrEmpty(LayerMask.LayerToName(i))) { layer = i; break; }
proxy.layer = layer;
cam.cullingMask = 1 << layer;
sceneLight.cullingMask &= ~(1 << layer);    // remove this layer from the scene light; remember to restore after rendering
var lg = /* your own directional light */; lg.cullingMask = 1 << layer;
```
Benefit: no existing object's enabled state/layer is touched; after rendering just `DestroyImmediate` the temporary objects,
and the scene's `isDirty` isn't polluted. In VRChat projects layers 8–21 are taken; 31 is usually free (**look it up every time; don't hard-code it**).

## 3 · Time must be pinnable, or sequences aren't reproducible

Effects written with `_Time.y` in the shader can't be precisely controlled in the editor. **Add an offset that defaults to 0 to the shader**:

```hlsl
_MLTimeOffset ("Time offset (s)", Float) = 0
...
float t = _Time.y * _MLTimeScale + _MLTimeOffset;
```
When rendering, set `_MLTimeScale` to 0; time is then fully determined by `_MLTimeOffset`, deterministic frame by frame.
The default-0 + multiply-by-scale form **doesn't change live behavior**, so it can stay in the shader long-term as a test hook.

**Don't dirty assets with temporary parameter changes**: make an instance with `new Material(srcMat)`, set `hideFlags = DontSave`,
and change the instance, not the `.mat`.

## 4 · Quantifying beats eyeballing: use the same frame with "the effect turned off" as the control

Eyeballing frame by frame misses things. Standard practice: first render a control frame with "the effect turned off" (e.g., intensity set to 0),
then for each frame compute `pixel - control`, and count **the number of pixels whose delta > threshold** and **the peak delta**.
These two numbers directly answer "is the effect actually on screen" and "which frame is strongest", and also allow side-by-side comparison across approaches.

---

# Three pitfalls of edit-time rendering itself (merged 2026-09-21 from the "Rendering and framing" main page)

## 5 · After changing blend shapes at edit time, a single `Render()` captures the skinning from **before** the change

### Trigger
**After you `SetBlendShapeWeight` (or do anything that changes skinning) in edit mode, when you are about to `cam.Render()` an image.**

### Question
**"How many times did I render before this image?"** If only once, the first `Render()` only triggers the skinning update and captures the previous frame's skinning.

```csharp
smr.forceMatrixRecalculationPerRender = true;   // or smr.enabled = false; smr.enabled = true;
cam.Render();
cam.Render();                                    // ★ only the second one is correct
```

Material property changes are **not affected** (`SetTexture` / `SetColor` take effect immediately); only skinning / blend shapes lag one frame —
in the same script the material-changing part is right while the blend-shape-changing part is fake, which is why it hides so well.

### If the answer is wrong
**Render twice**; and before taking any blend-shape-related image, first run a **0 vs 100 control sample** (use a key known to make a huge difference, such as full eye close):
if even the control shows no difference → the capture pipeline is broken; void the whole batch.
The cost is asymmetric: one extra render costs milliseconds; one render too few turns an entire batch of acceptance images into the same image, and leads you to misjudge a vendor key as "useless".

### Evidence (2026-09-08)

| Strategy | Differing pixels | Max diff | Verdict |
|---|---:|---:|---|
| Single `Render()` | **0 (0.00%)** | 1/255 | ✗ broken |
| `forceMatrixRecalculationPerRender` + double render | 88002 (23.28%) | 191/255 | ✓ |
| `enabled` toggle + double render | 88002 (23.28%) | 191/255 | ✓ |

Symptom: in a set of 5 "acceptance images" for eye-close keys, **4 had identical md5s and the 5th differed only by compression noise** — half-closed and fully closed eyes can't look the same; that should have been the stopping point.
Later, the same tooling was used to "verify" whether a key could hide the pupil, returned "zero effect", and nearly led to judging that vendor key useless.

> **Debugging order for "different inputs rendered identical pixels": suspect the capture pipeline first, then that the input didn't take effect, and only last the object under test.**
> Same family as 3 · duplicate images, different cause: 3 is the scene not being reloaded, this one is skinning not being updated; when pairwise pixel diff is 0, **check both**.

---

## 6 · Baking **doesn't save** edit-time rendering either (if what you bake is the same stale state)

### Trigger
**When you plan to "bake once first, then render acceptance images in the editor".**

### Question
**"In the merged controller after baking, is there any layer writing `blendShape.Shrink*` / `blendShape.Toe_*`?"**

### If the answer is wrong
If yes → those shrink keys are **animator layers**, not evaluated at edit time; the render shows them **not applied**, and all images are void.
The only options are shooting in Play mode (GestureManager) or just asking a person to take a look.

### Why this happens
MA's reactive components (ShapeChanger / Object Toggle / Material Setter) **are not always statically baked into the mesh**.
If the controlled object is **animation-toggled** (outfit root hanging off the outfit-switch wheel), MA can only implement the effect as a conditional animation —
generating a layer named `MA Responsive: <mesh name>`. Static baking only happens when "the object is fixed on at build time".

### Trade-off
- To render at edit time → the controlled object must be fixed on at build time, but then there's no outfit switching; not realistic.
- So this is essentially a **hard constraint**: in projects with outfit switching, acceptance of shrink-key-type work **must go into Play**.
- The cost is asymmetric: edit-time rendering is cheap but **the conclusion is wrong**; shooting in Play is expensive but correct.
  A wrong conclusion leads to "changing something that was already right" — this order wasted a round of outfit-switch clip edits because of it.

### Evidence (2026-09-08, Project C)
Of the 109 layers in the merged controller after baking, **15** were `MA Responsive:` layers writing `Shrink_Foot` / `Toe_heels` /
`Toe_highheels` / `Shrink_Knees` / `Shrink_Elbow`.
When the baked avatar was rendered in the editor, LUNALICE's `Shrink_Foot=100(Delete)` had no effect at all; the whole foot stuck out of the shoe.

**A labor-saving side observation**: in those 15 layers MA **automatically propagates blend shapes to every `BlendshapeSync` mesh**
(`Body_base` + stockings + socks + toenails written together). Hand-writing "one curve per renderer" is redundant.

---

## 7 · Paths in the baked avatar are **not** the source project's paths

### Trigger
**Doing anything that "finds objects by path" on the baked clone**: outfit-switch renders, combination matrices, force-showing suppressed objects.

### Question
**"Does this path still have this name in the baked avatar?"**

### If the answer is wrong
AAO's flattening pass turns `_Acc/Acc_GothicRoseFox/Ears` into **a direct child of the root**, named
`_Acc$Acc_GothicRoseFox$Ears$138` (the numeric suffix may change on every bake; don't hard-code it).
`root.Find(source path)` returns null → the following `SetActive` **silently does nothing**, no error, no warning.

The resolver needs **four** fallback levels; missing any one of them misses an entire class of parts:

| Level | How to find | Which kind of rename it covers |
|---|---|---|
| 1 | `root.Find(源路径)` | Untouched ones |
| 2 | `路径.Replace('/', '$')` prefix match against root children | AAO flattening: `_Acc/X/Ears` → `_Acc$X$Ears$138` |
| 3 | Match by last segment `$<name>` / `*$<name>$*` | Middle segments truncated after flattening |
| 4 | **Search the whole tree by the bare last-segment name; accept only a unique hit** | **Parts moved by BoneProxy have bare names in the baked avatar** (`HeadDress`, without any `$`) |

⚠ Level 4 must carry the "unique hit" precondition, otherwise it will pick an arbitrary one among same-named parts. If ≥2 are found, report "ambiguous"; don't guess.

### Criterion (no human viewing needed)
After rendering a batch, compute each image's MD5; **any two byte-identical images = state didn't switch; images unusable**.
Real renders have anti-aliasing jitter; two renders of the same state aren't necessarily byte-identical, let alone different states.

### Side note
AAO **really deletes objects that are never enabled** (in this order `Rose_Ears`/`Roses_Tail` were written 0 in all four tiers → they don't exist in the baked avatar).
Finding them by path returns null; this is a correct optimization, not a defect — don't "fix" it.

### Evidence (2026-09-08, Project C)
Ten-cell conflict close-ups: in the previous version four of six images had the same MD5 — all ten renders were the same "no clothes on at all" state.

## 8 · Don't use PIL's default font for Chinese text on annotated images (2026-09-21, pointed out by the user on the spot)

`ImageFont.load_default()`, and `ImageDraw.text()` without a font specified, **have no CJK glyphs**;
Chinese renders as a string of boxes (tofu). Only whoever receives the image can notice this; the script raises no error and the log is all PASS.

```python
import sys; sys.path.insert(0, "开发工具/通用工具")
from cjk_font import cjk_font
d.text((8, 8), "电光青", font=cjk_font(21), fill=(238, 238, 243))
```

`开发工具/通用工具/cjk_font.py` tries in order
`NotoSansCJK-Regular.ttc` (index 2 = SC) → Sarasa → NotoSerifCJK,
and **verifies that the bboxes of `电` and `□` are not equal** before returning — if none is found it raises, rather than silently falling back to boxes.

> **Checkable question**: the Chinese text on this image — did I **look at the rendered result**, or only see that the script didn't error?
> Trade-off: better to raise than silently degrade — sending a box-filled image to a client costs more than a crashed script.

> Related: [Three pitfalls of the render pipeline](three-render-pipeline-pitfalls.md) · [Occlusion-type criteria](../occlusion-type-criteria.md)
