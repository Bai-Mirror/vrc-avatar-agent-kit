> 🌐 English translation · [中文原文](<../../../../开发工具/SOP/60_菜单与动画层/生成器实现坑.md>)

# 60 · Generator implementation pitfalls

> ← [60 · Menu and animator layers](../60-menu-and-animation-layers.md)

The problem this page solves: implementation pitfalls you'll hit when writing or modifying the menu/animator layer generator (`菜单架构/MenuGen.cs`) —
symptoms that look like logic errors, with root causes in asset saving, render capture, parameter values, and curve binding names.

## Subpages

| Page | What it covers | When to open |
|---|---|---|
| [Saving and idempotency](generator-implementation-pitfalls/save-and-idempotency.md) | Four pitfalls you will hit · ① fill content before CreateAsset · ⑥ bake a clone · ⑦ rename with RenameAsset · ⑦-2 MenuItem names · ⑧ idempotency · ⑨ ambiguous leaf names · ⑩ align default parameters at edit time · one field may only be written by one script | Writing/modifying the generator, readback counts don't match, results regress after a rerun |
| [Toggle and curve authoring](generator-implementation-pitfalls/toggle-and-curve-authoring.md) | ② acceptance images driven by real animation data · ③ the off-step value isn't 0 · ④ single-frame clips · ⑤ parent objects must be on too · finger muscle binding names · vendor parameters via Parameter Driver · particles toggle the renderer · appearance-variant steps (materials animatable, textures not) | Clip written but not taking effect, wrong effect |
| [Layer and readback criteria](generator-implementation-pitfalls/layer-and-readback-criteria.md) | Any two radial steps differ · AddLayer weight is 0 · empty clip + WD=ON · BoneProxy escapes the outfit root | Acceptance after generation |
