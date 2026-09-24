> 🌐 English translation · [中文原文](../../../../开发工具/SOP/30_捏脸/捏脸凹凸的归因与修复.md)

> ← [30 · Face sculpting](../30-face-sculpt.md) ｜ Sibling: [Baking and compensation](baking-and-compensation.md)

# After sculpting, how to attribute and fix "bumps" on the face

**Trigger moment**: the user says "face sculpting has made the mesh show a bumpy texture that hurts the look", or you yourself see wrinkle ridges in a cavity/toon render.
Implemented on 2026-09-20 on Project B v2; 輝夜 (Kaguya, Project A) hit the same kind of problem earlier but **failed to attribute it**
(the "before sculpting" baseline in `工程A/Assets/_Work/嘴部褶皱定性.md` can't be read, and that 24.5°/21.1% table **has no control, so its conclusion doesn't hold** — don't copy it).

## First rule out two plausible-looking wrong paths

**① It's not "stale custom normals".** The intuition: blend shapes changed the geometry, the vendor's baked custom split normals didn't rotate along, so shading goes wrong.
Measured on Milfy `Body`: the vendor's custom normals **already deviate from geometric normals by mean 37.7°, p99 149.9°, with 34332/42334 corners over 5°** —
that's an entire hand-painted normal field (standard practice for layered face cards), and the 2–11° rotation of geometric normals has almost no effect on it.
After rotating the custom normals to follow via Rodrigues and re-rendering, **the toon image B−C diff p99 = 0.0/255** — a completely useless operation.
> **Checkable question**: before compensating normals, measure once "the angle between custom normals and geometric normals".
> **If it's large (on the order of >20°), the normals are hand-painted and decoupled from geometry, and rotating to follow is bound to be useless**; only if it's small is following worthwhile.
> Similar lesson: [The brightness compensation in recoloring is a mathematical identity](../40-texture-and-coloring/base-texture-and-recolor-techniques.md).

**② It's not "the surface got wrinkled by stretching".** Per-vertex Laplacian (umbrella) magnitude: after sculpting p99 **dropped** from 4.757 mm to 4.675 mm,
with an increment p99 of only 0.132 mm. Overall curvature didn't get worse, so don't do global smoothing — that would only smooth away the sculpting.

## The real cause: local crushing + interpenetration between layers. Locate it with three metrics together

All computed on two sets of coordinates, "vendor original basis" and "basis + sculpting displacement", **with the same face table**:

| Metric | How to compute | Project B v2 measured (vendor → sculpted) |
|---|---|---|
| **Mesh self-intersection** | `BVHTree.FromPolygons(...).overlap(self)`, excluding adjacent face pairs sharing vertices | 632 → 666, **114 new** (66 pairs are `Face_transparent` cards interpenetrating) |
| **Face normal rotation** | Angle between face normals (Newell/sum of cross products) before and after | **30 faces >25°**, max 49.69° |
| **Area collapse** | `A_after / A_before` | **60 faces <0.5**, min **0.129** |
| Normal flip | Angle >90° | 0 (flipping is a more severe tier; not reached) |

> ⚠ **These three can't detect the "stepped horizontal banding" kind.** They all measure "how much **the face itself** rotated / collapsed / whether it penetrated",
> while those layered horizontal light/dark bands on the eyelids are **step discontinuities between adjacent faces**. On 2026-09-20 I fixed using only these three;
> the hard dark line on the lower eyelid disappeared, **but not one of the stepped bands on the upper eyelid moved** (none of the three exceeded thresholds in that band: rotation p99 9.03°, area min 0.882, no new self-intersections),
> and agy spotted it at a glance under in-engine shading. **A fourth metric must be added**:

| Fourth metric | How to compute | Why it's necessary |
|---|---|---|
| **Δdihedral (change in dihedral angle between adjacent faces)** | For each edge shared by two faces, measure the difference in the angle between the two face normals before and after sculpting | Corresponds directly to shading steps; it's the quantity toon shading actually shows |
| **High frequency of the displacement field `\|Laplacian(D)\|`** | The umbrella operator on D using edge adjacency | Used as **seeds**; exposes problem regions earlier than Δdihedral |

**How to set thresholds: use an untouched region as the control.** Project B measured (number of edges with Δdih >5° / p99 / `\|Lap(D)\|` p99):
upper eyelid 34 / 5.43° / 0.4445mm; lower eyelid 200 / 7.76° / 0.4683mm; around the mouth 83 / 6.55° / 0.227mm;
**forehead (never touched) 0 / 0.07° / 0.0386mm**. The control band is nearly zero → `Δdih>3°` and `\|Lap(D)\|>0.06mm` are enough to separate them.

**Write the seed set as**: new self-intersecting faces ∪ rotation>20° ∪ area ratio<0.75 ∪ **vertices with `\|Lap(D)\|>0.06mm`** ∪ **vertices of edges with `Δdihedral>3°`**.
After Project B's fix: upper eyelid 34→**10**, lower eyelid 200→**14**, around the mouth 83→**11**, with all three hard thresholds still 0; the cost was perturbation p99 rising from 1.19 to 1.37 mm.

⚠ **The blending boundary of smoothing introduces a bit of high frequency into originally clean regions** (control band `Δdih p99` 0.07°→0.34°, `\|Lap(D)\|` 0.039→0.171mm).
**List the control band in the acceptance table too**, and confirm its edges>5° remain 0; if some edges exceed the threshold, `r_blend` has been spread too wide.

**The three will land on the same band**; binning statistics by z locates it. For Project B it was the **lower eyelid–cheek band** at z 1080–1128 mm;
the upper eyelid band (p99 9.03°, area min 0.882) and the around-the-mouth band (9.55° / 0.688) were relatively clean.

**Per-key attribution**: turn on only one key and run the same three metrics to know who did it.
Project B: `eyelid_corner_up = −1.0` alone gave 30 collapsed faces, `eyelid_corner_down = 1.0` another 10;
the top source of self-intersection was `face_child = 0.38` (64 places from that key alone).
> **Negative values are reverse linear extrapolation**, a range the vendor never designed for, and the most likely to cause this; check full-range (±1) keys first.

## Fix: local synchronized displacement across layers (repair, not reset)

Principle: adjacent card layers got **different displacements**; the layer spacing is only a few tenths of a millimeter, so once the difference gets large they interpenetrate.
So what needs smoothing is the **displacement field**, not the geometry; and only within the neighborhood where things went wrong.

1. **Seeds** = new self-intersecting faces ∪ faces with rotation>20° ∪ faces with area ratio<0.75, taking all their vertices.
2. **Influence weight** `w(v)`: the 3D distance `d` from v to the nearest seed, `w = smoothstep(1 − d/r_blend)`, 0 when `d ≥ r_blend`.
3. **Smoothing**: `D̃(v) = Σ_j exp(−(d_ij/(0.6·r_smooth))²)·D(j) / Σ w`, with the neighborhood by **3D KDTree radius `r_smooth`**
   (**not mesh connectivity** — it must cross unconnected card layers, otherwise the layers can't be synchronized at all).
4. `D(v) ← D(v)·(1−w) + D̃(v)·w`, iterate 1–3 rounds.

**The parameters were swept, not made up.** Project B swept 5 sets; the criterion = the three metrics go to zero with minimal perturbation of the sculpting:

| r_smooth / r_blend / rounds | New self-intersections | Faces >25° | Area <50% | Area min | Perturbation of sculpting max/p99/mean |
|---|---|---|---|---|---|
| 4 / 10 / 1 | 16 | 0 | 0 | 0.552 | 1.43 / 0.73 / 0.11 mm |
| 8 / 16 / 2 | 10 | 0 | 0 | 0.692 | 2.31 / 1.08 / 0.20 mm |
| **10 / 18 / 2** | **0** | **0** | **0** | **0.726** | 2.54 / 1.19 / 0.23 mm |
| 12 / 20 / 3 | 4 | 0 | 0 | 0.730 | 2.64 / 1.47 / 0.29 mm |

**Trade-off**: larger isn't better (12/20/3 actually climbs back to 4), because once the smoothing radius exceeds the card-spacing scale, layers start pulling each other off.
**What to do if you can't reach all zeros**: prefer tightening `r_blend` (move fewer points) over adding rounds (adding rounds repeatedly smooths the same points, and perturbation rises fast).
**Add one more acceptance check**: the total number of self-intersections must not exceed the vendor original (Project B 629 < 632) — otherwise you've just moved the problem elsewhere.

## Send the conclusion for falsification, and it will pick out residuals below your thresholds

This time on Project B we used `agy_ask` + a Workbench cavity triptych (A original / B unfixed / R fixed, same camera, lighting, materials).
It confirmed "B has wrinkles, R fixed them, R didn't flatten the sculpt", but **falsified "completely eliminated"**:
it pointed out that R still has slightly deeper shallow steps than the original at the **outer eye corners** and **upper lip/philtrum**; it also pointed out that **B's philtrum–upper lip also has compression creases** (I had originally reported only the lower eyelid band).
And it measured R's **cheek peak curvature flattened by about 5–10%**.
> These are all below my numerical thresholds — **"three metrics at zero" doesn't equal "no residual visible to the eye"**; report both, not just the numbers.
> Related: [The criterion itself may be broken](../troubleshooting/observation-criteria/criterion-may-be-broken.md).
