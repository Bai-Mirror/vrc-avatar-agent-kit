> 🌐 English translation · [中文原文](../../../开发工具/SOP/90_交付打包.md)

# 90 · Delivery Packaging 🤖

**Output**: `交付_COMM-<订单号>/COMM-<订单号>_<客户名>_交付.zip` — **the deliverable is this single file**
**Next gate**: 95 final delivery review (👤)

---

Before packing, first use [Missing-item criteria and cleanup](90-delivery-packaging/missing-item-criteria-and-cleanup.md) to distinguish generated delivery assets, project tools, and intermediate outputs.

## Deterministic steps

### Step 1 · Pre-delivery cleanup 🤖

**Preconditions**
- [ ] 80 has passed
- [ ] Environment confirmed usable per [02 · Environment setup and manual intervention](02-environment-and-manual-intervention.md)

**Execute**
1. Delete `Assets/Editor/AvatarGen/`, `Captures/`
2. Remove development dependencies (the MCP entry) from `Packages/manifest.json`
3. Clear baked clones from the scene, save

**Post-criteria**

| Expected | How to read |
|---|---|
| Generator script directory does not exist | File system |
| `manifest.json` contains no development dependencies | Search package names, hits == 0 |
| Exactly 1 root selected into this build; other delivered roots kept and accepted one by one | Record root name, purpose, blueprintId; check against the [avatar-root convention](03-assembly-and-conflict-rules/avatar-root-conventions.md) |

---

### Step 2 · Pack the project zip 🤖

**Preconditions**
- [ ] Step 1 passed

**Execute**
1. **Pack from the project root**, containing only 5 items
2. Exclusions **only at the project-root level** (see “Exclude rules must be anchored to the project root” below)

**Post-criteria**

| Expected | How to read |
|---|---|
| Top-level entry count == 5 | List the zip's top-level entries |
| `Library` / `Temp` / `Logs` / `obj` / `Captures` hits at the **project-root level** == 0 | List zip top level |
| These names still exist **inside plugins** | Search `Packages/**/Library/` inside the zip, hits **> 0** |

> The last one is the key: 0 hits means the plugins' own same-named directories were excluded too.
> **Checking only the “number of excluded entries” cannot catch this class**, because the wrongly removed files are not on the violation list.

---

### Step 3 · Verify the project zip really compiles 🤖

**Preconditions**
- [ ] Step 2 passed

**Execute**
1. Unpack the project zip to a temporary directory
2. Open it once with Unity batchmode: `-batchmode -projectPath <临时目录> -quit`

**Post-criteria**

| Expected | How to read |
|---|---|
| `Library/ScriptAssemblies/Assembly-CSharp-Editor.dll` exists | File system |
| `error CS` hits in the log == 0 | Search the compile log |

**STOP**
- Missing namespaces like `CS0234` → go back to step 2 and check the exclude rules; **do not** manually add files into the package

> **This step is mandatory.** Once, a delivered project failed to compile as soon as the client opened it,
> precisely because this step was skipped and only “number of excluded entries is 0” was checked.

---

### Step 3b · Compiled-state menu assertions + post-upload self-test checklist 🤖→👤

① Write `期望.json` from the delivery notes (without looking at the generator code); ② post-build T4 → `menu_expect_check.py gen-request --delivery` → T1 → `check --delivery --params <T4/params.json>`; ③ attach this order's checklist per the [Post-upload self-test checklist](90-delivery-packaging/post-upload-selftest-checklist.md).
**Criteria**: verify under the strict delivery measure — behavior assertions non-empty, no untested reachable states, no ambiguity in input/matching; both states for every toggle, every slot for every radial, plus the fixed self-test items. Tool exit 0 is only a necessary condition → [Compiled-state menu assertions](90-delivery-packaging/compiled-menu-assertions.md)

### Step 4 · Pack the asset zip and write the delivery notes 🤖

**Preconditions**
- [ ] Steps 3 and 3b passed (post-upload real-device items are left for the 95 final review; do not pretend they have been tested)

**Execute**
1. The client asset package contains **only what the client supplied**; original packages we found ourselves go into `_追加素材（非客户自备）/`
2. `来源说明.txt` lists, one by one, purpose + corresponding `Assets/` path + size
3. Write the delivery notes (when finishing an order on the spot, write a full work report; for after-the-fact archiving write only archive notes, **do not fabricate the design intent of the time**)

**Post-criteria**

| Expected | How to read |
|---|---|
| Every item in `_追加素材/` has an entry in `来源说明.txt` | Entry counts on both sides are equal |
| Notes are UTF-8 without BOM, LF | Read the bytes |

---

### Step 5 · Pack the full package and verify 🤖

**Preconditions**
- [ ] Step 4 passed

**Execute**
1. Pack the full package with **store** (the inner files are already zips; compressing again just burns CPU)
2. Keep one copy of `_追加素材/` **each** at the full-package level and inside the asset zip (this duplication is intentional)

**Post-criteria**

