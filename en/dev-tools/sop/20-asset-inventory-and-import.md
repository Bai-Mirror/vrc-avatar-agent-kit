> 🌐 English translation · [中文原文](../../../开发工具/SOP/20_素材清点导入.md)

# 20 · Asset inventory and import　🤖

**Purpose**: turn the asset packs into a Unity project that opens, compiles, and whose GUIDs haven't been touched.
**Output**: the project's `Assets/`, `导入报告.md`, **`_素材应用表.md`**
**Next gate**: [30 Face sculpting](30-face-sculpt.md) (🔒 30a manual)

> ⚠ **50 Assembly must come after 30**; don't start it before face sculpting is finalized —
> swapping the FBX resets material arrays and breaks up the armature lock. For scheduling see
> [01 · Automated execution and parallelism](01-automation-and-parallelism.md).

**Deep water**: three pitfalls of statistical criteria, the reverse check before producing numbers, dependency reproducibility →
[Implementation pitfalls](20-asset-inventory-and-import/implementation-pitfalls.md)
**Creating the project and first compile** → [02 subpage](02-environment-and-manual-intervention/project-setup-and-first-compile.md) (not repeated here)

---

## Deterministic steps

### Step 1 · Prepare the project　🤖

**Preconditions**
- [ ] Environment confirmed usable per [02 · Environment preparation and manual intervention](02-environment-and-manual-intervention.md)
- [ ] The package-picking list from [10 Order intake](10-order-intake.md) is settled

**Execute**
1. Create the project per [Creating the project and first compile](02-environment-and-manual-intervention/project-setup-and-first-compile.md)
2. Inject `scriptingDefineSymbols: {Android,Standalone}: VRC_SDK_VRCSDK3` into `ProjectSettings.asset`

**Post-criteria**

| Expected | How to read |
|---|---|
| Number of `locked` entries in `vpm-manifest.json` == number of VPM package directories under `Packages/` | Compare the two numbers |
| `Library/ScriptAssemblies/Assembly-CSharp-Editor.dll` exists | File system |

### Baseline toolchain (all in this machine's cache; installable offline)

```
Unity 2022.3.22f1 · SDK 3.10.4 · MA 1.18.1 · NDMF 1.14.3
AAO 1.9.16 · lilToon 2.3.4 · VRCFury 1.1414.0
Companions: vpm-resolver 0.1.29 · gesture-manager 3.9.9 · gogoloco 1.8.6
      LLC 2.12.3 · av3manager 2.1.2 · performance tools 1.3.7
```

> The above is a **snapshot**; the authoritative table is [`_toolchain-benchmark.md`](../_toolchain-benchmark.md) (including a per-package "newer version in cache?" column),
> checked with `通用工具/vpm_baseline_check.py <工程目录>`. **For a new order copy the baseline table, not the previous order's `建档.md`** —
> intake records "what that order used at the time"; the baseline table records "why these versions".

#### Why it's frozen: the dependency graph itself leaves no room for choice

