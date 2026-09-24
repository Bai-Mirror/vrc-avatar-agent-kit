> 🌐 English translation · [中文原文](../../../开发工具/SOP/65_感知机制.md)

# 65 · Perception mechanism (turning blend-shape and visibility fitting into data)　🤖

> ← [00 · Master table](00-overview.md). Trigger: when you need to decide "while this garment is on, what should the body's / other parts' keys and visibility be", or when writing declarations or re-checking scenario classification.

**Purpose**: turn "how the body should shrink once a garment is on, which shoes the foot shape follows, who covers whom and should be hidden" from **judging by eye on images** into **declaration + value reconciliation**. Looking at images is the most expensive and least reliable method (the user's ruling, 09-18); the blend-shape fitting in every project was done poorly precisely because it relied on eyeballing image by image.

**The approach in one sentence**: for each order, write a **declaration** (when which part is visible, what value a given key should take / which part should be hidden); the validator reconciles it item by item against the readings produced by [70 regression test](70-regression-testing.md) (T1 states, writer graph, geometric distances), and outputs verdicts such as `pass / violation / no_data / undecidable`; images are only used to re-check candidates that the data picks out.

## How scenarios are classified

Externally we uniformly speak of **9 kinds** of dependency (D1–D8, with D4 split into a/b); internal re-checking and gap-hunting use **12 blend-shape classes + 4 visibility-only classes**. The mapping between the two schemes, how many entries of each class are live in Project A, and how to classify cases like F/C2/C3 that don't map to a single dependency → [Scenario classification mapping](65-perception-mechanism/scenario-classification-reference.md).

Trade-off: better to add one more re-check class than to force a mismatching scenario into an existing dependency just to keep it at 9; before something goes into the schema, add the dependency kind first.

## Division of labor with 70 regression test and the audit tools

| Who | Responsible for |
|---|---|
| [70 regression test](70-regression-testing.md) | The audit flow: preparation sheet, T1 full scan, real sequences, same-name key following, pinpoint image checks on candidates. It produces the readings |
| `通用工具/审查/perception/` ([README](../tools/audit/perception/README.md)) | Offline Python tools that only read the project and never launch Unity: writer graph `writers_static.py`, declaration draft `decl_draft.py`, declaration validation `decl_validate.py` (schema `perception-0.2`), verdict engine `verdict.py` + universal rules `rules_universal.py` (including same-name key mismatch U-KF), thresholds `thresholds.yaml`, pose library and pose × state plan |
| `通用工具/审查/` ([README](../tools/audit/README.md)) | Unity-side data collection (T1/T3/T4, part inventory); deploy to a project with `perception/sync_audit.py` |
| This chapter | Scenario definitions and classification criteria; once declaration reconciliation is in place it merges into step 5 of 70 |

**Status and limits**: the declaration reconciliation of `verdict.py` has not yet been merged into the must-run flow for every order (see "Coverage record" in 70); items whose thresholds are not calibrated (e.g. T-33 `shrink_cover`) serve only as leads, not as "pass" — see [Foot-shape and shrink-key ownership](50-outfit-and-hair-assembly/foot-and-shrink-key-ownership/two-key-types-and-writers.md). **`skipped`/`no_data`/`undecidable` are all not pass**: when a dependency input is missing, the validator degrades, and the report must truthfully say "not tested".

## Where this chapter is referenced

- The D1–D8 in parentheses in the entries of the [Conflict handling checklist](50-outfit-and-hair-assembly/part-understanding-and-menu-layout/conflict-handling-checklist.md)
- Visibility conditions in [Three axes and reading meaning into names](50-outfit-and-hair-assembly/part-understanding-and-menu-layout/three-axes-and-naming-trap.md) (D8 pose-dependent)
- Step five of [Foot-shape and shrink-key ownership](50-outfit-and-hair-assembly/foot-and-shrink-key-ownership.md): poke produces the numbers
