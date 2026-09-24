> 🌐 English translation · [中文原文](../../../../开发工具/SOP/问题定位/存档与依赖.md)

# Troubleshooting · Save Files and Dependency Reproducibility

> **Whether an archive can be opened matters more than how big it is.**
> Discovered on 2026-09-01 while pulling historical projects: **4 of 10 personal projects could no longer be opened.**

## Symptom

Unity exits a few seconds after launch with return code 1, and the log has a single line:

```
An error occurred while resolving packages:
  Project has invalid dependencies:
    jp.lilxyzw.liltoon: The file [<cloud-sync-dir>\VRC\liltoon\package.json] cannot be found
```

## Two non-reproducible ways of writing dependencies

**① `file:` pointing to a local directory outside the workspace**

The path often still carries an **old account name** (e.g. a user directory like `<cloud-sync-dir>/...`).
Change machines, move the directory, or let the cloud drive fall out of sync, and the project immediately won't open.

**② `git#<branch>` branch dependency**

```json
"jp.lilxyzw.liltoon": "https://github.com/lilxyzw/lilToon.git?path=Assets/lilToon#master"
```
**It only opens because `Library/PackageCache/` holds the copy cloned back then.**
Delete Library and you can never reproduce the same code again — measured: two projects on the same `#master`
got **2.3.2 and 1.10.3** respectively.

## Must check before archiving

```bash
grep -E '"(file:|https?://)' Packages/manifest.json
```
Any hit must be converted to a VPM version number before packaging.

## Finding out which version was actually used back then

**`Library/PackageManager/ProjectCache`** is text and records every package as resolved at the time.

⚠ **The `version:` field comes before `name:`**. Searching forward picks up the value of the adjacent entry —
the first time I misread one project's AAO as `3.2.1` (actually `1.9.8`).

`source:` is the `UnityEditor.PackageManager.PackageSource` enum:

| Value | Meaning |
|---|---|
| 1 | Registry |
| 2 | Builtin |
| 3 | **Embedded** (in `Packages/`; this is what VPM installs) |
| 4 | **Local** (`file:` pointing outside the workspace) |
| 5 | LocalTarball (`.tgz`) |
| 6 | Git |

## Conversion procedure

1. Put the package contents into `Packages/<包 id>/`
   — **prefer the copy in the project's own `Library/PackageCache/`** (the bytes actually used for the build back then);
   only if absent, copy from a sibling project on the same version
2. **Delete** that line from `Packages/manifest.json` (VPM-managed packages don't go in the UPM manifest)
3. Write the version number in both `dependencies` + `locked` in `Packages/vpm-manifest.json`
4. Clear the corresponding entry in `packages-lock.json` so Unity re-resolves it
5. Keep the original files as `.bak-<日期>`

**Just remove dead dependencies that aren't used**; don't force-fit a version
(instance: one project depended on AAO 1.9.8, which was not available locally, and **not a single AAO component was used in that scene**).

## Don't mistake lilToon's self-rewriting for "package contamination"

Two copies of the same lilToon 2.3.2 had 5 shader files with different contents, **each side newer in some and older in others**.
That is **lilToon itself rewriting `#pragma skip_variants` according to the render pipeline** (`Editor/CurrentRP.txt` is its marker);
it rewrites them automatically on import, so **either copy is fine**.

## Can an old archive be deleted: comparing file counts alone doesn't count

`7z l -slt` outputs the **CRC32** of every file, so you can compare `(path, size, CRC)` triples without extracting.

**Judge in three categories:**
- **Fully identical** (0 missing, 0 different) → deletable
- **Differences only in regenerable items** (`Library/`, `Assets/*__Generated/`, `Packages/*.temp/Builds/`,
  old-version sources removed after a plugin upgrade) → deletable
- **Has unique non-regenerable content** → first figure out what it is.
  > Instance: in one "copy", 7 materials were **newer** than in the new package, looking like lost work;
  > the diff showed **7 materials batch-switched to `VRChat/Mobile/Toon Standard` + render queue pinned to 2000**
  > — that was a **failed mobile conversion**, not content worth keeping.

**Shader GUID for reference**: `e765db0afa7ecfc44ade2e4e2491f65a` = VRChat/Mobile/Toon Standard.

## Transfer and verification path

- Packages go straight into `$ARCHIVE_ROOT/` (the archive directory configured in `kit.env`)
- **Run `7z t` on the copy in the archive directory**; before deleting the local source you must verify that copy, not the pre-packaging source
