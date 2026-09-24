> 🌐 English translation · [中文原文](<../../../../开发工具/SOP/55_配饰装位/通用坑.md>)

# Common pitfalls

> ← [55 · Accessory placement](../55-accessory-placement.md)

The problem this page solves: pitfalls outside the placement algorithm that **every kind of accessory runs into** — what to look at before attaching,
how to scale generic packages, which surface to measure for embedding depth and for placement, what contaminates criteria, how to handle mirroring and bounding boxes,
how to frame acceptance images, how to judge occlusion. Every item comes with measured numbers and failure symptoms.

## Before attaching, look at how the author designed it

Asset packages usually include **showcase / promo images** (directories like `preview` `sample` `image` `宣伝` `商品画像`,
or jpg/png at the archive root). **This is the cheapest source of correct answers**: the author has already rendered “how this thing
should be worn” for you.

Look at the images first, then decide how to attach. Geometric criteria (does it encircle, how eccentric) can only prove “it's attached”,
not “it's attached correctly” — none of the following can be measured by geometric criteria:

- Is the halo **floating directly above**, or **offset to one side with the ring center pointing at the head** (only the latter feels like a satellite; the former looks like “balancing a plate”)
- Are the animal ears **perched on the hair**, or **reasonably embedded into the head, joined with it**
- Is the headband **clamped on top of the head** or **worn slanted/backward**
- Does a pendant hang at the side of the body or sit against the waist

When there are no showcase images, look at how the vendor prefab is laid out in **its own sample scene**; that's equivalent to a showcase image.

## Generic accessory packages on a different base avatar: first scale proportionally to the base avatar, then talk about position

**The number-one cause of the 2026-09-01 rework.** Generic packages (one prefab for every base avatar) are built on **the author's own reference base avatar**.
The vendor's animal ears natively span 35.7cm, while 輝夜's head is only 15.4cm wide — 2.32×.
At that ratio, no height adjustment makes them look “grown on the head”; they just look like two blackboards propped on top.

Method:

1. Measure a ratio from the **vendor's character render** (ear span ÷ face width ≈ 1.9). That's the relative size the author approved.
2. Convert to a scale factor with the **measured head width of the base avatar**: `k = 目标比例 × 头宽 ÷ 当前展宽`.
3. Use the **head center** as the fixed point of scaling, not the accessory's own origin — this way the accessory shrinks while drawing in toward the head,
   and the position comes out right at the same time; using its own origin, you'd have to move it again after scaling.
4. **Recompute** the scale factor every time (`k = 目标 ÷ 当前`); a second run naturally gives 1.000, idempotent by construction.

The same reasoning applies to any piece “made by the author for a different base avatar”. Conversely, **don't scale pieces the vendor made specifically for this base avatar**;
their absolute coordinates are the answer (see “Base-avatar-specific accessory packages” in [Rigged accessories](rigged-accessories.md)).

## The reference surface for “embedding” is **the surface that gets rendered**

When an accessory should be “reasonably embedded into the head, joined with it”, the reference surface is **not the top of the skull bounding box**.
Measured on this project: skull top y=1.1507, while the **hair surface** at the ear root is y=1.1834 — a 3.3cm difference.
Embedding 3cm relative to the skull top, it still floats above the hair. The review model pointed out “the ear bases are fully floating on the hair surface”,
while my log said “embedding depth 3.0cm” — **both were right, because they measured two different surfaces**.

Two sub-rules:

* **Measure locally**; don't take the highest point of the whole head. The 98th percentile of the whole head bites into **ahoge tips** (measured 5.7cm higher than the real hair surface);
  embedding relative to that surface actually pushes the accessory above the hair, and it gets worse the more you fix.
  Correct method: take a small patch of radius 3cm near the accessory's contact point, 90th percentile.
* For left/right symmetric pieces, measure each side separately and average.

## Placement reference surfaces for wearable pieces: set by type, all **top-aligned**

Each kind of piece lands on a **physically meaningful surface**, not a set of offsets (copied coordinates break on another base avatar; surfaces follow the base avatar):

- **Floating pieces** (HUD panels etc.) → against the **front surface of the head bounding box** (measured deviation 3mm), height with the panel's lower edge ≈ eye height.
- **Ring pieces** (necklaces, rings, wrist cuffs) → **encircle the bone**, ring center on the bone axis; first check what covers that ring —
  when a necklace is covered by a collar, it has to move 3.0cm down and 3.2cm forward from the Neck bone to show.
- **Held items** (plushie in the arms / on the back) → bounding box center on **the front surface of the torso at that height**
  (measured one piece 0.8cm outside, one 2.4cm inside); large pieces also shift sideways by about 0.9 head widths.

All are **top-aligned, not center-aligned**: held items align their top with the chin, wrapping items with the top of the head. Only four samples; experience, not theorem.

