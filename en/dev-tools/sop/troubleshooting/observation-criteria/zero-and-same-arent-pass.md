> 🌐 English translation · [中文原文](../../../../../开发工具/SOP/问题定位/观测口径/零和相同都不等于通过.md)

# Observation criteria · "0" and "all the same" both don't mean pass

> Subpage split out of [`The criterion itself may be broken`](criterion-may-be-broken.md) (2026-09-20, parent page exceeded 10 KB).
> Both are **false negatives**: the criterion appears to give a verdict but actually measured nothing. Sister page: [The shape of a criterion](shape-of-a-criterion.md).

## No difference between candidates means nothing was measured

**Trigger**: any selection of the form "apply per candidate → measure → rank" — R9 foot/shoe selection, dose sweeps, picking the best tier.

**Self-check question** (ask at first glance at the table):

> **Are the metric values of different candidates in the ranking table exactly identical?**

Stepped in it (Project B 43% LopEarMine, 2026-09-20): R9's candidate loop only wrote **the keys it listed itself**
and never zeroed other keys. The outfit's MA ShapeChanger had long since driven `Ankle/Foot/Toe/Foot_heels` to 100,
so the four rows `none` (no keys listed = change nothing), `Foot_heels=100`, `Foot_highheels=100`, `current=…`
measured **the same pose**: si_p50 all 4.060768, tilt all 24.106232;
only the `Foot_heels=50` row differed — because it was the only one that actually changed a weight.
The table still produced a recommendation, and I still trusted it; the user later saw the collapsed ankle directly.

**Fix**: applying a candidate must come with a **zeroing domain** (first write the same-family keys to 0, then write the candidate value),
and the ranking table carries a self-check item: "all pairwise metrics identical → mark `indistinguishable`, revoke `recommended`".

**Trade-off**: the zeroing domain has to be given manually **per body part**; don't take the shortcut of "all keys" —
that would zero `Knee` and the body-shape keys too, and you'd be measuring someone else's foot.


## The threshold was calibrated on **another body**: the same cm² is not the same thing on a different mesh density

**Trigger moment**: whenever an "area/length/vertex count" threshold is reused across projects or base avatars.

**Self-check question**:

> On which body was this threshold originally calibrated? **On this body, how many vertices does it correspond to?**

Stepped in it (Project B tier 5, 2026-09-20; the cost was a real missed detection): poke's initial `min_patch_area_cm2 = 0.5`
was calibrated on Kaguya (the README assumed "vertex spacing 3–6 mm, toes poking out of a shoe 3–8 cm²").
On Milfy the toe region has only **0.0043 cm²** per vertex, and **all** the toe skin of both feet adds up to just 11.34 cm² —
"3–8 cm²" amounts to requiring 26%–71% of both feet's toe skin to poke out simultaneously as **one connected component**, which is physically impossible.
So the toes measurably poked out **14.86 mm deep with 472 vertices outside the shoe**, while `patch_count` was still **0**;
based on that I removed the shoe part's shrink key, and the user saw the toes sticking out of the shoe tip directly in Play.

**Fix**: convert area thresholds into a quantity comparable across bodies such as **vertex count** ("at least N connected vertices count as a patch"),
or at least output `area_per_vert` together with "number of components / total area dropped by the area gate" —
**never let a single 0 mean both "none" and "some, but below the gate"**.

**Knock-on**: `opening` exclusion and deleted-vertex exclusion **punch holes** in above-threshold regions, cutting a whole patch into fragments that fall below the gate.
Whenever the criterion has logic that directly `continue`s past a class of vertices, ask: could it cut the connectivity?


## A neighborhood window swallows unrelated dark/bright areas, pinning the metric

**Trigger**: the criterion is written as "take min/max / range / contrast within a ±N px neighborhood of affected pixels".

**Self-check question**:

> Could this window contain something **more extreme than the thing I'm measuring**?
> If so, min (or max) always equals it, and my computed range has nothing to do with the parameter.

Stepped in it (Project B meteors in the eyes, 2026-09-21): measuring "how much local contrast the meteor's dark edge adds",
the method was "for pixels differing from the still frame by >12, take the luminance min/max in their ±2 px neighborhood and subtract".
Across the five dark-edge levels 0.0 / 0.3 / 0.5 / 0.7 / 0.9 the computed local contrast was **174 every time, not a single digit different**;
min was always 71 and max always 245 — because the window edge brushed the **dark area of the upper eyelid and lashes**,
so min was always pinned at 71 by it, completely unrelated to the dark-edge parameter.

**Fix**: don't use "absolute extremes within a neighborhood"; instead use the **per-pixel difference against a still frame with the same settings in the same frame** —
report `brightened pixel count / max positive Δ` and `darkened pixel count / max negative Δ` separately. After switching methods the five levels separated immediately:
darkened pixels 70 → 205, deepest −22 → −104.

**Trade-off**: if you really want to see "does it pop out" (and not just "how much changed"),
use the method on the [ΔE and hue channel](rendering-and-framing/measuring-effect-visibility.md) page,
taking the background as **pixels in an annular neighborhood excluding the effect itself**, rather than taking extremes.
