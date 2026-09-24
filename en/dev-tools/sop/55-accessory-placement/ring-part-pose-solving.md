> 🌐 English translation · [中文原文](<../../../../开发工具/SOP/55_配饰装位/环状件位姿求解.md>)

# Ring-part pose solving

> ← [55 · Accessory placement](../55-accessory-placement.md)

The problem this page solves: for **“a ring around a limb segment”** pieces like rings, wrist cuffs and headwear,
how to compute the hole axis, hole center, inner radius and roll, instead of typing Euler angles by hand.
The first half is the four-step algorithm; the second half is the corrections forced out by review; where they differ, the second half wins.

## Ring accessories: rings, wrist cuffs and headwear are **the same problem**

Measured: all three are “a ring around a limb segment”, differing only in axis and scale:

| Piece | Vertex group of which bone holds the ring | Ring axis | Local inner radius | Around which segment |
|---|---|---|---|---|
| Ring `Swaying_heart_ring` | `Bone` (root bone) | Z | 6.6 mm | At 30% of the proximal phalanx |
| Wrist cuff `wristcuff` | `frill1.001` (**not** the root bone; the root bone is the bow) | Y | 20.0 mm | At 97% of forearm→hand |
| Headwear `headdress` | `Bone` (root bone) | Y | 73.7 mm | At 195% of neck→head, axis taken as **the base avatar's own up axis** |

One algorithm handles them all. Necklaces, anklets and earrings work the same way.

### Step 0: first probe what shape it actually is; don't assume from the name

The mesh of `Acc_心形戒指` is actually called `Swaying_heart_ring` — **ring + a chain + a swinging heart pendant**,
four bones. The **root bone of `Acc_腕饰` is the bow, not the ring**. Going by name or by “take the root bone's group” will both place it wrong.

**Run the probe first** (`RingProbe.cs`, one-off diagnostic, delete before delivery): print the hierarchy, print `rootBone`,
**group vertices by bone weight**, then per group compute the bounding box and the minimum radius along each of the three axes. Swinging pieces are invariably
“main body rigidly bound to one bone, dangling part on a child bone chain”; grouping makes it clean.

### Step 1: hole axis and hole center — per group, per axis, find the “largest empty circle”

“Largest empty circle” = the point in the plane farthest from all vertices. That's exactly the hole center of a ring.

**It must be done per group, not on the whole vertex cloud**: the ring's pendant hangs right along the hole axis,
and the whole-cloud minimum radii on the three axes are `(5.79, 2.81, 6.20) mm` — no axis passes through the hollow, and the criterion is useless.

**Four pitfalls you will hit**:

1. ❌ **Don't use the bounding box's shortest edge as the hole axis**. With decorations on the ring the box is nearly a cube (ring measured 15.8/17.0/13.3 mm);
   pure luck.
2. ❌ **Don't use the centroid or box center as the hole center**. Vertex density on the band is uneven (more vertices on the patterned side); the centroid measured **6 mm** off the hole center;
   and iterating “average the inner-ring vertices” converges toward dense regions — the inner radius **collapses** from 5.92 mm all the way to 0.6 mm.
   Hill-climbing to maximize the minimum radius improves monotonically and doesn't collapse.
3. ⚠ **Hill-climbing must be clamped inside the bounding box**. On an unbounded plane “farthest from the point cloud” diverges; minR measured climbing to **24 m**.
4. ⚠ **After clamping, comparing magnitudes isn't enough**. Clamped in a box, the other two axes can always find corner gaps
   (measured `(3.51, 2.49, 6.65) mm`; the true hole axis leads by only 1.9×, and a 2.5× threshold would reject it).
   The real criterion is **the hole center is enclosed on all sides**: split nearby vertices into 12 sectors by angle and require material in every sector.
   Ring hole centers all pass; corner gaps always have a few directions with no material.

The inner radius is **not** determined in this step — see ② of “Four points forced out by three-way review” below; that version of the rule was falsified three times.

### Step 2: size — **measure** limb thickness from the base avatar mesh

❌ **Don't use bone spacing as a proxy**. “Adjacent finger proximal-phalanx spacing × 0.85” measured out to a ring twice as thick as the finger.

✅ Take the vertices bound to this bone segment that fall within a thin slice near the target position, measure their distance to the bone axis, and take the **97th percentile**.
**The slice must be limited**: the forearm bone runs from elbow to wrist, and the elbow end is noticeably thicker; taking the whole segment overestimates wrist girth.
(Initially the 85th percentile was used, and two review models pointed out “the lower half of the ring sinks into the finger” — finger cross-sections are flat,
and the 85th percentile underestimates the widest direction.)

Compute in the bind pose (vertices transformed into bone-local space via the bindpose), so whether the limb is bent doesn't affect the measurement.

Measured results: fingers 8.5–10.6 mm, wrist 33.3 mm, head (at headband height) 150.7 mm.
Inner radius set to `肢体粗细 × 1.05` (snug pieces) or `× 1.10` (loose pieces with frills).

