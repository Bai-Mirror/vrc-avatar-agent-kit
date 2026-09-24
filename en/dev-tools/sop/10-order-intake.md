> 🌐 English translation · [中文原文](../../../开发工具/SOP/10_接单建档.md)

# 10 · Order intake　🤖

**Purpose**: turn the order context into an actionable constraint table, and work out the boundaries of this order.
**Output**: `建档.md`
**Next gate**: 15 Set direction at kickoff (👤)

## Steps

| # | Action | Command / location | Criterion |
|---|---|---|---|
| 1 | Read the three txt files | `COMM-*_素材/客户需求/{订单信息,需求说明,需求问卷}.txt` | All three read; note down whichever is missing |
| 2 | Copy out the hard constraints | See "Constraint table" below | Things to avoid are copied as carefully as positive requirements |
| 3 | Inventory the assets | `ls 素材/{素体,服装,发型,配饰,贴图,功能插件}/*` | Number of list entries = number of product directories |
| 4 | Pick a version per product | See "Picking packages" below | Every product has a decided zip to install, with the reason written down |
| 4b | Open packages to check compatibility | See "Opening packages to check compatibility" below | Each item's verdict ∈ {supported / not supported / pending bone comparison}, recorded in `客户需求/素材兼容性核查.txt` |
| 5 | Check the base avatar lineage | See "Base avatar lineage" below | Find ≥1 historical project to use as reference |
| 6 | Count avatar roots | Does the request include a face-tracking version / Quest version? | One blueprintId per root; changes must be made once for each |

## Constraint table (copy verbatim into `建档.md`)

```
Order no. / client / base avatar / quote / schedule / duration
Add-ons   ← determine the workload boundary; miss one and the work is wasted
Overall palette / contrast colors / eyes / hair / outfit / style preferences
Things to avoid   ← negative requirements are the easiest to gradually violate during the work; copy them in the most prominent place
Structural requirements ← e.g. "split the outfit into parts"; this is a menu architecture issue, not a recoloring issue — the earlier you know, the less trouble
```

## Ask about face-tracking hardware preset and target platform separately (trigger: intake questionnaire stage)

**"Do you want face tracking" and "which platform" are two questions; they can't be merged into "a Quest version with face tracking".** A scene can contain multiple avatar roots at once, and one is chosen at upload:

| Question | What to ask | What happens if you don't ask this way |
|---|---|---|
| Face-tracking hardware preset | Which device does the user actually use? Vendor packages often put a **platform name** like `[HD(Quest,Pico)+HD(Pico)]` into the root name; it refers to the **hardware preset**, not the Quest platform | Guessing from the name and installing the wrong preset |
| Target platform | How many roots for each of PC / Quest / iOS | Doing too few or too many, or missing the Quest conversion |

- **Criterion**: at intake, record "device model" and "platform" on separate lines; the face-tracking preset must match the client's device **word for word** (historically measured: Project C's scene had two face-tracking roots, and `HD(...)` must match the client's device; F §7 unverified).
- **If you can't meet it**: if the device is unclear, write "to be confirmed"; don't infer the device from the platform name.

## Constraint table: write in the parameter and PhysBone headroom (same stage)

Besides visual and functional items, the constraint table **must add two lines of resource headroom**, otherwise you discover you're over the limit only at 60/80:

- **Parameter headroom**: `≤256 bit` (Int/Float 8 each, Bool 1). When the client wants many toggles, first estimate "how much still needs to be reserved for face tracking/VRCFury", and write it into the constraints.
- **PhysBone headroom**: total `≤256`. Historically a project was measured sitting at 255/256 (zero headroom); attaching one more would exceed it — face tracking, tails and accessories all take slots.
- **Trade-off**: set the headroom too small and the client adding features goes over the limit and things must be cut; too large wastes parameter bits. **The criterion is that both numbers are written into `建档.md`, and reconciled against measured values at stage 60** (see [60 Menus and animator layers](60-menu-and-animation-layers.md)).

## Picking packages (this step is the easiest to get wrong)

**Vendors ship separate packages per base avatar; you must pick the one for this base avatar.** You can't take the "latest" by sorting numerically.

| Symptom | Example (measured on the 2026-09-01 Kaguya order) |
|---|---|
| Picked another base avatar's | Vendor packages are often named “base avatar name + version number”; another avatar's package has a higher version number → taking the latest by sort picks the wrong one |
| Picked a non-package file | Some plugin packs include an installation video, which sorts last by file name |
| Missed the common package | The hair package has only FBX+prefab (2 files); the materials are in `Materials_*.zip`; miss it and the materials are missing |

**How to do it**:
1. Locate the product directory by the **Booth product ID (`-NNNNNNN` suffix, pure ASCII)** — directory names contain emoji and full-width brackets, so path matching is unreliable
2. In `files/`, filter file names containing this base avatar's name
3. **Scan again for common packages**: file names containing `material` / `shader` / `common` / `core` / `dlc`
4. If there's no version for this base avatar, **don't judge it incompatible outright** → go to the bone comparison in [50 Assembly](50-outfit-and-hair-assembly.md)

