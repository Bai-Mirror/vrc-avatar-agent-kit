> 🌐 English translation · [中文原文](../../../../开发工具/SOP/20_素材清点导入/实施坑.md)

> ← [20 · Asset inventory and import](../20-asset-inventory-and-import.md)

# Implementation pitfalls in asset inventory

The problem this page solves: **statistics like inventory/usage rates can produce numbers that all look reasonable and raise no errors, yet may be entirely wrong.**
Three criterion pitfalls we've already hit, plus the reverse check you must do before producing numbers.

---

## 1. Three criterion pitfalls we've already hit

| Pitfall | Symptom | Correct approach |
|---|---|---|
| Guessing the product mapping from **directory names** | All wrong. "揺れるハートのリング" unpacked as `HINO shop`, "Makeup & Eye Texture" as `cumulus` | The unitypackage carries the original GUIDs; intersect them with the project's `.meta` |
| Using the **extension** to decide whether an entry is a file | `.prefab` (6 characters) treated as a directory and missed, while prefabs are exactly the main things scenes reference → the "referenced" column is falsely 0 across the board | A directory = it is the parent path of another entry. In a unitypackage directories and files are listed together, so this criterion is deterministic |
| Reachability starting from `Assets/**/*.unity` | Vendor demo scenes (plugin-bundled Generator / Sample Scene and the like) mark every asset in the whole package as "used" | **Start only from your own working scene** |

---

## 2. Statistical criteria: falsify before producing numbers

The three pitfalls above have one thing in common: **the numbers produced all look reasonable, and not one raises an error.**

For any "coverage / usage / completeness" statistic, before producing numbers you must first do a **reverse check with a known answer**:

1. Pick an asset that is **definitely used** → its number must be **> 0**
   > Measured counterexample: a plugin clearly attached to the avatar showed 0. This reverse check should have been done proactively in the first round,
   > not discovered by chance after the table was filled in.
2. Pick an asset that is **definitely not used** → its number must be **== 0**
   > Measured counterexample: an accessory just imported and not installed on the avatar showed 56.
3. Only when both ends match can the table be used for decisions.

> Not limited to asset statistics. **Broken-link scans, parameter budgets, performance reports — any "counted conclusion" applies.**
> The cost is two minutes; the cost of skipping it is redoing the whole round.

---

## 3. Keep tooling and verification separate

Upgrading a one-off script into a general tool while still hunting errors doubles the time.

**Correct order**: first get the answer by the crudest means and hand it in; **tooling is the next task**.
When the two are tangled, every criterion fix requires a full re-run, and it also tends to break the patch scripts along the way.

> When writing patch scripts, don't pass content containing `\n` or backticks through a shell heredoc —
> backticks get treated as command substitution, and `\n` becomes a real newline that breaks C#/Python strings.
> Write to a file on disk and then execute.
> Also, when an assertion fails the whole file isn't written, and **earlier successful edits get rolled back with it**,
> which is easy to misjudge as "nothing changed".

---

## 3.5 Package provenance, licensing and orphan packages (trigger: after import, before inventorying assets)

**Purpose**: be clear about where a package **came from, whether the original is needed, and whether an upgrade will wipe out generated files**; when paid items are involved, make licensing decisions early rather than leaving them to delivery.

### Three dependency notations, none reproducible

```bash
grep -nE '"file:|git#|\.git\?path=' Packages/manifest.json
```

| Notation | Meaning | Why it must be checked |
|---|---|---|
| `file:` | Points to a directory outside the workspace | Won't open after changing machines/moving directories |
| `git#master` | References a branch directly | Only works because `Library/PackageCache/` holds a copy from back then; delete Library and it changes |
| `.git?path=…#master` | References a git subdirectory | Same as above, and more hidden (a historical check missed it once — it was actually 7 projects, not 5) |

**If you can't meet it**: on a hit, convert to a VPM version number before continuing (see section 4); anything that can't be converted is named in the import report and handled separately at archiving.

### Three lines of package notes

For each package record three lines: **version / download date / upgrade notes**. The library-lookup rule for permanently missing items (look in this machine's `<asset-library>/` first; don't make the user re-download) is in [10 · What to do about missing items](../10-order-intake.md); only a pointer is kept here, not repeated.

### Before upgrading a vendor package: register generated files first

1. **Move** the current package away (or first register `#GENERATED`/`Backup/`), because the upgrade overwrites same-named paths.
2. Avatar tools generate per-avatar directory structures that vary (historically measured two namings, `#GENERATED/` and `Backup/`, F §5) — each needs a line in the application table, otherwise after the upgrade you can't tell generated files from originals.
3. **Upgrading a paid original package is a licensing decision, not something to do in passing**: vendor originals (including paid Booth zips and Patreon shaders) **don't go into the delivery** (K #3/#4; the SOP "licensing" entry was checked empty on 2026-09-18 and this is the first batch) — both attaching and upgrading require the user's approval, and must be written into the delivery notes.

### Orphan package registration (only in `Packages/`, not in `manifest.json`)

**Definition**: the package directory is under `Packages/`, but `manifest.json` has no entry for it — it doesn't take part in version resolution, and **will disappear after changing machines / `vrc-get resolve`**.

