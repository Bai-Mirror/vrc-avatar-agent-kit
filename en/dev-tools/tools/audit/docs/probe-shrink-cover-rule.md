> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/probe-shrink-cover-rule.md)

# Probe shrink_cover · criterion revision history (CU / CX / CT) <!-- nav -->

> Former name: T1 `AuditStateDriver` / T3 `AuditTurntable` etc. (originally `审查/README.md`) middle part of §3.2.8. § numbers follow the original text; for cross-page § references see the [documentation index](../README.md). <!-- nav -->
> Previous page: [Probe shrink_cover (shrink-key occlusion consistency) · request and parameters](probe-shrink-cover.md) · Next page: [Probe shrink_cover · output, diagnostics, self-check, and calibration](probe-shrink-cover-output.md) <!-- nav -->

> **Task CU changed the criterion (the old distance basis was falsified)**: `seq_t33_calib` (Project B 43%) swept `cover_dist_mm`
> at 3/10/25/40 mm with positive and negative samples: 3 mm caught the positive sample (socks off + `Ankle` forced on) but falsely reported the negative sample `Shoulder`, while 10/25/40 mm missed the bare ankle.
> The root cause is that distance answers "is there cloth **nearby**" rather than "is there cloth **outside** me" — a loose coat sits 1–3 cm from the skin, and right **beside** a bare ankle is the shoe upper.
> Now the default is `cover_rule=outward_ray`: for each affected vertex, take the body's outward pseudo-normal n (`PokeAngleWeightedPseudo` angle-weighted, sign corrected with the BakeMesh
> normals, sharing the same implementation as poke's shell), and cast 1 ray along n + 4 cone rays at ±`cone_deg` from `v + n*origin_mm`,
> of length `cover_ray_mm`; hitting any visible clothing triangle counts as covered, voted per `ray_vote`. The old distance readings are kept as reference columns
> `nearest_cover_dist_mm` / `covered_near_ratio` (the latter = share of affected vertices whose nearest distance ≤ `cover_dist_mm`, excluding inside-shell),
> **not participating in the verdict by default**.

> **Task CX / B-T33b changed the verdict shape ("and" → "or")**: in the positive sample of `seq_t33_calib2` (socks off + `Ankle` forced on),
> **most** of that key's affected vertices **were already inside the shoe cavity** (outward rays at 30–80 mm hit the shoe surface, a legitimate occlusion); what was really exposed above the shoe opening
> was only **21/221 = 9.5%**, failing `ratio_thr=0.60`; but their absolute area was **6.86 cm²**, far above the area gate. So under all three
> `cover_ray_mm` values (30/50/80) the positive sample was **missed every time**. Root cause: a blend shape's affected region naturally **spans both occluded and exposed zones**, so the ratio gets
> diluted by "the part that is legitimately covered", while the human eye sees the **absolute exposed area**. Hence `verdict_rule` now defaults to `"or"`; `"and"` restores the old behavior in one step.
> Each row also gives `verdict_by` (`ratio`/`area`/`both`/`none`) and `ratio_ok`/`area_ok`, reporting truthfully which side met its threshold.

> **Task CX: initial `area_thr` of 1.0 cm² (⚠ pending calibration with positive/negative samples in B-T33b; not a verified value)**. Derivation: 10 mm × 10 mm
> of continuous exposed skin (about one fingernail) is the smallest patch recognizable at a glance, without looking at labels, from a 0.5–1 m viewing distance; below ~0.2 cm² (a 5 mm round spot) it is
> easily confused with single vertices / mesh seams / ray noise, so ~5× margin is taken = **1.0 cm²**. Trade-off: half as strict as the old 2.0, giving the positive sample's 6.86 cm²
> a 6.8× margin; the cost is that 1–2 cm² boundary exposures will also be reported (on the conservative side). **Looking at the N (fully dressed) step of `seq_t33_calib2`: at 30 mm,
> `Chest_2=71 cm²`, `Spine_2=95.9 cm²`, and `"or"+1.0` would judge them uncovered too (all 8 keys in that step would be uncovered →
> `self_check` suspicious → all `undecidable`); at 50/80 mm the negatives clearly converge but are still not all ok.** So **B-T33b must sweep
> `cover_ray_mm` together with `area_thr`** (positive sample `Ankle` must be uncovered, negative samples all ok, no flip across 30–80 mm), not just tune
> `area_thr`. **Predicted failure mode**: if some positive sample's exposed area is also <1 cm², or a negative sample still has >1 cm² of false exposure at a short-ray step,
> that step's `verdict` will give a wrong conclusion — in that case `verdict_by` will show it was triggered by `area`, and then decide whether to relax `cover_ray_mm`
> or raise `area_thr`.

> **Task CT fix (root cause of the 100% false positives on the first actual run)**: CS's default string `(?i)(…|ear|head|…)` matched against the **whole path + substrings**,
> hitting the `ear` in `_Outfit/LopEarMine/…` and the `ear` in `Underwear`, excluding the entire LopEar coat/socks/shoes being worn;
> while the body itself (`Body`) stayed in the set, and the tested keys lived on `Body_base` → every key in all four states had `uncovered_ratio=1`,
> `Ankle.nearest_cover_dist_mm≈799mm` (the nearest "clothing" left was only the bra). Now:
> **①** exclusion only looks at leaf names with whole-word matching (`Ear`/`Hair_Front`/`Jacket_Ear` still excluded; `LopEarMine`/`Shoes` not excluded);
> **②** the body family (`body` itself + other pieces of the same base avatar: `Body`, `Body_b*`, judged by `ShrinkCoverRules.IsBodyLike`'s
> normalized word root / same-parent prefix) never enters the set; **③** the list is written into the output together with the judgments (`garments_considered`/`used`/`excluded`,
> `body_leaf`/`body_family_root`/`body_family_rule`); **④** `self_check` is added (see below).
> Cost: word matching is "whole token equality", and compound names like `NaturalNail`/`Hairpin`/`Kumachan_HeadAcc` are not split on CamelCase,
> so they are no longer excluded by the default word list (better to exclude too little than to wrongly hit a whole outfit); to exclude them, write the word list with words that will hit, or use a custom regex.
