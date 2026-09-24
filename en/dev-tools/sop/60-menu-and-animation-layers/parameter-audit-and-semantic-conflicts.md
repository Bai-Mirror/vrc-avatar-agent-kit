> 🌐 English translation · [中文原文](<../../../../开发工具/SOP/60_菜单与动画层/参数审计与语义冲突.md>)

# Parameter audit and semantic conflicts: two pieces of evidence that “criteria can't see”

> Subpage split out of [60 · Menu and animator layers](../60-menu-and-animation-layers.md). Takes over the measured runtime-mode audit from “Hard constraints” and the semantic-conflict warning from step 3; the hard-constraint table and step criteria stay on the main page.

**The parameter audit must run in runtime mode** — at edit time you can't see the part generated at build time by MA / VRCFury / MenuInstaller.
> Measured (Milfy): 24 parameters, 108 bits at edit time; **92 parameters, 177 bits after build**.

**Parameter budget**: VRCFury compresses parameters on demand, so the real payoff from removing dead parameters is **faster sync**, not an equal amount of freed space (mechanism and measured floor in [VRCFury parameter compression](vrcfury-parameter-compression.md): only “menu-bound synced parameters” can be compressed; the uncompressible part is the real budget); **Triturbo face-tracking parameters are bit-decomposed**, cheaper than 8-bit floats.
> ⚠ **Don't write the criterion as “is there clipping”.** The most common defect on top of the head is a **semantic conflict** —
> two pairs of ears on one head at once, no geometric collision, “no clipping seen” in renders, and it just looks wrong.
> 2026-09-08 Project B_Milfy: 66 combination renders all judged “no clipping seen”,
> while the default state actually had two pairs, “gyaru cat ears + base avatar bear ears”, and two hair-bundled animal ears weren't in any toggle at all.

## Reclaiming parameters after splitting layers / deleting objects: scan every entry point for “which parameters does this layer use”

**Trigger moment**: after deleting a set of objects and removing the animator layers that only served it, judge which synced parameters become dead along with them.
**Checkable question**: besides transition conditions, is this parameter read or written as Motion Time / Speed / Mirror / Cycle Offset, by a BlendTree (including nested), or by a Parameter Driver?

- Entry points in the state machine: transition conditions; `AnimatorState.timeParameter` / `speedParameter` / `mirrorParameter` / `cycleOffsetParameter` (each with its own `*ParameterActive` switch); recursive BlendTree `blendParameter(Y)`; `VRCAvatarParameterDriver`. In the scene there are also the `parameter` fields of PhysBones and Contact Receivers.
- **The cheapest fallback is full-text grep**: before removing, `git show HEAD:<controller> | grep <参数名>` (`m_TimeParameter: X` is visible at a glance); after removing, grep all `.controller/.asset/.unity/.prefab/.anim` in `Assets`; it counts as dead only if all that remains is the parameter declaration, unreachable menus, and unattached vendor parameter tables.
- **The last gate is the post-build sync list** (listed item by item in the `ParamCost90` report); dead parameters show up there at full price.
- Trade-off: parameters no longer reachable from the menu can't be compressed by VRCFury (see above) and are billed at full price, so reclaiming them is a full gain; dead parameters still attached to the menu only save sync time.

> Measured (2026-09-22 Project B deleting the base avatar hairstyle): scanning “transition conditions + BlendTree” only found two Bools, `FHSharp` / `HairNoSide` (2 bits, matching 254→252 after build).
> The post-build list still had three Floats `FHLength` / `TWLength` / `TWVolume` — they were the **Motion Time** parameters of the three removed layers; 24 bits were missed.
