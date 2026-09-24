> 🌐 English translation · [中文原文](../../../../开发工具/SOP/03_装配与冲突通则/装饰与变体的判据.md)

# Criteria for decoration vs. variant: bounding boxes can't answer it, measure per vertex

> A subpage split out of [`03-assembly-and-conflict-rules.md`](../03-assembly-and-conflict-rules.md). It takes over the derivation and evidence from the "decoration or variant" section; the trigger, the question and the wiring trade-offs remain on the main page.

### What to do if you get it wrong

**A bounding box cannot answer this question.** I used "volume ratio 0.76 + center distance 1 cm" and judged it a variant —
a decoration **distributed along the main body** (flowers wrapped around an ear) has a bounding box that almost coincides with the body,
and is **indistinguishable** by bounding box from "another version at the same position".

**Use per-vertex nearest distance as the criterion**: for each vertex of B, find the nearest vertex on A, and take the **median** of the distances.

| Median distance | Verdict |
|---|---|
| **< 2 mm** | Variant — the two pieces are nearly coplanar; two versions of the same geometry |
| **> 5 mm** | Decoration — B hangs outside/on top of A |

**Auxiliary criteria (cheaper, run first)**:
- **Same source FBX + exactly the same bone list + only the materials differ** → almost certainly a **color variant**
- Vertex count and triangle count **exactly identical** → variant
- Paired suffixes in the name such as `_White` / `_PINK` / `_A` / `_B` → a strong signal of a variant (but **only a signal; still measure**)

### Evidence (Project C · Acc_GothicRoseFox, one positive and one negative sample)

**Judged as decoration (correct)**: `Rose_Ears → Ears` per-vertex nearest distance **median 11.7 mm**,
`Roses_Tail → Tail` **median 34.8 mm**. The author confirmed: "this part is not a variant, it's a decoration", "Rose is a decoration on Ear".
→ Changed to toggle on together.

**Judged as variant (correct)**: the same directory also has two sets of ears and tails, "white / pink" —
**the same mesh file, exactly the same bones, bounding boxes differing by only 1 cm, only the materials differ (white vs pink)**.
Previously one preset turned **all four** on, and the white and pink ears clipped through each other. → Must be mutually exclusive.

**The two samples form a perfect control**: both are "two pieces at nearly the same position"; the bounding-box criterion gives **the same answer** for both,
while the per-vertex distance criterion gives **opposite and correct** answers. Choose the criterion that **can distinguish known positive and negative examples**.
