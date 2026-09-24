> 🌐 English translation · [中文原文](../../../../开发工具/SOP/问题定位/透明排序与抓屏.md)

# Troubleshooting · Transparency sorting and screen grabs

> The symptom looks like this: **"through some semi-transparent effect, you can't see what's behind it"**,
> and it's fine from another angle / fine with another outfit — it looks random, but it's actually deterministic.

## First tell which category it is

Three mechanisms all cause "the thing behind disappeared", with completely different criteria:

| Category | Criterion (checkable) | Symptom signature |
|---|---|---|
| **A Grab timing** | Some material uses a `GrabPass`-type shader (lilToon's Refraction / Gem / RefractionBlur) | Looking through it, **everything queued after the grab point is gone**, yet the background is correct |
| **B Semi-transparent depth writes** | `renderQueue ≥ 2500` and `_ZWrite = 1` | If it draws first, it depth-culls entire transparent objects drawn later; draw order depends on bounds-center-to-camera distance → changes with angle |
| **C Frustum culling** | `SkinnedMeshRenderer.bounds` smaller than the actual post-skinning extent | **The whole renderer** disappears at once, not just a piece |

For C, see [Observation criteria](observation-criteria.md) (note that source-scene bounds are often not the delivered state's).

---

## A · Grab timing: the most counterintuitive category

### Mechanism

`GrabPass { "_lilBackgroundTexture" }` is a **named grab**. Unity's rule is:

> **Grab only once per frame; the grab point = the first object in the frame that uses this name**;
> all later shaders using the same name **share that one image**.

So **anything with render queue ≥ the grab point is invisible through any grab-pass object** —
it hadn't been drawn yet when that image was grabbed.

In lilToon, the shaders that use this name are **Refraction / RefractionBlur / Gem** (including the Multi versions).
Common grab-pass materials on an avatar: gems, halo glass, eye effects, holographic panels.

### Why it behaves as if "intermittent"

It's not sorting jitter. **Viewing angles where "that effect happens to be in front of the target" are simply rare.**
Large, fixed things (back-mounted accessories, long hair) are more likely to be noticed;
a small panel is only visible once in a while when it drifts past a certain position.

**Another genuine source of "intermittency"**: the grab point is determined by **the frontmost grab-pass material in the frame**,
and parts like gems/halos are often attached to **toggleable accessories**. Toggle an accessory on and off and the grab point jumps —
that's where "sometimes visible, sometimes not" comes from.

### Debugging steps

1. List **all** grab-pass materials on the avatar (shader name containing `Refraction` or `Gem`) and their `renderQueue`
2. Take the **smallest** queue among them = the frame's grab point
3. List all materials with `renderQueue ≥ grab point` — this is the complete list of "can't be seen through the window"
4. Compare that list against the symptoms the user reported; if they match, it's confirmed

### Fix: squeeze from both ends

Changing just one end is often not enough, because the grab point takes the **minimum**:

- **Move the grab-pass materials back as a whole** to a large enough queue (e.g., 3050)
- **Move the things that must be visible forward** to before the grab point

The second one is often required: as long as a single grab-pass material stays in front, it pins the grab point.

> **Prioritize consistent behavior over optimal behavior.**
> If some grab-pass material can't be moved (e.g., a recoloring animation will swap it back to the vendor original; see below),
> prefer pulling "the things that must be visible" in front of it, so that **both cases behave the same** —
> "sometimes right, sometimes wrong" is harder to debug and harder to explain than "consistently wrong".

### Two traps before you start

**① Copy vendor materials before changing them**; don't edit the originals.

**② Materials that a recoloring animation swaps out must not be touched.**
If recoloring is "swap materials between parallel directories" (`Material/Black/X.mat` ↔ `Material/Pink/X.mat`),
on recolor the animation points `m_Materials` back at the vendor's copy, your modified copy gets pushed out,
and the result is "change the color and it breaks again". Criterion: the material path lies in a recoloring parallel directory.
**Recoloring clips we generate ourselves are not in this category**; point their keyframes at the copy: on 2026-09-18 Project A's "headpiece color" clip referenced the vendor original (2450),
which after build pushed out the copy in the scene, and the user saw "transparent through the headpiece and hairstyle". Checkable question: "For every grab-pass material referenced in PPtr curves, is the queue ≥ the grab point?"

### ⚠ Whether offscreen rendering can verify this category depends on the render path — do a positive control first

On 2026-09-03 (Project A), `GrabPass` didn't work in that offscreen path; grab-pass materials rendered as **solid color blocks**,
and judging from such images gives completely wrong conclusions (taking solid blocks as a reproduction of the defect).
On 2026-09-18, in review tool T3 v2 (Play mode, Vulkan, `Camera.Render` to RT), `GrabPass` **did work**:
window transmittance t≈1; moving another grab-pass material's **runtime instance** queue up to 2450 to reproduce the pre-fix grab point,
T3 detected 7 items attributed to the hairstyle, versus 0 before the change (supported by both agy providers).

- **Trigger moment**: before using offscreen images to judge any grab-pass (Refraction / Gem) phenomenon.
- **Checkable question**: "Can this render path reproduce a grab-point problem I **manufactured on purpose**?" — in Play, change only the `renderQueue` of `renderer.materials` (instances, not saved to disk) as a positive control; if it can't reproduce, this path can't serve as a criterion.
- **Trade-off**: the "queue table" is always the primary criterion (provable, can be read back, recomputed whenever state changes, no render needed); offscreen images are supplementary only after the positive control passes, and the final look is still judged in the Play Game view.

### ⚠ "Refraction strength 0" doesn't mean refraction isn't in use

We've seen vendors use a refraction shader with `_RefractionStrength = 0` **as transparency** —
the panel's "transparency" is entirely composited by the screen grab; the material itself has no alpha.
Swap it for an ordinary transparent shader and the panel becomes a **solid slab**.

So: seeing refraction strength 0 and casually swapping the shader is wrong. First figure out where its transparency comes from.

---

## B · Semi-transparent depth writes

If a material with queue ≥2500 has `_ZWrite = 1`, when it draws first it **depth-culls entire** transparent objects ordered after it.
And who draws first depends on **the bounds-center-to-camera distance** → the symptom is necessarily "gone from another angle".

A transparent overlay writing depth is almost always an author's slip. Just change to `_ZWrite = 0`;
leave `ZTest` alone — it will still be hidden when blocked by opaque objects.

**But first confirm its transparency isn't composited by a screen grab** (see above), or the symptom will remain after the change.

---

## Common checks

Get the data needed for all three categories in one go:

- For every material slot of every renderer: **material name / `renderQueue` / `_ZWrite` / shader name**
- Pick out shader names containing `Refraction`/`Gem` and sort by queue ascending → the first row is the grab point
- `SkinnedMeshRenderer`'s `bounds` vs. the positions of **the bones its vertices are actually bound to**

Note on the third: `smr.bones` is the full table, most of which are bones used by other parts;
filter by indices with `weight > 0` in `mesh.boneWeights`, or you'll get a pile of false reports.
