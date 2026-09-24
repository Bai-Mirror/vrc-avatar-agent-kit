> 🌐 English translation · [中文原文](../../../../开发工具/SOP/50_服装发型装配/收缩键可见后果_渲图对照.md)

# Shrink keys “does a missing one have visible consequences”: freeze the Animator and render a 0/100 comparison

> Parent: `脚型与收缩键归属.md`. This page handles only one thing: the data shows some shrink key is never written (e.g. vendor layer weight 0, writer missing), and you need to judge whether its absence is visible.
> Rerun script (C-12): `开发工具/通用工具/审查/unity/Editor/T3ArmFreeze.cs`, menu `Tools/AvatarAudit/T3 Arm Freeze (Edit Mode)`; request `Library/AvatarAudit/t3_arm_freeze_request.json`, example `审查/unity/examples/t3_arm_freeze_request.json` (the original values of Project F's `t3_arm_A3`).

## Trigger
T1 readings show a body shrink key (like `Shoulder_OFF`, `Upper_arm_OFF`) at 0 while “the garment is worn”, whereas the vendor clip intends 100.

## Method (measured in Project F, 2026-09-18)
1. T1 `reset:none` poses the avatar into the target state (garment worn; **turn off any outer layer in front first**, e.g. if a knit vest covers the shoulders, turn off the vest first).
2. `execute_code` turns off `Animator.enabled` on the avatar root (freeze; otherwise the animation writes it back the next frame), manually `SetBlendShapeWeight` to 0, render a set with T3; set 100 and render another set, with identical camera parameters.
3. **Positive control**: the same two values with `only_renderers:["<身体>"]` rendering only the body; the difference pixels must be significant (Project F ≈35,000 / 512²). If the positive control fails, the key didn't take effect or the camera isn't aimed right, and the later “0 pixels” can't be used.
4. Compare the two clothed sets pixel by pixel (threshold 24/255).
5. When done, **restore** the key values and re-enable the Animator.

## Criteria and trade-offs
- Clothed sets differ by 0 (or only a few dozen scattered points) = not visible in this pose → no rush to fix; record “no visible consequence at idle, pending the motion batch for in-motion”.
- Differences in patches → the missing key has visible consequences; add a writer (MA ShapeChanger on the garment, or add a clip).
- **Check the framing before looking at images**: `hide_renderers` should at least turn off hair, tail and shoulder bag; in Project F's first round the back view was entirely blocked by hair, so a difference of 0 meant nothing. Stitch a small 2×2 image and glance at it before comparing.
- The conclusion still has to be sent to agy to try to overturn it (the prompt states “my conclusion”); if agy points to problems unrelated to the key under test (such as seam outlines), use “are the 0/100 sets identical pixel by pixel” to tell them apart.

## ⚠ Don't do “mesh swap” comparisons in Play (measured in Project D, 2026-09-19)
After an NDMF/AAO build, the renderer's bone array may be reordered, and the body merged into `$$AAO_AUTO_MERGE_SKINNED_MESH_n`. Swapping `sharedMesh` at runtime for the original mesh from assets breaks skinning (the measured “distances” are all garbage on the order of 100 mm, and renders may even be pixel-for-pixel unchanged). **To compare “before and after a mesh swap”, do it in edit mode with the scene's real bones**: `BakeMesh`, then measure the item-to-body nearest distance (quantiles); only comparisons that change nothing but blend shape values can be done in Play. When finding the body by name in Play, also note it may already have been merged and renamed.
- **Single source for geometry measurements** (2026-09-19 acceptance AY): both body and item use `BakeMesh` (with current blend shape weights, restored after reading), and the output states `geometry_source`; don't use sharedMesh raw vertices on one side and skinned vertices on the other — mixing the two spaces makes distances meaningless. For multi-frame blend shapes take the full-weight frame.
- **BakeMesh's two parameters and “both ends”** (2026-09-19 acceptance BF): if you'll multiply by `localToWorldMatrix` afterwards you must use `BakeMesh(m, true)` (useScale), otherwise renderers with scale ≠ 1 get scaled twice; “both ends at key 0 / 100” means really setting the body key to 0 and baking once, setting 100 and baking once, then restoring the original value — don't pass off “current weight” and “current + 100” as the two ends.
- **MA Delete deletion regions can only be measured in edit mode** (2026-09-19 acceptance BQ): after entering Play / building, MA has already processed the body mesh — persistent Delete physically removes vertices, toggleable ones are hidden via NaN bones (MA `ReactiveObjectPass`), so BakeMesh in Play can't measure “the region that should be deleted”. Take the deletion region by the writer's own `m_threshold`, don't make up a threshold; if the writer is on a container with no mesh, report it; silently skipping is not allowed.

## Which item the shrink SC hangs on (2026-09-20 Project D Velvet China)
The vendor attached the ShapeChanger for 8 shrink keys to the **full-set root**: after part switches (socks/outerwear etc.) are turned off the keys are still 100, and the exposed parts (calf, ankle) collapse into thin lines. Trigger: when auditing a shrink SC, first ask “is its host the full-set root or the item covering that patch of skin?”; if it's the full-set root, split it onto each item by coverage (socks = knee/calf/ankle/foot/toes, arm sleeves = elbow/forearm, body garment = shoulders), and render “turn off one item alone” for each. Open shoes (ankle strap / low-cut): don't let the shoe shrink the ankle and instep — the exposed segment collapses; shrink only the toes; the instep showing from the shoe opening is by design (judge against the “socks on” reference image).
