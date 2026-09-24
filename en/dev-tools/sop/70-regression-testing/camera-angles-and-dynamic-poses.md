> 🌐 English translation · [中文原文](../../../../开发工具/SOP/70_回归测试/视角与动态姿势.md)

# Camera angles and dynamic poses (regression framing)

> ← [70 · Regression test](../70-regression-testing.md). Trigger: before rendering images for candidates, or when framing beyond the showcase shots is needed. Before shooting, first Apply the parameters to the delivery tier (in the bare editor state hats, cat ears and accessories are all lit — a state that will never be delivered; a manual `SetActive` also proves nothing about what the animator layers will write). For how to reproduce, see [Shape of a criterion §5](../troubleshooting/observation-criteria/shape-of-a-criterion.md).

**The default 4 shots (front / three-quarter / back / face) are not enough**; at minimum add:

| Extra shot | Catches |
|---|---|
| Side 90° | Front/back layering, nose/ear/hair-strand clipping |
| Low angle | Foot shape, shoe soles, under the skirt, ankle straps |
| Top-down | Top of head, ears and tail, hats, hair whorl |
| Hands | Finger clipping, rings/gloves, wrist accessories |

- **Dynamic poses**: 4 static shots cannot reveal exposure / things flying off — add at least one frame each of "walking, sitting, leg raised" (observation of [PhysBone dynamics](../80-performance-optimization/textures-and-physbones.md) is also done in Play; PhysBone behavior is not simulated at edit time).
- **If it can't be achieved**: record poses you can't render as "not covered"; do not pass off a static front comparison as a dynamic conclusion.

## The camera must cover "the side where things go wrong"

**Passing acceptance can be merely an artifact of framing.** Case (2026-09-09, Project B): the foot-shape acceptance matrix had 106 images (13 tiers × 4 foot-shape keys × 2 views); tier 4 "bunny slippers" looked fine in both views and was passed on that basis; the user looked from the **side** and immediately found the problem — the slippers are open-heeled, and in both camera positions (`Euler(0, 35°, 0)` front three-quarter + top-down) the heel was never in frame. The two images weren't "two views"; they were two angles of the same side.

**Criterion**: before rendering acceptance images, ask first — **from which side could this thing give itself away? Is that side in frame?**

| Part | Required camera position |
|---|---|
| Open-heel / open-toe / parts with openings | Rear view or true side view (the front three-quarter can't see the opening) |
| Ring-shaped parts (rings, wrist accessories) | Along the axis |
| Snug-fitting items (sock cuffs, glove cuffs) | Close-up of the ring where the seam is |

**The cost is asymmetric**: one more camera position costs only a few seconds; miss that side and the defect rides all the way to delivery, with every intermediate "acceptance passed" reinforcing false confidence. That is exactly how the old version's all-PASS was overturned ([legacy counter-example](../_legacy/70-regression-testing-legacy-20260918.md)).