## Opening packages to check compatibility (do before quoting; read-only; a few minutes per item)

**A client asset pack ≠ everything supports the target base avatar.** Measured: in a client library of 92 items, 1 item didn't support this base avatar at all and 1 had only other base avatars' versions;
we had assumed the client's asset library was picked for this base avatar, and nearly wrote unusable items into the plan. The quote and schedule were computed as if "everything works";
finding out at kickoff that something can't be installed means wasted work.

### The criterion is the prefab / fbx paths inside the package, not the file name

A product name saying "22アバター対応" doesn't tell you which 22. List the `pathname` entries in the unitypackage
(it's a tar.gz; each asset directory has a `pathname` file; see section 4 of the [02 subpage](02-environment-and-manual-intervention/project-setup-and-first-compile.md)):

```python
with gzip.open(p) as g, tarfile.open(fileobj=io.BytesIO(g.read())) as t:
    paths = [t.extractfile(m).read().decode().split("\n")[0]
             for m in t.getmembers() if m.name.endswith("/pathname")]
prefabs = [x for x in paths if x.lower().endswith((".prefab", ".fbx"))]
```

Products shipped per base avatar will have a series of `Outfit_<素体名>.prefab`, showing at a glance which ones are supported. Nested archives need digging two levels down
(`X.zip` → `X_12_Avatars.zip` → `.unitypackage`).

Three tiers of judgment — **do the cheap one first, go further down only if it can't be settled**:

| Tier | What to look at | What it can establish | What it can't establish |
|---|---|---|---|
| File name | Base avatar name in the zip / directory name | Which zip to pick (previous section) | Compatibility — shared-project avatars are released under the project name, and same-name-different-source also exists |
| **Package pathname** | prefab / fbx names | Which base avatars a per-avatar product supports | Generic packages (one prefab for all base avatars) have no base avatar in the name |
| Bone comparison | Set of bone names in the FBX | The final criterion ([50](50-outfit-and-hair-assembly.md)) | Highest cost; reserve for what the first two tiers can't settle |

- **Don't use regex matching on base avatar names for automatic verdicts**: `sio` in `Version` would pull Sio in. Automatic scans are only for flagging suspicious items; open each package and review manually
- The costs are asymmetric: wrongly judging "not supported" costs one library lookup / one bone comparison (minutes); wrongly judging "supported" costs quoting on the wrong scope + reworking halfway through installation.
  When unsure, write **"pending bone comparison"**; don't guess either way

### Same-spec base avatars: one fbx with multiple prefabs ⇒ the mesh is shared, textures are not

If the package has only one `X.fbx` yet provides `X_<素体A>.prefab` and `X_<素体B>.prefab` — the vendor ships the same clothing mesh to two base avatars,
meaning their body shapes fit equally, and **mesh items such as outfits / accessories (possibly including hairstyles) are interchangeable**.

**But this doesn't extend to textures.** Face / body textures depend on UV; if the two base avatars are original models by different authors, and the face-tracking author also released separate adaptation packages for each
(separate face tracking ⇒ different blendshape sets and UVs), textures are not interchangeable. Criterion: **has the vendor ever released one texture labeled with both base avatar names**;
if you only see separate texture packages for each, treat them as not interchangeable.

Write the conclusion into `客户需求/素材兼容性核查.txt`; for "not supported" items, together with **which base avatar versions the package actually contains**, fill them back into the "not used" column of the asset application table ([20](20-asset-inventory-and-import.md)).

## Base avatar lineage

**Because shared base avatar projects exist, "this base avatar's name isn't in the file name" is no criterion for compatibility at all.**
First find out which project / which author this base avatar belongs to, then find historical projects from the same project as reference.

Known:
- **Kipfel** = the まめふれんず (Mamefriends) project → outfit authors release under the project name
- **Kaguya (輝夜)** and **Rurune** share an author and a lineage (the vendor directory is `IKUSIA` for both)
  → reference projects `H5-Rurune`, `工程E` (Project E)

## What to do about missing items

**First look in this machine's asset library `<asset-library>/`; don't make the user re-download.**
```bash
ls <素材库> | grep -iE "<关键词>"
ls <素材库>/*<商品号>/files     # directory names contain NFD and emoji; wildcard by product number, don't type the full name
```
It's a full library of Booth products, structured the same as client asset packs (`.booth-meta.json` + `files/` + `images/`).
**The library is often more complete than the client asset pack** (measured on the Kaguya order: the library also had the face-tracking plugin and animated eye textures, which the asset pack didn't).

## What tripped us on this order (kept from v1.1)

The client provided 6 asset packs, and only at wrap-up did we discover **only 1 was actually wired up**.
→ List them at intake, and **tick them off one by one before delivery** ([90](90-delivery-packaging.md)).
