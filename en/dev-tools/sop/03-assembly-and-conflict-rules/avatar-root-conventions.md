> 🌐 English translation · [中文原文](../../../../开发工具/SOP/03_装配与冲突通则/头像根口径.md)

# Counting conventions and fact-checking for "how many avatar roots"

> ← [03 · Assembly and conflict rules](../03-assembly-and-conflict-rules.md). Trigger: before reading the "number of avatar roots" in any report/document; or before writing an analysis report's conclusion into an SOP.

There are four ways to count "avatar roots" in the same scene, and when the counts differ, people using different conventions end up overturning each other (measured on historical projects: one project had 15 roots / 2 active / 2 descriptors in the archive; another project's "7" was actually two runs counted together).

| Convention | Definition | When to use |
|---|---|---|
| Scene roots | Every object in the scene with a `VRCAvatarDescriptor`, including disabled ones | Investigating "how many times a change was applied" |
| Scene-wide descriptors | Also counts prefab instances and backup prefabs | Cleaning archives, checking blueprintId collisions |
| **Active root** | Only this one is the current delivery state and will be uploaded | **Always use this convention for delivery and acceptance** |
| Including backup prefabs | Whole per-avatar copies such as `Backup/` `bk_*.prefab` | Cleanup and dependency inventory |

- **Criterion**: when writing "there is only 1", you must state which of the above conventions you mean (by default it should mean "only 1 goes into the build"); prefabs in `Backup/` often also carry a `blueprintId` and can overwrite the live version. For diagnosing multiple roots, see the [symptom table in section 4 of 03](../03-assembly-and-conflict-rules.md).
- **If you can't meet it**: if the counts don't reconcile, stop first and don't delete — deleting the wrong root loses the live version; ask the user before any deletion.

## Three auxiliary conventions that are easy to trip on

- **`_定妆照/` may mix multiple runs**: two batches of renders from the same project (measured: H3-Eku had two batches on 09-01) can be mixed in the same directory, and ordering by filename is unreliable for old vs. new; before taking images, check their generation time / run batch.
- **13/14 are personal archives, not positive delivery samples**: multiple roots and broken references in historical projects are archive leftovers; read them only as counterexamples, never as proof of "how the SOP should be done".
- **Mechanically verify the "facts" in analysis reports first**: the six historical analyses A–F and the first draft of the overview all contain errors of their own (sources attributed to the wrong project, two runs counted together, a single source treated as settled); before citing their conclusions, check against the original text or files, and only then write "verified in this document".
