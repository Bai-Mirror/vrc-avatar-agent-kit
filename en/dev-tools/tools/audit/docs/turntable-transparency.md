> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/turntable-transparency.md)

# T3 · Transparency sorting criteria <!-- nav -->

> Formerly: T1 `AuditStateDriver` / T3 `AuditTurntable` etc. (original `审查/README.md`) §6 "Transparency sorting criteria". § numbers follow the original; for cross-page § references see the [documentation index](../README.md). <!-- nav -->
> Previous: [T3 turntable renders · request and output](turntable.md) · Next: [Self-check 1 · provenance of the GM / SDK symbols used via reflection](selfcheck-symbols.md) <!-- nav -->

### Transparency sorting criteria (why it is judged this way)

Candidates = every **material slot k** of each renderer R under the avatar with `activeInHierarchy && enabled`, satisfying
`sharedMaterials[k].renderQueue > transparent_queue_min` (default 2501), where k falls within the range of slots that actually get rendered.
Unity's material→submesh mapping: **submesh i uses `mats[min(i, mats.Length-1)]`**, so when `mats.Length > subMeshCount`
the extra material slots are never rendered (a warning is recorded and they are skipped); when `mats.Length < subMeshCount` the last material slot covers all
submeshes after it (the mask is their union, noted with `slot_note` in the candidate).
(The task brief originally said "when there are fewer submeshes than materials, the extra materials draw the last submesh"; checked against Unity's actual mapping, the direction should be "when there are fewer materials than
submeshes, the last material covers the extra submeshes". This implements the actual rule and records the discrepancy.)

**Why it changed from "whole renderer" to "(renderer, submesh)"**: the first version worked per renderer, so the mask was the outline of the whole renderer, most of which was
opaque submeshes (the hair itself); an opaque object is supposed to hide what's behind it, so every record was judged "vanished", with vanish ratios up to 0.97 —
all false positives (measured on Project A, 2026-09-18). After switching to per-slot, opaque slots (queue ≤ `transparent_queue_min`) never enter the candidates.

For each candidate (R, k) and each view, render five images (A is the turntable image itself, reused):

| Symbol | How it is rendered | Meaning |
|---|---|---|
| **M** | Only R visible (other renderers `enabled=false`), R's slot k = FlatColor pure white, other slots = Invisible, background pure black | Non-black pixels = screen mask of slot k |
| **C0** | Only R visible, slot k = original material, other slots = Invisible, **background pure black** | Image containing only slot k's own emitted color |
| **C1** | Same as C0, **background pure white** | Used to solve for per-pixel transmittance |
| **B** | Full scene normal, only slot k = Invisible, background = requested `bg` | Image without slot k; `B ≠ bg` = something is behind the slot |
| **A** | Full scene normal, background = requested `bg` | Normal image (which is also the turntable image) |

Per pixel (counted only within the mask and where `t >= t_min`):

- Transmittance `t = clamp(three-channel mean of (C1 − C0), 0, 1)`. Derivation: under alpha blending `C0 = src·a`, `C1 = src·a + (1−a)`,
  so `C1 − C0 = 1 − a` = transmittance; `t≈0` is opaque, `t≈1` fully transparent.
- `behind`: color difference between `B` and `bg` > ε → there really is something behind slot k;
- Expected color `E = C0 + t·B` (linear blending model);
- `vanished`: `behind` and `|A − (C0 + t·bg)| < ε` (A looks as if the background is behind) and `|A − E| > ε` (clearly different from correct blending);
- `vanish_ratio = vanished / behind`; `behind < min_behind_px` records `null`;
- `model_error_p50 = median(|A − E|)`, taken over pixels with `t >= t_min` that are not vanished — used to see whether this slot's shader satisfies the linear model.

**Why t ≥ 0.15**: when `t` is very small the shader is nearly opaque, `C0 + t·B` differs from `C0` only slightly, and `|A − E|` is dominated by quantization noise,
easily jittering around ε=0.03; moreover, a nearly opaque slot is supposed to hide what's behind it, so "can't see through it" is not worth discussing.
0.15 is the empirical lower bound of "at least 15% passes through"; it can be changed with `t_min` in the request.

**Why the linear model E = C0 + t·B**: ordinary alpha blending (including lilToon transparent modes) is `dst = src·rgb * a + dst·(1−a)`,
which expands to exactly `C0 + t·B` (`C0 = src·a`, `t = 1−a`), so the model holds exactly. What mainly breaks this formula is
**the Refraction / GrabPass family**: slot k samples "the screen behind" while shading, and in C0/C1 it samples the black/white background,
different from the real background it samples in A, so `E` doesn't match A and `model_error_p50` rises noticeably (Screen/Multiply/custom Blend
usually don't match either). Pure additive (`Blend One One` and the like) solves to `t ≈ 1`, and `E = C0 + B` exactly equals `A`, so it neither false-positives nor
gets judged vanished (it "adds on top" rather than "pushing out what's behind").

**How to read model_error_p50**:
- Low (< ~0.02) with high `vanish_ratio` → the linear model holds and what's behind really disappeared; trustworthy;
- High (> ~0.05) → the slot's shader is not ordinary alpha blending (Refraction/GrabPass/custom Blend); the vanished verdict is untrustworthy, look at A/B/C0/C1 first;
- `null` → this slot never reached `t >= t_min` or had no `behind` pixels in any view; effectively not measured.

**Where vanished_owners comes from and how far to trust it**: for flagged records, every renderer other than R that is "currently enabled and within
`culling_mask`" is temporarily swapped to a FlatColor of a unique color, R is turned off, and one ID image is rendered under condition B (a separate
`RenderTextureReadWrite.Linear` + colors written via `Material.SetVector`, bypassing Gamma/Linear color-space conversion),
then decoded and counted over the vanished pixels, returning the top 3. It answers "what vanished" (in P3 it should be the merged mesh of `Hair_GoldenHour`);
pixels that can't be decoded (background / occluded by another of R's own slots) are not counted in the denominator. Anti-aliased edge pixels with blended colors are classified by nearest neighbor,
so the shares are approximate — only for finding suspects, not for threshold verdicts.

**Residual limitation (still present in the second version, but no longer a systematic false positive)**: mask M is "the geometric outline of slot k" and does not account for self-occlusion by R's other slots.
If slot k is a piece of transparent geometry and an opaque slot of R covers the same pixels in front of it, A equals that opaque slot in front; under particular color schemes
`|A − (C0 + t·bg)|` can still be < ε and be misjudged. This differs from the first version's systematic false positive of "the whole renderer counted as vanished" (entire records at 0.97);
it only appears on a few pixels where slots of the same renderer overlap front-to-back. When encountered, look at the four images A/B/C0/C1 and `vanished_owners` (mostly undecodable,
falling into "not counted in the denominator") to tell them apart.

---
