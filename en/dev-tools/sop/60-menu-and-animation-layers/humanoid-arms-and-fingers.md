> 🌐 English translation · [中文原文](<../../../../开发工具/SOP/60_菜单与动画层/人形手臂与手指.md>)

# 60 · Humanoid arms and fingers

> ← [60 · Menu and animator layers](../60-menu-and-animation-layers.md)

The problem this page solves: you need a humanoid pose involving arms/fingers (hugging an object, holding an item), and when it's off, locomotion, gestures and breathing must all be completely normal —
which playable layer to occupy, why masks can't “take over on demand”, how to drive fingers with weights, and why the pose doesn't show on desktop and in VR respectively.

## Making humanoid arms move: three routes, each with a different cost

The requirement looks like: “hug the thing in the arms”, “hold a prop” — a humanoid pose **involving the arms**,
and **when it's off everything must be normal**. There's no free solution for this in VRChat; lay out the constraints first.

### Hard constraint: playable layer masks are fixed at build time

| # | Where | Notes |
|---|---|---|
| ① | **Playable layer mask** | Taken at build time from “the `avatarMask` of **layer 0** of the merged controller”. Changing the `mask` field on the descriptor is useless — both NDMF and VRCFury overwrite it |
| ② | Each layer's own `avatarMask` inside the controller | Only governs what that layer writes |

② is wrapped inside ①: **for body parts ① doesn't open, ② can't write out no matter what.**
And ① **can't be switched at runtime**, so “occupy the arms only when needed” can't be done with masks.

**Technique for pushing a self-made empty layer to layer 0**: add a second MA MergeAnimator + negative `layerPriority` (in NDMF, smaller comes first); measured: the vendor's original layer 0 keeps `defaultWeight` 1 after being shifted.

### ⚠ If a mask opens some body part, something must always write it

This is the easiest one to fall into. Humanoid layers don't behave as “not written = pass through to lower layers”; instead:

> **The mask claims a body part, but no curve writes it → humanoid zero pose is output (all muscles 0).**

Two consequences, both hard to self-check:

- **Arms**: the zero pose is straight arms against the body, uglier than the standing pose. So once arms are put in the mask,
  a pose must be written every frame — and **the locomotion layer's arm swing never comes through**.
- **Fingers**: the zero pose is **a slight claw**. If that layer's mask includes fingers but its clip has no finger curves,
  it covers the vendor's gesture layer below entirely — the symptom is “all gesture expressions broken, hands stuck half-clenched”.

**Corollary**: the arm layer and finger layer **must be separate**, each with its own mask.
With one layer handling both, you can't have “arms always on, fingers on demand”.

### Three routes

| Route | When off | When on | Cost |
|---|---|---|---|
| **A: Gesture occupies arms** | Arms hard-set to some pose | Pose exact | Arms all wrong under locomotion/sitting/third-party pose plugins |
| **B: Arms given back to locomotion** | **Completely normal** | Arms don't participate; the item can only dangle | Give up the arm pose |
| **C: Additive layer** | **Completely normal** (zero delta) | Exact when standing; while moving it's “arm swing + offset” | See pitfalls below |

**C is usually the best solution**, because the nature of the Additive layer fits exactly:

> Additive layer “not written” = “add 0” = **truly no effect**;
> whereas Override layer “not written” = drop to humanoid zero pose.

Before choosing C, confirm **the Additive playable layer isn't occupied** (controller empty on the descriptor = nobody's using it).

### Why going through the Action layer is usually not recommended

Action is home to many pose plugins (locomotion enhancements, pose systems, interactive toys may all merge into it).
And `VRCPlayableLayerControl` flips **the weight of the entire Action playable layer**, not one layer —
several parties share one switch, and whoever exits cuts off everyone else's pose.
Also, Action is a full-body takeover, so walking while it's on causes foot sliding.

Check how many parties are already on Action before deciding.

### Three pitfalls of route C