- **Multiple slots of the same radial must have exactly the same pose** (both position and orientation); only pattern/color should change; the vendor ships an author pose with each prefab, so placing them one by one misaligns every slot.
- Placement tools need **“manual-adjustment detection” and “readback”** entry points: manual-adjustment detection **aborts** when the scene state differs from “the position computed from the table”, so human tweaks aren't overwritten; readback **exports manual adjustments into the table's units**.

## Criteria get contaminated by **your own output**

When measuring the cross-section radius of “head + hair” to judge whether a ring fits, the scan must exclude **accessories attached in this very round**.
Measured: while placing the silver headwear, the gold headwear was already attached under the `Head` bone (not in `_Acc`, so it slipped through directory-based exclusion),
and the cross-section radius was falsely reported as 12.6cm instead of 9.3cm.

The exclusion list must cover three kinds: asset containers (`_Acc` / `_Outfit` / `_Plugin`), **mount points generated this round**
(`Mount_*`), and **anything not rendering** (`!enabled || !activeInHierarchy`).

## Same-name meshes shipped with the base avatar: a whole-tree name search will collide

輝夜 ships a pair of animal ear meshes also named `ear` (10382 faces, already turned off by the menu).
`FirstOrDefault(t => t.name == "ear")` hits that one, not the pair in the accessory package. Two consequences,
**neither raises an error**:

* The framing is set from something that doesn't render, and the isolated shot comes out black;
* The halo's “avoid the animal ears” avoids something invisible and gets pushed 28cm from the head center,
  reading as a floating object unrelated to the character — while every criterion in the log is green.

Rule: name lookups **must always be scoped** (search under `_Acc`), and **filter out anything not rendering first**.

- Judge **what** something is by its **measured world bounding box** (where the center is, how big), not the object name — some outfit's `Ring` measured 13×7.5×14cm, above the head and to the left; it's actually a built-in halo, not a ring.

> → [Mirrored parts: the sign of the scale must be carried over from the prototype](common-pitfalls/mirrored-part-scale-sign.md) — take the sign back from the prototype, run rotation composition through the sign too, and the left/right self-check criterion (measured 57.27°/46.05° → 313.90°/46.05°).

## Don't recompute what the author already decided

The vendor prefab root's `localRotation` is identity and the piece's ring axis is exactly the base avatar's +Y — this means
**the author set the orientation in the base avatar's standing-pose space**; the orientation is already right.

Running the “rotate the decoration outward” geometric fit again on top of that **yaws** the whole headwear **12.8°**,
and twists the big bow that belongs on the side to the front. That's the “headwear mounting position problem” the user pointed out.

**Geometric fitting only fills in information the author didn't give; don't recompute what the author gave.** Specifically for head-top pieces:
keep the base avatar's orientation (at most add an explicit pitch angle) and compute only the position — pin the piece's own ring center to
“measured head center + offset”.

## Vendor shape keys: the weight is **bracketed** with renders, not computed

When the author writes “シェイプキーで角度やサイズを調整可能” in the product description,
**prefer shape keys for fitting, not scaling** — scaling enlarges ribbons and beads along with everything else, and the proportions fall apart.

But the weight value can't be computed: geometric probes like `FindRing` read **bind pose vertices** and can't see shape keys.
You can only bracket: `width_large = 0` → the beads at the back of the head cut into the hair; `= 100` → the whole thing floats off the hair; take **50**.
Two review rounds each pointed out one direction, and the middle value came out.

> → [Skinned pieces whose armature was moved: `localBounds` must be recomputed at the end](common-pitfalls/skinned-mesh-local-bounds.md) — bounds drifting from real geometry gets the whole mesh culled from every camera position; the method and the “all-green log but empty image” self-check.

## Pieces on the head: acceptance images must have **head and accessory in the same frame**

`AccShots.cs` frames by **the accessory's own bounding box**, so the shot shows only the accessory, not the head.
But “should the halo be offset to one side”, “are the ear bases embedded in the head”, “where on top of the head the headwear sits”
are all questions about **the relationship between the accessory and the head** — without the head as reference, the image contains no answer.

`HeadShots.cs` (added this round, generic): framing = head bounding box ∪ accessory bounding box, 12% margin all around,
six views: front / left and right three-quarter / side / back / top. It also has an **isolated single-piece** mode
(keep only this one renderer, hide everything else) — questions like “does the ear opening face forward or backward”
can never be seen clearly in an image with headwear on and hair pressed down, but shot alone they're obvious at a glance.

⚠ Merged bounding boxes **must not use `Renderer.bounds`**. A skinned renderer's bounds are derived from the local bounding box baked into the asset,
and for pieces where “mesh and armature live in two different hierarchies” (the ear/tail package) it can come out big enough to frame the whole body —
measured: in the first version the head took up only 3% of the frame. Switched to statistics over **actual skinned vertices**.


---

---

**See also**: rebinding the armature and editing the wrong branch, occlusion ≠ occupancy → [Rebinding the armature and occupancy](rebinding-armature-and-occupancy.md)