**Three packages simultaneously pin `com.vrchat.avatars` below 3.11** (read directly from the `dependencies` in each package's `locked` section):
`com.anatawa12.avatar-optimizer` `>=3.7.0 <3.11.0`, `dev.vrlabs.av3manager` `3.2 - 3.10`,
`vrchat.blackstartx.gesture-manager` `>=3.10.4 < 3.11.X`. Upgrading the SDK to 3.11 breaks **all three at once**,
and the SDK already sits at that 3.10.4 ceiling — "use the latest SDK" is currently an **empty option**, not a trade-off.

The rest that could be upgraded are only patch-level (as of the check date: MA 1.18.1→1.18.7, NDMF 1.14.3→1.14.8, AAO 1.9.16→1.9.18,
VRCFury 1.1414.0→1.1426.0, LLC 2.12.3→2.13.0). Trade-off:
- **Upgrade** → the benefit is "might fix bugs we haven't hit" (speculative); the cost is that the hard gate "land only one change at a time" breaks ([Step templates and hard gates](01-automation-and-parallelism/step-templates-and-hard-gates.md)) — toolchain and assets changing at the same time makes problems unattributable (certain, and it would happen in the middle of a paid order)
- **Don't upgrade** → the cost is getting "possible fixes" later — as of the check date only a speculative loss
- So **freeze by default, never upgrade while an order is in progress**; the cost asymmetry lies on the "upgrade midway" side

#### When to recheck: by event, not by calendar

① Upload rejected by the SDK (a hard signal of a game update; don't guess) ② A bug in some package **directly blocks the workflow** ③ A new asset pack declares a requirement for a higher version
④ **The gap after an order is delivered** (routine, lowest cost). Write the recheck conclusions back into the baseline table;
in the delivery notes include a sentence "the project's versions are locked; upgrading is not recommended unless problems arise" ([90](90-delivery-packaging.md)).

#### Three pitfalls when checking

- Prerelease version suffixes aren't uniform; besides `-alpha/-beta/-rc/-pre` there's also **`-pr6`**. To judge "is it a prerelease", always look for **the presence of a hyphen**;
  don't enumerate suffixes — miss one and a prerelease gets reported as the latest version (gesture-manager `3.9.9-pr6` was misreported this way)
- Under VCC `Repos/` the same source has multiple hashed historical snapshots; take the **union** — reading only the latest one misses versions
- 16 `Packages/` directories = the 14 named at intake + implicit dependencies `com.vrchat.base` and `jp.lilxyzw.avatar-utils`; don't treat those 2 as missing items

---

### Step 2 · Unpack and import assets　🤖

**Preconditions**
- [ ] Step 1 passed

**Execute**
1. Unpack `.unitypackage` directly with the unpack tool (**don't use Unity's import dialog, and don't drag folders**)
2. Tool behavior: skips duplicates with identical content; reports conflicts with different content (**keeps the old one and lets a human decide**);
   excludes `.exe/.bat/.cmd/.ps1`

**Post-criteria**

| Expected | How to read |
|---|---|
| Number of conflicts == 0, or each has a handling record | Unpack report |
| Remaining unopened `.zip`/`.unitypackage` == 0 | Run `find` over the asset directory |

**STOP**
- Same-path conflicts with different content appear → hand to a human to decide; don't pick one yourself and overwrite

> **Why not drag folders**: when the `.meta` doesn't come along, Unity **regenerates GUIDs** for the folder.
> Plugins that locate their own directory via hard-coded `AssetDatabase.GUIDToAssetPath("<guid>")` then fail to resolve
> → `Instantiate(null)` → a modal dialog interrupts the build.
> The symptom is extremely misleading: the Console doesn't report missing resources, and the error is in the plugin's own code — **it looks like a plugin bug**.

> ⚠ **Several sub-packages of the same product share folder/material GUIDs**; when importing the second package Unity moves the first package's files away
> and silently drops same-path assets. **Imports must be serial**, never concurrent.

---

### Step 3 · Five completeness checks (read-only, a few minutes)　🤖

**Preconditions**
- [ ] Step 2 passed

**Execute**

| What to check | How to check |
|---|---|
| Any unopened packages | `find 素材 -name '*.zip' -o -name '*.unitypackage'` |
| Any missing common/material packages | File names containing `material` / `shader` / `common` / `core` / `dlc` |
| Are materials variants missing their parent | Count lines in material files |
| **One GUID, multiple paths (collision)** | `python 开发工具/通用工具/guid_uniqueness_audit.py <工程>` |
| Broken GUID links | Same as above plus `--refs`. The index **must include `Assets/` + `Packages/` + `Library/PackageCache/`** |

**Post-criteria**

| Expected | How to read |
|---|---|
| Unopened packages == 0 | First row of the table above |
| A complete lilToon material is **700+ lines**; ones with only a few dozen lines are **variants with a missing parent** | Line count |
| **One GUID multiple paths == 0** (hard criterion; non-zero must be fixed) | Audit tool "criterion 1" |
| Broken GUIDs == 0 after excluding false positives | Audit tool "criterion 2" + the screening rules below |

> → [GUID collisions and fixes](20-asset-inventory-and-import/guid-collisions-and-fixes.md) — two measured cases: a vendor moving files in a version bump while keeping GUIDs, and an accessory pack bundling a fallback copy of lilToon; the boundary of shared assets is the "vendor", not the "product"; the fix requires retrieving the original GUID from the source package.

**False-positive screening** (these aren't defects; don't fix them)
- Ones landing in lilToon optional slots: `_OutlineTex` `_BumpMap` `_EmissionBlendMask`
  `_ReflectionColorTex` `_GlitterColorTex` — **inert when the corresponding `_UseXxx` toggle is off**
- `0000000000000000f000000000000000` is a Unity built-in resource
- ⚠ lilToon's feature toggles are **`_UseXxx`, not `_XxxBlend`** —
  with `_MatCapBlend: 1` but `_UseMatCap: 0`, that layer doesn't take effect at all

---

### Step 4 · Build the asset application table　🤖

**Preconditions**
- [ ] Step 3 passed

**Execute**
1. Run the application-table generator to produce `_素材应用表.md`
2. The first six columns are machine-generated; **the last column "purpose / reason not used" is handwritten**, and re-runs backfill it by product number without wiping it

**Post-criteria**

| Expected | How to read |
|---|---|
| Number of rows in the table == number of products in the asset packs | Compare the two numbers |
| **The criterion passes the reverse check first**: definitely-used > 0, definitely-unused == 0 | See section 2 of [Implementation pitfalls](20-asset-inventory-and-import/implementation-pitfalls.md) |

**STOP**
- The reverse check doesn't match at either end → the criterion is broken; **fix the criterion before producing numbers**, and don't make decisions from this table

- Generation command: `python 开发工具/通用工具/pack_usage.py <工程目录> <素材包目录>`.
- Distinguish **"not imported" from "imported but 0 references"**: "not imported" may mean the package itself lacks files (some Booth directories have only product images, not the actual item); **only "imported but 0 references" is truly missed usage**.

### "Not used" must state a reason, and only three kinds qualify

1. Doesn't support this base avatar (**list which base avatar versions the package contains**)
2. Functionally overlaps with something already installed (**name which one**)
3. The client explicitly doesn't want it

If you can't write a reason, it was missed.

> Why this table is needed: asset packs routinely have twenty-plus products, and halfway through you simply can't remember which went on, which didn't,
> and which were **deliberately** left off. Counting only before delivery leads to "the client bought it but it was never used at all" —
> measured: we once missed an eye pack with 203 textures, while the questionnaire stated eye color requirements in black and white.

---

### Step 5 · Dependency reproducibility self-check　🤖

**Preconditions**
- [ ] Step 4 passed

**Execute**
1. Scan `Packages/manifest.json` for `file:` and `git#` dependencies

**Post-criteria**

| Expected | How to read |
|---|---|
| Hits for `file:` and `git#<分支>` == 0 | grep results |

**STOP**
- Any hits → convert to VPM version numbers before continuing, otherwise it won't open after archiving.
  For finding the version actually used back then, see section 4 of [Implementation pitfalls](20-asset-inventory-and-import/implementation-pitfalls.md)

**Criteria for package provenance, licensing and orphan packages** (the three notations `file:`/`git#master`/`.git?path=`, three lines of package notes, paid original packages and upgrades, orphan package registration) → [Implementation pitfalls · 3.5](20-asset-inventory-and-import/implementation-pitfalls.md) (grep `许可` (licensing) or `孤儿包` (orphan package) to jump straight there).
