> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/foot-shoe-candidates-fields.md)

# R9 Foot-Shoe Selection · New Fields (CS / D2 / CW) <!-- nav -->

> Formerly: T1 `AuditStateDriver` / T3 `AuditTurntable`, etc. (originally `审查/README.md`) middle part of §3.4. § numbers follow the original; for cross-page § references, look them up in the [document index](../README.md). <!-- nav -->
> Previous: [R9 Foot-shoe selection candidates · request, execution and output](foot-shoe-candidates.md) · Next: [R9 Foot-shoe selection · lessons, insole-surface convention and acceptance](foot-shoe-candidates-metrics.md) <!-- nav -->

**New fields (task CS, 2026-09-20)**:
- `candidates_zero` (request level) / `zero_keys` (candidate level, overrides the request level): the set of keys zeroed before applying a candidate.
  Application order = **zeroing domain first, then candidate keys**; both go onto the restore stack. If not written = old behavior (only candidate keys are written).
- Per row: `zero_applied` (keys in the zeroing domain matched on that mesh → old values before zeroing), `applied_readback`
  (after zeroing + all candidate keys are written, each key is read back with `GetBlendShapeWeight`; for same-name multiple frames, the first index is taken),
  `zero_missing` (keys in the zeroing domain that didn't match, **not counted as a hard failure**).
- Per row: `indistinguishable_with` (ids of other candidates within the same state whose six metrics all differ by <1e-6).
  That state gets `state_indistinguishable=true`; it's then split by `applied_readback`/`zero_missing` (**task D2, see below**):
  when truly equivalent, `recommended` is kept with an additional `recommended_note`; when not zeroed/not written, `recommended=null` +
  `recommended_suppressed_reason`. A Chinese explanation is added to top-level `warnings[]`. Sorting and `rank` are unchanged.

**New fields (task D2 / B-T33d, 2026-09-22): the indistinguishable warning is split into “candidates equivalent” vs. “not zeroed”**:
- State-level `indistinguishable_kind`: `"candidate_equivalent"` (the candidates really are equivalent) or `"not_zeroed"`
  (not zeroed / keys not written); at the same level, `indistinguishable_group` (candidate ids of the indistinguishable group, sorted) and
  `indistinguishable_reason` (the criterion, in Chinese) explain which class it was split into and on what basis.
- Split convention (pure function `ClassifyR9Indistinguishable`, `AuditStateDriver.cs`):
  - **Candidates equivalent**: the group has at least two candidates that “should write something” (have candidate `keys` or a non-empty zeroing domain), whose `applied_readback`
    are pairwise different and all non-empty, with no `zero_missing`. → `recommended` is **not set to null** (the first in sort order is taken; the final tie-break
    is the candidate id, so the result is deterministic), with an additional `recommended_note:"候选等价，任选其一…"` (candidates equivalent, pick any one…); warnings explain “read-backs all differ,
    the keys really were written”. Basis: **if the read-backs differ yet measure the same pose, the only possibility is that the candidates themselves are equivalent**.
  - **Not zeroed / not written**: read-back empty, read-backs identical, `zero_missing` non-empty, or the group doesn't have two key-writing candidates with differing read-backs.
    → `recommended=null` + `recommended_suppressed_reason` (keeping the old convention).
- Candidates like `current_no_zero` that “by design write no keys” (`keys` and zeroing domain both empty, read-back `{}`) are **not counted** as “should write”,
  so that their empty read-back isn't misjudged as “keys not written” (this is the only difference between it and the “`none` with the shoe group not zeroed”).
- Offline self-check: `perception/selftest_r9_indistinguishable.py` extracts the pure layer as a whole, wraps it, and compiles and runs it separately
  (without starting Unity, testing exactly the same code as production): on the production fixture `seq_lopear_r9/01_measure/r9_Set05_sock.json`,
  `m_sho_off` (sock group, read-backs pairwise different, metrics all equal) asserts `candidate_equivalent`; after removing the zeroing domain from `m_sok_off` in `r9_Set05_shoe.json`,
  the two “no key written” candidates assert `not_zeroed` (“not zeroed”). Unity live re-verification: see the Project B Play session.

**New fields (task CW, 2026-09-20)**:
- Per row: `patch_verdict` (`"undecidable"` only when the four columns are suppressed), `suspect_subthreshold`,
  `dropped_components`, `dropped_max_area_cm2`, `dropped_total_area_cm2`, `dropped_max_depth_mm`,
  `area_per_vert_cm2`, `area_per_vert_pos_source`, `min_patch_area_cm2`, `min_patch_area_source` (from the row's best pairing).
  **These diagnostic columns are still written when the four columns are suppressed to null** — `suspect_subthreshold=true` or `dropped_max_depth_mm`
  greater than `tau` is direct evidence that “0 patches doesn't mean no piercing”. State-level `patch_columns_suppressed` /
  `patch_columns_suppressed_reason` explain why they were suppressed.
- `rows[].by_sub_part[]` adds `patch_count`, `total_patch_area_cm2`, `suspect_subthreshold`,
  `suspect_reason?` (per sub_part, judging “vertices exceed the threshold but didn't form a patch”).