- **Criterion**: number of directories under `Packages/` vs. number of entries in `manifest.json` + `locked`; register each mismatch individually. Historically measured: F §2's body lists 6 kinds while its conclusion table says 5, and **7 projects have dependency problems** (verified in this document, not 5).
- **If you can't meet it**: either write the orphan package into `dependencies` in `manifest.json`, or move it into `Assets/` and accept it's not package-managed; **don't leave it alone** — it compiles today purely because the `Library/` cache is still there.

---

## 4. Dependency reproducibility (must check before archiving)

```bash
grep -E '"(file:|https?://)' Packages/manifest.json
```

On a hit, convert to a VPM version number — `file:` local paths and `git#master` branch dependencies are **both non-reproducible**:

- `file:` points to a directory outside the workspace; changing machines / directories means it won't open (Unity returns exit code 1 outright)
- `git#master` opens only because `Library/PackageCache/` holds a copy cloned back then; delete Library and it changes

**Find the version actually used back then**: read `Library/PackageManager/ProjectCache` (text).

⚠ In that file the **`version:` field comes before `name:`**; searching forward picks up the adjacent entry's value.

`source:` enum: `1=Registry 2=Builtin 3=Embedded 4=Local 5=LocalTarball 6=Git`

## 5. A VPM package zip unpacked in the wrong place: all files present, all references correct, compiles fine, but **version defines silently mismatch**

Feature plugins from vendors are often **VPM package `.zip`s** (not `.unitypackage`),
containing a `package.json`. Such a package **must land in `Packages/`**; put in `Assets/` it's just a pile of source code —
Unity's package manager doesn't recognize it, so none of the `versionDefines` match.

> Evidence (2026-09-09 Project C): the face-tracking framework's VPM release `<framework>-v<version>.zip`
> was unpacked to `Assets/Packages/<framework-package-name>/`.
> As a result, in the asmdef of the installer plugin in the face-tracking plugin's install directory,
> `versionDefines: [{ name: "<framework-package-name>", define: "<framework-define>" }]`
> never held → the plugin compiled into the `#else` branch → the window showed only
> **"<framework name> is not detected. Please import it."**
> — while the framework was actually on disk, all 472 assets present.

**Why it's hard to find**: this pitfall **raises no error**. The asmdef `references` (by GUID) still resolve,
compilation has zero errors, and the console is clean. The only manifestation is a human-readable "not detected" message,
which reads like "you didn't install it", so the first reaction is to install it — heading in the wrong direction.

⚠ The converse also holds: **the `name` in `versionDefines` only recognizes packages registered with the package manager**
(embedded packages under `Packages/`, VPM packages and Unity registry packages all count), not any directory in `Assets/`.
So the criterion is "is it in Package Manager", not "are the files there".

#### Criteria (three, each given as a positive/negative pair)
1. What counts is whether the define is in the **compiled output**, not `.csproj` —
   `.csproj` is only regenerated when **scripts change**; it doesn't change when the package location changes, and gives a stale false answer.
   Check `Library/ScriptAssemblies/<插件>.dll` and search the binary for:
   - a type name unique to the `#if` branch (e.g. the base class `FaceTrackingInstaller`) → **must hit**
   - a symbol unique to the `#else` branch (e.g. the field `addonConfig` that only that branch has) → **must not hit**
   Checking only the former gets fooled by "generic symbols referenced in both branches" (e.g. `EditorWindow` is on both sides).
2. **Moving must not break references**: before moving, save "the set of GUIDs that consumers point to inside the package" as a baseline,
   and after moving compare that the sets are **exactly identical**. The criterion isn't "the files are still there" — files there but GUIDs changed means
   references silently become null, with no error at edit time. Moving together with the `.meta` keeps them unchanged.
3. After moving the top-level package directory into `Packages/`, **delete its own `.meta`** (the package root doesn't need a meta).

#### How to do it and the cost
Close Unity before moving. Embedded packages under `Packages/` are **only scanned at startup**;
move with Unity open and not restart, and the define won't take effect — leading to the wrong conclusion "moving didn't help".
The cost is a full reimport (this time 472 assets, about 3 minutes), in exchange for clean GUIDs and package registration.

**Don't settle for manually adding Scripting Define Symbols**: that **decouples** the define from the package's existence;
once the package is removed or changes version, the define is still there, and the plugin fails to compile or worse — compiles but behaves wrongly.

## Supplement

- **When remedying, write to disk by original GUID**: `unpack_unitypackage.py --only-new-guids` unpacks only GUIDs not yet in the project, without rewriting common assets, avoiding two paths for the same GUID.
- **0 references ≠ missed usage** (2026-09-19 acceptance BP): before writing "imported but unused", first grep the plan documents already in the project (`_配色方案.md`, `_素材应用表.md`) — Project B's highlight dye pack Ↄiao2 was explicitly not used per the color plan.
- **When checking "is X in the assets", check the original zip listing too** (`unzip -l`): unpacked directories may be incomplete, and chat screenshots/requirement sheets often never made it into the asset pack at all (2026-09-19 checking face-tracking devices for Project C).
