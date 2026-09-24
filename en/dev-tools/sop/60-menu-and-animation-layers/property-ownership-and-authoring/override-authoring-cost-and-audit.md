> 🌐 English translation · [中文原文](<../../../../../开发工具/SOP/60_菜单与动画层/属性归属与写法/压制写法的代价与审计.md>)

# The cost of SupMine / SupBlock and the ownership audit

> Subpage split out of [60 · Menu and animator layers / Property ownership and authoring](../property-ownership-and-authoring.md). Takes over the cost-and-audit derivation from the “four authoring styles” section; the comparison table of the four styles stays on the main page.

### The cost of using SupMine / SupBlock

**It scatters “who is the owner” across two places**, and someone reading the code who looks at only one place will think nobody manages it.
So these two styles must satisfy:

- The generator must have an **ownership audit**: scan all controllers (ours + every MA MergeAnimator in the scene + each layer of the descriptor),
  and for each path record “which layers wrote 1 / which layers wrote 0”.
  **Written 0 but never written 1 by any layer** → once turned off it can't come back; confirm item by item whether that's intentional.
- ⚠ The audit must add the **Relative path prefix** — vendor MergeAnimators are mostly in Relative mode,
  the clip writes `Skirt`, which only becomes `_Outfit/…/Skirt` at build time. Without adding the prefix,
  the vendor's 1 and our 0 never match, and owned paths get **reported as orphans en masse** (measured: 11 of 19 came about this way).
- ⚠ Layers containing **WD=ON states can self-restore**, invisible to curve scanning — list them separately; don't treat them as orphans.

Details in [Layer order and override · empty clip + WD=ON](../layer-order-and-override.md) and
[Generator implementation pitfalls](../generator-implementation-pitfalls.md).