| Expected | How to read |
|---|---|
| Full package size ≈ sum of the three members + a few hundred bytes of headers | Compare byte counts |
| **No loose files** in the delivery folder besides the full package | List the directory |
| Full package passes `7z t` | Exit code == 0 (**don't add `-bso0`**, it swallows the verdict line) |

---

### Step 6 · “Imported ≠ used” reconciliation 🤖

**Preconditions**
- [ ] Step 5 passed

**Execute**
1. Reverse-lookup, by GUID, each asset package's references in the project
2. Fill in the last column of `_素材应用表.md`

**Post-criteria**

| Expected | How to read |
|---|---|
| No blank cells in the application table | Scan the table |
| Every “not used” has a stated reason | Read it through once, by a human |

**STOP**
- An asset package has no references outside the package at all → it was never wired in; go back to the corresponding stage, do not deliver as-is

## Structure (hard requirement)

```
交付_COMM-<订单号>/
└─ COMM-<订单号>_<客户名>_交付.zip        ← no loose files left in the folder
    ├─ COMM-<订单号>_<客户名>_工程.zip
    ├─ COMM-<订单号>_<客户名>_素材.zip     contains COMM-..._素材/ + _追加素材（非客户自备）/
    ├─ _追加素材（非客户自备）/             one copy at the full-package level too (incl. 来源说明.txt)
    └─ 交付说明.txt
```

- **“Compress the whole delivery folder into one zip” is a hard requirement** — additional assets and notes must not be left outside the zip
- `_追加素材/` has one copy at the full-package level and one inside `素材.zip`; **this duplication is intentional**, don't delete it to save space
- The full package must use **store** (`7z a -tzip -mx0`) — the inner files are already zips; compressing again just burns CPU
- Verification: **full package size ≈ sum of the three members + a few hundred bytes of headers**

## The project zip contains only 5 items

`.gitignore`/`.gitattributes`, `.vsconfig`, `Assets`, `Packages`, `ProjectSettings`

Exclude: `Library` `Temp` `Logs` `obj` `UserSettings` `.vs` `.git` `Captures` `*.sln` `*.csproj`
Plus the generator script directory `Assets/Editor/AvatarGen/`
Plus remove development dependencies (the MCP entry) from `Packages/manifest.json`, otherwise when the client opens it Unity will try to pull a git package they don't need

## ⛔ Exclude rules must be anchored to the project root

> → [Exclude rules must be anchored to the project root](90-delivery-packaging/exclude-rules-anchor-project-root.md) — `-xr!Library` recursively matches same-named directories inside plugins (2026-09-01 Project G delivery failed to compile); the correct form excludes only the project-root level, and acceptance must unpack and compile once with batchmode.

## Asset packages

- Gather **the original zips “outside the client asset directory”** — half the assets may come from Downloads, another order's asset directory, or this machine's asset library
- Consolidate with **hard links**, taking no extra space
- **The client asset package contains only what the client supplied**; anything we found ourselves goes into `_追加素材（非客户自备）/`
- `来源说明.txt` lists one by one: purpose + corresponding `Assets/` path + size (MiB); for those without the original package kept, write the list only
- **VPM packages don't count as additional assets** (GoGoLoco, Light Limit Changer, etc.) — they travel with `Packages/` and VCC restores them automatically;
  just write them in the “Toolchain versions” section

## “Imported ≠ used” reconciliation

Take the asset list from [10 order intake](10-order-intake.md) and **reconcile it item by item**:
reverse-lookup references by GUID; **anything without references outside its package was not used**.
> Measured: the client gave 6 packages; only at wrap-up did we find that only 1 was actually wired in.

## Two pre-packing criteria (trigger: before the 95 final review)

- **Showcase shots must be of the delivered outfit**: at least shoot the outfit actually delivered; the generation record must show outfit slot = delivered outfit; if it doesn't match, reshoot first (`_定妆照/` mixes multiple runs). Details in [70 regression](70-regression-testing.md) “outfit hit”.
- **Compiles ≠ defect-free**: `MissingScript`, `InternalErrorShader`, and broken links don't affect compilation, yet cause magenta / silent failure for the client. Five criteria + cleanup → [Missing-item criteria and cleanup](90-delivery-packaging/missing-item-criteria-and-cleanup.md).

## Delivery notes

Two tiers:
- **When finishing an order on the spot, write a full work report** — what was done / things you must know / after opening the project
- **For after-the-fact archiving write only archive notes** — package contents / what's installed in the project / toolchain versions / after opening the project,
  **do not fabricate the design intent of the time**

Must cover at least:
1. Which paid assets are included as extras
2. **Why the performance rank is VeryPoor** (see [80](80-performance-optimization.md))
3. Which features were disabled due to trade-offs
4. **Corrections of wrong judgments previously given to the client**
5. **The project's versions are locked** (per [`_toolchain-benchmark.md`](../_toolchain-benchmark.md)); upgrading is not recommended unless problems arise (reasons in [20](20-asset-inventory-and-import.md) baseline toolchain)

Format: all txt files UTF-8 without BOM, LF line endings, box-drawing layout.

## Before cleaning the working directory

The project package excludes `.git` and the generator script directory — **and those two are exactly the history and recipe of the whole order**.
Before cleaning, first confirm these things have a copy elsewhere.

## Archiving (after delivery)

→ [Archiving and backups](90-delivery-packaging/archiving-and-backups.md): 7z/LZMA2 into `$ARCHIVE_ROOT/<个人存档|交付文件>/` (a `kit.env` setting), **verify the copy in the archive** before deleting local, update the roster; thread count set by memory for concurrency; **copying into the archive directory is done by Claude** (it is read-only in DSH's sandbox); Windows usability criteria.

## When paths contain Japanese names

Use Python `subprocess` passing an **argument list**, not through the shell — going through the shell scrambles the encoding.
