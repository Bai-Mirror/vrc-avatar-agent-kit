> 🌐 English translation · [中文原文](<../../../../../开发工具/SOP/60_菜单与动画层/生成器实现坑/开关与曲线写法.md>)

# Generator implementation pitfalls · Toggle and curve authoring

> ← [Generator implementation pitfalls (index)](../generator-implementation-pitfalls.md)　Parent: [60 · Menu and animator layers](../../60-menu-and-animation-layers.md)

The problem this page solves: generated clips / curves that are **written correctly but don't take effect or have the wrong effect** — values, binding names, parent objects, vendor parameters, particles, appearance-variant steps.

> ②~⑤ of “six pitfalls every generator hits” are on this page; ① ⑥ are in [Saving and idempotency](save-and-idempotency.md).

### ② Acceptance images must be driven by **real animation data**, not manual SetActive

Manually posed images only prove “the state I think it is looks like this”; **they can't prove the animator layers will actually output that**.
Both ③ and ④ below were only exposed after switching to real data; under manual preview they're never visible.

Method: read the generated controller → decide from the parameter values which state each layer rests in → apply each layer's clip curves in order.
All layers in this project are Override, weight 1, WD=OFF, so “apply in layer order” is equivalent to runtime.
Reference implementation `A2State.cs`. Three dead ends are also recorded in that file's header
(`animator.SetFloat` can't reach FX parameters, `playableGraph` is ineffective, `AnimationMode` sampling gets rolled back).

### ③ The radial's “off” step value is **not 0**

Step i occupies `[i/N, (i+1)/N)`, and the program uses the interval midpoint `(i+0.5)/N`. The “off” of a three-step radial is **0.167**.
Consequence of writing the override layer threshold as `0.01`: the accessory is clearly off, but the override layer stays on Hide, **permanently suppressing the hat/gloves on the clothing**.
Always write the threshold as `1f / 档数`, never a constant.

### ④ A clip with only one keyframe has `clip.length` **0**

Part toggle and override layer clips are all single-frame. Any code like `if (clip.length <= 0) continue;` skips the whole layer.
When generating, add a tail frame at `t = 1/60` to single-frame clips, and don't use length as a gate when reading either.

### ⑤ Parent objects must be on too

The vendor outfit sits under `kaguya_cloth/`. Writing only the children's `m_IsActive` while the parent is off, the whole outfit doesn't show.
Whenever “a group of pieces shares one empty object as parent”, the parent must go into the same curve table.


## Finger muscle curve binding names: wrong ones still save, then silently fail at runtime

For muscle curve binding names in humanoid clips, arms use `Left Arm Down-Up` (same as `HumanTrait.MuscleName`),
but **fingers are `LeftHand.Index.1 Stretched` / `LeftHand.Index.Spread`**, not `Left Index 1 Stretched`
(all 40 per the SDK's bundled `proxy_hands_fist.anim`).

**General transformation rule** (derivable from any muscle name):

```
<Side> <Finger> <Rest>   →   <Side>Hand.<Finger>.<Rest>
e.g.: Left Index 1 Stretched → LeftHand.Index.1 Stretched
      Right Thumb Spread    → RightHand.Thumb.Spread
```

`<Finger>` ∈ `Thumb / Index / Middle / Ring / Little`, `<Side>` ∈ `Left / Right`.
**Only fingers need this transformation**; arm, body and head muscle names match `HumanTrait.MuscleName` and are used as-is.
`SetEditorCurve` happily accepts a wrong name, `GetCurveBindings` counts it, and **only at runtime does it have no effect**, with no error —
the readback verification of ① above can't catch it, since readback uses the same wrong name.

**Criterion**: in Play, the 40 finger muscles read by `GetHumanPose` stay at 0.000 while the arms from the same clip are normal.

## Changing the vendor's own parameters: use VRC Avatar Parameter Driver; don't replicate its animations

Base avatar/outfit packages often implement a feature as “**one Float parameter + one blend tree**”.
Example in this project: 輝夜's tail count is `kaguya tail Count`, a blend tree with 9 thresholds 0.1～0.9,
each holding a clip under `tail_control/1/`～`/9/` (**the directory name is the count; no guessing needed**).

To have your own radial switch it along the way, there are two routes:

* ❌ Replicate those clips yourself — they're addressed by **path hash** and can't be replicated.
* ✅ Open a separate layer with one state per step; put a `VRCAvatarParameterDriver` on each state that `Set`s that parameter on entry.

```csharp
var st = sm.AddState("尾数_九尾");
var d = st.AddStateMachineBehaviour<VRCAvatarParameterDriver>();
d.parameters.Add(new VRC_AvatarParameterDriver.Parameter {
    type = VRC_AvatarParameterDriver.ChangeType.Set, name = "kaguya tail Count", value = 0.9f });
var tr = sm.AddAnyStateTransition(st);
tr.hasExitTime = false; tr.duration = 0f;
tr.canTransitionToSelf = false;          // ⚠ without this it re-enters and writes the parameter every frame
tr.AddCondition(AnimatorConditionMode.Greater, slot / (float)n, param);
tr.AddCondition(AnimatorConditionMode.Less, (slot + 1) / (float)n, param);
```

Two pitfalls:

* `canTransitionToSelf = false` is mandatory. Otherwise while the condition holds it re-enters the state and writes the parameter every frame,
  and values the user adjusted manually keep getting pushed back.
* **Edit-time preview can't simulate Parameter Driver** (it only runs at runtime).
  So these steps **look completely identical** in offscreen renders, and that's expected — they can only be verified in Play mode.
  Write this in a comment in the comparison-shot tool, otherwise next time you see “two steps look identical” you'll spend ages investigating again.

## Toggling particle effects: toggle the renderer, not the object (measured 2026-09-03)

**`ParticleSystem.playOnAwake` fires only once at Awake, not on every OnEnable.**

So toggling a particle object with `m_IsActive`: the first activation plays, **but after turning off and on again it never plays**
— the system stays in the Stopped state, and nothing will make it Play again.
The symptom is “the radial is on that step, the object is active, but there isn't a single particle”.

Correct method: **keep the object always on, and have the animation toggle only `ParticleSystemRenderer.m_Enabled`.**

```csharp
// classID 199 = ParticleSystemRenderer
EditorCurveBinding.FloatCurve(PathOf(r.transform), typeof(ParticleSystemRenderer), "m_Enabled")
```

A particle group often has several renderers (vendors often leave a non-emitting root container + several actual emitting children);
**all of them need curves**, or the root container layer gets missed.

Explain the side effect clearly to the user: **these objects' names in the Hierarchy will always be white (always active)**;
this is intentional, not a missed toggle. Particles keep simulating while the renderer is off; the cost is that they're always resident;
set `cullingMode` to `AlwaysSimulate` to keep behavior consistent.

### Companion: not seeing particles at edit time is normal

**In edit mode particle systems don't run at all**, unless you select one in the Hierarchy
(then the Scene view's “Particle Effect” preview panel calls `Simulate` to advance it).
So “the object is active but no particles are visible” **proves nothing** at edit time.

To see the effect at edit time, write a tool that bypasses the “selected” precondition:

```csharp
foreach (var ps in group.GetComponentsInChildren<ParticleSystem>(true)) ps.Clear(true);
group.GetComponent<ParticleSystem>().Simulate(6f, true, true, false);   // advance to steady state
// then render
```

**Don't judge brightness/visibility by impression**: shoot “renderer off / on” from the same camera and take the pixel difference;
the difference set is exactly the pixels the particles actually draw, which distinguishes “faint” from “absent”.
Reference implementation: Project A's `PsPreview.cs`.

For different patterns of the same vendor effect set, **the average brightness of the textures themselves can differ by more than 3×**
(measured 8.4 / 17.3 / 28.1); multiplied by their respective tint factors, steps of the same radial can differ 5× in impression.
Prefer `startSize` as the means of evening them out (it preserves pattern and color); don't swap patterns to raise brightness —
swapping breaks the thematic consistency of “which step goes with which pattern”, and Gemini will catch it on the spot.

---


## Appearance-variant steps: **material references can be animated, texture references can't**

### Trigger
**What the menu switches is “different appearances of the same mesh”** — recolors, different patterns, different finishes.
(Switching “different objects” doesn't belong here; use `m_IsActive`.)

### Question
**“Does the vendor's appearance difference lie in material **properties**, material **references**, or **texture** references?”**

The three have completely different animatability:

| Where the difference is | Animatable? | Curve binding |
|---|---|---|
| Material **properties** (colors, floats, vectors) | ✅ | Float curves like `material._Color2nd.r` |
| Material **reference** (swap a whole `.mat`) | ✅ **PPtr curve** | `m_Materials.Array.data[N]`, `SetObjectReferenceCurve` |
| **Texture** reference (swap `_MainTex`) | ❌ **Impossible** | —— |

So when “steps differ by texture”, **the only route is to pack the texture differences into N materials and switch material references instead**.

```csharp
var b = EditorCurveBinding.PPtrCurve(meshPath, typeof(SkinnedMeshRenderer),
                                     "m_Materials.Array.data[" + slot + "]");
AnimationUtility.SetObjectReferenceCurve(clip, b, new[]{
    new ObjectReferenceKeyframe{ time = 0f,      value = mat },
    new ObjectReferenceKeyframe{ time = 1f/60f,  value = mat } });   // ⚠ single-frame clips still need a tail frame
```

### Along the way: **material slots can be expanded, drawing the same mesh twice**

A common vendor technique for effects like “make the whole body semi-transparent” isn't changing the body material, but
**expanding the body mesh's material slots from 1 to 2**: slot 0 = masked skin, slot 1 = a layer of glass/overlay shell.
Changing color = swapping slot 1's material reference.

Each layer writes its own curves without interfering, **far cleaner than “stuffing two sets of parameters into one material”**:

```
Slot 0 ← shape layer (off / half / full)       three skin materials
Slot 1 ← color layer (six colors + one "empty shell")  empty shell = same material with alpha 0, so the second pass draws nothing when "shape off"
```

⚠ **The “off” step can't write only slot 0** — if slot 1 still holds the last glass material it keeps drawing.
Either write an alpha-0 empty-shell material into it, or put both slots in the same layer.

⚠ **Mesh optimizers (AAO) merge meshes and may reorder material slots**,
so the slot order after expansion **must be rechecked on the baked avatar**; don't trust only the source scene.

### What to do if you get it wrong
First run a full diff table of “which properties actually differ among the six materials”
(see [Asset and material troubleshooting · nine](../../troubleshooting/asset-and-material-checks.md)).
Differences **only in floats/colors** → use property animation, material count unchanged;
differences **include textures** → material reference swapping is the only way.

### Evidence (2026-09-08 Project C · Aquaglass leg glass)
I first implemented the six-color radial with “property animation”, and two pairs of the six steps turned out to be **dead steps** —
`water/Blue` had identical `_Color` (the difference was in the normal ripple texture), and likewise `purple/white` (the difference was in the matcap).
Only after switching to “swap the whole `glass_*.mat` into slot 1” were the six steps truly pairwise distinguishable.

---