### Step 3: roll — whichever side of the ring the decoration is on faces outward

Whichever side of the ring the pendant / bow / ribbon is on should face outward; otherwise the decoration grows into the limb.
For how to take the direction see ③ of “Four points forced out by three-way review” below — it is **not** “non-ring vertex centroid − hole center”; that version was wrong.

**“Outward” for a finger = the back-of-hand direction**, and this step has a big pitfall:

❌ **Don't use “sum of the four fingers' curl” as the palm direction**. At rest the little finger, besides curling toward the palm, has a large **lateral adduction** component
(measured right little finger curl 0.1246, middle finger 0.0000 — the combined direction is dragged off by one finger),
so **the right-hand bow faced the palm and the left-hand one the back of the hand: one right, one wrong**.

✅ The normal is set by the cross product “knuckle row (index knuckle→little knuckle) × pointing direction”, **with the sign set by handedness**:
right hand, back of the hand facing you, fingers pointing up, the thumb is on the left and `across` points right; in Unity's left-handed system `Cross(right,up)=forward=away from you=palm side`,
so **negate for the right hand, positive for the left**. Curl amounts are kept only as a consistency warning.

- ⚠ **Don't write the handedness sign from memory**: verify after `Cross` — the projection of the gem's (a part with a front face) centroid onto the **back-of-hand normal** must be **> 0**; compute both signs and take the one with a positive projection, **verify once for each hand** (corrected 2026-09-07; a wrong sign makes both hands wrong together).
- The “encircles” criteria (eccentricity, angle) **only concern the hole axis**; worn correctly or reversed, the readings are identical, so they can't catch reversal; ring-piece criteria need at least two: ① hole axis aligned (encircles) ② **front facing** (not reversed); ① alone is not enough.

---

## Four points forced out by three-way review (2026-09-01, three rounds of agy cross-review)

I misjudged three rounds in a row looking at images myself; every point here was found only after a review model pointed it out. **This section is the most expensive part of this page.**

### ① Feed review **normal viewpoints**, not face-hugging close-ups

In the first round I fed accessory close-ups and the three models contradicted each other (one said the headband was in front of the face, another behind the head) —
the close-up viewpoint itself misled the judgment. After switching to **full-body front / three-quarter / back / head close-up**,
the three models' findings converged immediately and matched what I saw.

**Use numbers for criteria-type information and normal viewpoints for positional impressions.** Close-ups are only for fine texture and clipping.

### ② The wearing hole is neither “the largest ring” nor “the smallest ring”

- Taking the **largest**: the wrist cuff was positioned by the outermost frill, and the whole piece slid along the axis out past the palm (bounds center x=0.467, hand bone at 0.395).
- Taking the **smallest**: it locked onto the hole in the bow's knot (14.3 mm, while the ring around the wrist is 17.2 mm), and the whole piece was scaled up 1.3×.
- Taking “minimum radius over all vertices + a floor”: the floor was triggered by the bow, scaled up 2.5×.

**Correct answer**: determine the axis from the group with the strongest signal, then **re-measure each group** on that axis and take the smallest among groups that still pass the sector-enclosure criterion
**and have radius ≥ 60% of the largest ring**. The 60% bar keeps small holes on decorative parts out.

### ③ The roll reference is “vertices protruding radially outside the ring”, not “the centroid of non-ring bone groups”

The bow **sits in the ring's group**; the non-ring bone groups only have the chain and pendant — using them as the decoration direction, the reference isn't the bow at all.
All three models agreed: “the ring's bow is lying flat instead of standing up”.

**Correct answer**: take the vertices with radius > 1.5× inner radius and compute the radial direction weighted by `(r − 阈值)`.
The ring wall itself is within 1.0–1.3× and the pendant hangs along the axis at only 1.1× radially, so both are excluded;
the frill goes all the way around and cancels out radially — what remains is exactly the bow.

### ④ One quantity geometry can't derive: **which end of the axis the decoration flares toward**

Whether the frill opens toward the hand or toward the elbow is **asset semantics**; geometry can't measure it (I tried a covariance criterion on “direction in which radius grows along the axis”;
it doesn't hold for this asset). Keep a ±1 `flare` in the table, render one comparison image for each direction and let a human choose.
**This is not a magic number** — it has only two values and there is always an image as evidence.

### Two more fixed along the way

- **The sign of the back-of-hand direction is set by handedness**; you can't use “sum of the four fingers' curl”: the little finger's lateral adduction at rest drags
  the combined direction off, so the right-hand bow faced the palm and the left-hand one the back: one right, one wrong.
  Correct answer: `Cross(食指关节→小指关节, 指向)`, negate for the right hand, positive for the left.
- **Take limb thickness at the 97th percentile**, not 85: finger cross-sections are flat, the 85th percentile underestimates the widest direction, and the ring cuts into the flesh from both sides.
- **Hand-entered offsets must be written in the base avatar's own coordinate system** and then converted to the mount's local space. Bone local axes are set by the base avatar's author;
  writing (x=right, y=up) directly into bone-local space tilts the halo in the reversed direction.
