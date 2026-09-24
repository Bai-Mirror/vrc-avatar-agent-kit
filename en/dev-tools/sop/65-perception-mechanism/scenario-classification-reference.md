> 🌐 English translation · [中文原文](<../../../../开发工具/SOP/65_感知机制/情景分类对照.md>)

# Scenario classification reference: the schema's 9 dependency kinds ↔ the review's 12 + 4 classes

> Drafted by DSH (D-05), **reviewed and approved by Claude 09-22** (spot-checked that the citations `01_需求说明.md:44-53`, `scnV.md:165-170`, `critic.md:7-11` are consistent; corrected the outdated statement in the “total number of instances” item). Saved separately before D-04 (the `65_感知机制/` index and subpages) lands; sources: `_长程任务_20260918/进度核查_20260919/scnV.md:133-176`, `critic.md:7-11`, `感知机制研究/01_需求说明.md:44-53`.

## 1. External wording: **9 kinds**

Externally, always say “there are **9 kinds** of scenarios”, i.e. the schema's dependency kinds D1–D8 (`01_需求说明.md:44-53`; D6 covers both the nipple key and toenail visibility):

| Dependency | Scenario in one sentence |
|---|---|
| D1 | Body ← clothing: when a covering piece is visible, write body shrink/delete; restore when taken off |
| D2 | Foot ← shoe: choose the foot pose key by heel (flat/mid/high heel are values) |
| D3 | Sock ↔ foot shape; sock ← shoe: when the sock is visible the foot shape satisfies the sock; shoes off + socks on doesn't return to neutral |
| D4a | Clothing ← clothing: when the outer layer is visible the inner layer shrinks; outer off returns to baseline; **turning it on again must re-shrink** |
| D4b | Underwear ↔ bottoms: who shrinks, who overrides whose visibility, the same-body-part priority chain |
| D5 | Clothing ← body shape: tight-fitting pieces follow bust/hip/leg sliders; variants chosen by body shape |
| D6 | Occlusion visibility: hide as soon as any covering piece is visible (nipple key, toenails) |
| D7 | Hair ← jacket, hat: take the target value; return to baseline when off |
| D8 | Pose-related: no poke-through when walking, sitting, crouching (this phase only covers skinning-driven body parts; skirt hems go to visual residue) |

## 2. Reclassification for review: **12 blend shape classes + 4 visibility-only classes**

**This is not an external enumeration**; it's a review table that splits D1–D8 down to the granularity of “whose key changes, triggered by what” (`scnV.md:139-165`). “Original draft” refers to the numbering of the 17 scenarios before review.

**Blend shape classes (12)**

| Review class | Scenario (trigger → whose key changes) | Split from which D | Original draft | Project A effective declarations |
|---|---|---|---|---|
| A1 | Covering piece visible → body shrink or delete, restore when taken off (body part, Set/Delete as attributes) | D1 | #3, #4, #16 knees/elbows | 4 (incl. 2 Delete) |
| A2 | Shoe → foot pose key (flat/mid/high heel are values) | D2 | #1 | 2 (locked “must not write”) |
| A3 | Keep the foot shape if either shoe or sock is present | D2, D3 | #2 | 1 (plus 1 superseded) |
| B1 | Outer piece visible → keys on the inner piece or the yielding piece itself (shirt shrinks, jacket yields to the bag) | D4a | #5, #6 | 3 |
| B2 | Multiple pieces at the same body part require opposite values of the same body key, no priority | Value part of D4b | Value part of #7 | 0 |
| B3 | Jacket or hat visible → hair yield key | D7 | #15 | 1 |
| C1 | Piece follows body shape axes: bust, hip, thigh sliders | D5 sync | Bust/hip/leg part of #8 | 3 (18 targets total) |
| C2 | Piece follows body keys changed by other clothing (waist cinched by a dress, foot changed by shoes) | “Changed keys” of D1/D3 | Waist part of #8, #9 | 0 |
| C3 | Body shape baseline lock, vendor sliders must not grab keys, clothing limits body shape | Clamp/baseline of D5 | #11, #10 Clamp | 3 |
| D | Breast covered → nipple key to zero | Value of D6 | #13 | 1 (12 violations pending review) |
| E | Pose- or contact-driven | D8 | Contact part of #16 | 0 |
| F | Accessory → face keys; expression layers must not override | **Missed in original draft** (no corresponding D) | — | 0 |

**Visibility-only classes (4, not counted as blend shapes)**

| Review class | Scenario | Split from which D | Original draft | Project A effective declarations |
|---|---|---|---|---|
| V1 | Alternate pieces mutually exclusive, piece chosen by body shape | Variant part of D5 | #10 | 1 |
| V2 | Hide toenails when covered by shoes/socks | D6 | #12 | 1 |
| V3 | Hide ears and headwear when covered by a hat or hood | D6 | #14 | 3 |
| V4 | Base avatar pieces yield on whole-outfit switch, part toggles don't cross steps, one toggle only manages its own pieces | Visibility part of D4b | #17, visibility part of #7 | 1 |

Total: 12 blend shape classes + 4 visibility-only classes = **16 classes**; Project A has 71 effective = 18 blend shape + 6 visibility + 1 R + 46 geometric items, plus 1 superseded, `decl.json` 72 in total (`scnV.md:167-169`).

## 3. Usage trade-offs

- **External / requirements / acceptance tables** use the 9 kinds (D1–D8); **internal review and gap-finding** use 12 + 4, because the single dependency D6 covers both the nipple key (class D) and toenail visibility (class V2), and D1 covers both shrinking (A1) and the delete-vertices attribute, so the granularity doesn't line up.
- **Class F (accessory → face keys) has no counterpart among the 9**; it was added during review (neither Project G nor Project F reproduced it, and client feedback details are missing; `scnV.md:154`). To enter the schema, a dependency kind must be added first; don't force it into D6.
- **C2/C3 have no clean single-D ownership**: C2's waist is driven by clothing shrink (like the foot-shape class), C3 is baseline lock and vendor sliders grabbing keys; classify by “trigger source”, not by “body part” (`scnV.md:124-125`).
- **There is no usable figure for the total number of instances**: when `critic.md:11` was written the 14 past projects hadn't been scanned; on 09-19 E-T11-01 scanned them with the T-11 static rules (`_长程任务_20260918/审查产出/_历史工程/静态规则候选_20260919.md`, 0–71 candidates per project), but those are **candidates, not right/wrong judgments**, with no geometric/build-time/human review. So “how many kinds of scenarios were found” is still answered only as 9 kinds / 12 + 4 classes; the total instance count waits until after review.
- Trigger question: *Which dependency expresses this scenario in the schema? When it doesn't fit, do we change the classification or add a dependency?* Trade-off: better to add a review-class column than to force F, C2, C3 in just to make 9 kinds.