**① Additive clips can't write constant values.**
Humanoid additive computes “current frame − the clip's **first frame**” (script-generated clips have no additive reference pose,
so only the first frame can be the reference). A constant clip's delta is always 0, and it shows as **not moving at all**,
while curves, masks, weights and the state machine are all correct — completely invisible at edit time.

Write it as a ramp `t=0 → 0`, `t=RAMP → target`, with the clip **not looping** (otherwise it twitches back and forth),
stopping on the last frame after playing. The result is the same under both possible semantics, so there's no need to guess:

| Semantics | Delta |
|---|---|
| Current frame − first frame | v − 0 = **v** |
| Direct addition | **v** |

**② Set the layer blend mode to Additive, not Override.**
Layer 0 of the Additive playable layer is often VRChat's built-in breathing micro-motion (including arm curves).
With Override, Idle's empty clip **flattens** the breathing on the arms **to 0**.

**③ When the pose doesn't show, first rule out “playable layer weight is 0”.**
Put `VRCPlayableLayerControl(Additive → 1)` on the state — idempotent, no side effects;
**don't** flip it back to 0 when turning off (the built-in breathing layer still needs it).

### Drive the finger layer with weights

Fingers must “take over only when needed”, which masks can't do (as above), so use weights:

```
Layer N    control layer   mask = all off (writes nothing, only hosts behaviors)  weight 1
  ├─ Idle   empty clip   behaviors: TrackingControl fingers→Tracking, LayerControl(layer N+1 → 0)
  └─ On     empty clip   behaviors: TrackingControl fingers→Animation, LayerControl(layer N+1 → 1)
Layer N+1  finger layer    mask = fingers only                                   weight 0
  ├─ Idle   empty clip
  └─ On     pose clip (arm curves blocked by the mask, only fingers taken)
```

Key points:
- The control layer's mask must be **all off**. Give it a mask that includes fingers and the empty clip will again crush the fingers into the zero pose.
- For a layer at weight 0, **the state machine still evaluates and behaviors still fire** — that's the premise this approach rests on.
- Both layers can point at **the same clip**, each taking what it needs via its own mask; no need to split into two.

### ⚠ The layer index of `VRCAnimatorLayerControl` must be read back after baking

It holds the layer index **within this controller**. When merged into the playable layer, layers are **renumbered**,
and it relies on NDMF's layer-index remapping service to follow. If it points wrong, that layer can never be raised,
and **in the source project there's no way to tell right from wrong**.

→ After changing it you must bake once, read the merged controller, and confirm the layer name `LayerControl` points to matches.

### Desktop vs VR differences (decide whether extra work is needed)

- **Desktop**: arms are driven entirely by animation — all the problems above happen here.
- **VR**: arms are taken over by controller IK; **arm poses in animation are invisible by default**.
  To make it take effect, set `TrackingControl`'s **`trackingLeftHand`/`trackingRightHand`
  to Animation** on the state (setting only the fingers isn't enough). The cost is that during that time the real hands no longer drive the virtual arms.

So “arms wrong in desktop mode” and “pose doesn't appear in VR” are two independent problems, each with its own fix.

### There's a third suspect: `isDefault`

When `baseAnimationLayers[i].isDefault` is true, the descriptor's `mask` / `animatorController`
**are ignored**, and VRChat's built-in set is used. Handle it together with setting the mask.
For the arms, check `baseAnimationLayers[2].isDefault`.

> After changing it, **immediately re-verify the field's actual value in the scene**; don't assume that because the code ran it's set.
> Scene reloads, prefab overrides, or another tool rerunning can all wipe it out —
> Project A once had “the code wrote it, but the scene still has `vrc_HandsOnly`”.
> How to re-verify: search the scene YAML for `propertyPath: baseAnimationLayers.Array.data[2].mask`,
> and see which file the `objectReference` guid lands on.
> (Chinese names in scene YAML are `\uXXXX`-escaped; searching for Chinese finds nothing — unescape first.)

Priority: VRChat's playable layer order is Base → Additive → **Gesture** → Action → FX,
and Action covers Gesture. So the requirement “rank below GoGoLoco / AvatarPoseSystem”
is naturally met by the Gesture layer — those two plugins' poses go through Action.
