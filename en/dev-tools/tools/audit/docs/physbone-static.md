> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/physbone-static.md)

# PhysBone static inventory pb_static.py and U7 <!-- nav -->

> Former name: T-30 (originally `审查/README_T30.md`) full text. § numbers follow the original text; for cross-page § references see the [documentation index](../README.md). <!-- nav -->

# T-30 · PhysBone static inventory and U7 `pb_static.py`

> Goal: turn "does this outfit/skirt have PhysBones, which bones make up the PhysBone chain, which joint the colliders cover,
> and should rigid vs settle differences be attributed to PhysBones" from **eyeball guessing** into **offline data**.
> Attached to: T-27 `AuditPoseDriver.cs` (settle convergence only consumes this output's `chains[]`),
> T-29 `pose_plan.py` (`both` is only given to pieces with `has_pb=true`), T-14 `verdict.py` (U7 general rule).
> This tool is a **pure Python 3 + PyYAML** script: it doesn't start Unity, doesn't enter Play, doesn't touch the project; it only reads inputs and only writes `--out`.
> Reuses `perception/unity_yaml.py`; design basis `04 §T-30`, `03 §8.3`.

---

## 1. Deliverables

| File | Role |
|---|---|
| `开发工具/通用工具/审查/perception/pb_static.py` | This tool (the only code file) |
| `README_T30.md` | This page |
| `<工程>/_感知/out/pb.json` | Static inventory (default output) |
| `<工程>/_感知/out/pb_runtime_diff.json` | Diff against the T-27 runtime table (only written with `--diff`) |

## 2. Usage

```bash
PB=开发工具/通用工具/审查/perception/pb_static.py
# ① Static inventory (Project A)
python3 $PB --project 工程A
#    Reads <工程>/_感知/decl.json (if present, provides parts[].pb), writes <工程>/_感知/out/pb.json

# ② Compare against the T-27 runtime PB table (M6)
python3 $PB --project <工程> --diff <run>/pb_runtime.json
#    → <工程>/_感知/out/pb_runtime_diff.json (added / removed / changed)

# ③ Self-verification (Project A; reads the project only, writes no output)
python3 $PB --selftest
```

`--scene/--decl/--out` can override the defaults; `--diff` accepts three runtime table shapes:
`[ {...} ]`, `{"physbones":[...]}`, `{"by_key":{...}}`.

## 3. Parsing basis (points aligned with Unity)

- **Active avatar root**: a `PrefabInstance` at the scene root whose source prefab has an avatar descriptor and whose `m_IsActive` override is not 0.
  The Project A scene has two instances of the same base-avatar prefab;
  `Kaguya-工程A` (the base) has root GO `m_IsActive:0` and is skipped,
  so only `Kaguya-工程A-FaceTracking[...]` is counted.
- **Includes `m_AddedComponents`**: `VRCPhysBone` / `VRCPhysBoneCollider` are always identified by script GUID
  `2a2c05204084d904aa4945ccff20d8e5` + class fileID (PB `1661641543`,
  Collider `-1631200402`). **You can't rely on `m_EditorClassIdentifier`**:
  for components that land via `m_AddedComponents` that field is empty (in Project A only 36 of 164 PBs have the identifier).
- **Avatar root subtree**: the avatar prefab itself + its nested prefabs (`tail_mofu9`/`ear`/`kaguya_cloth`…)
  + child prefab instances hung under the avatar instance in the scene (hair/accessories/clothing/function parts), **including inactive child objects**
  — same basis as `GetComponentsInChildren(true)` in `PhysBoneAudit.cs`.
- Recorded for each component: root bone, chain (`rootTransform` + hierarchy descendants), `colliders` references,
  `immobile/immobileType`, `isAnimated`, `resetWhenDisabled`, `allowCollision`, `m_Enabled`.

## 4. Project A count check (important)

Current source scene (active avatar root): **PhysBone 164 / VRCPhysBoneCollider 21**.
The **158 at `_工程状态.md:197` is a 2026-09-01 snapshot**; the comment in `PhysBoneAudit.cs` records
**164** in the current source scene and 229 after baking (now `Assets/_Work/动骨审计.md` records 227).
`--selftest` asserts 164.

> `grep -c "VRCPhysBone"` on Project A only gets ≈36, because components landed via `m_AddedComponents`
> have an empty `m_EditorClassIdentifier`. To check component counts use the GUID basis;
> `checks.grep_like` in `pb.json` gives both numbers.

## 5. Output `pb.json` structure (v1)

```jsonc
{
  "schema": "pb.json/1", "scene": "...", "avatar_prefab": "...", "decl": "...",
  "counts": {"physbones": 164, "colliders": 21, "parts_with_pb": N, "u7": M},
  "checks": {"physbone_script_guid": "...", "distinct_pb_docs": 164,
             "name_resolved": 46, "name_placeholder": 118, "grep_like": {...}},
  "physbones": [{
      "key": "<文件>#<fileID>@<实例>", "file": "...", "file_id": 0, "instance": "...",
      "root_path": "...", "chain": ["..."], "colliders": ["<collider key>"],
      "colliders_on_regions": ["LeftUpperLeg"], "region": "LeftUpperLeg",
      "immobile": 0.4, "immobile_type": 0, "is_animated": 1,
      "reset_when_disabled": 0, "enabled": true, "name_source": "file|placeholder"
  }],
  "colliders": [{ "key": "...", "shape_type": 0, "radius": 0.08, "height": 2.0,
                  "region": null, ... }],
  "parts": {"<partId>": {"has_pb": true, "chains": ["..."],
                          "colliders_on_regions": [...], "covers": [...], "objects": [...]}},
  "u7": [{"rule": "pb_no_collider", "part": "...", "region": "LeftUpperLeg",
          "pb": "<PB 根骨路径>", "missing": "LeftUpperLeg"}],
  "warnings": ["..."]
}
```

- **`chains[]` is exactly the "PB chains the tested piece maps to" that T-27 needs**; chains are expanded along the local tree `m_Children`
  up to 64 nodes (including branches; `multiChildType` is not distinguished — better to monitor too much).
- `parts[].pb`: root bone → piece uses **parent-chain/path mapping** (`objects[].path` matched against root bone path
  segment prefixes/suffixes); only draft fragments without `objects` fall back to region matching via `covers`.

## 6. U7 (attribution hint, not a standalone violation)

If a piece covering region R carries a PB, but its colliders don't land on R's joint chain (`REGION_CHAIN`, e.g.
skirt → `LeftUpperLeg`/`LeftLowerLeg`/`Hips`, sleeve → `LeftUpperArm`/`LeftLowerArm`/`LeftShoulder`),
report `pb_no_collider(R)`, each entry carrying the PB path and the missing region name. It explains
the `pb_dependent` of `rigid ✗ / settle ✓` (the colliders are catching it), and does not itself enter the gate.

## 7. Known offline limitations (written into `warnings`, filled in by T-27's runtime table)

Unity stores FBX node names only in the **binary FBX**; prefab/scene YAML only has
`stripped` references to these nodes, and `internalIDToNameTable` in `.fbx.meta` is empty. Therefore
**bone nodes inside a prefab that come from an FBX cannot get names or full hierarchy**; this tool uses a `#<fileID>` placeholder
(`name_source:"placeholder"`), chains may degrade to `[自身]` (self only), and colliders' `region` is `null`.
Pure non-FBX prefabs (such as Project A's `Outfit_RePoppin`) get real names and full chains
(Project A: 46/164 named). At runtime T-27 exports a real-name table, and `--diff` aligns it with this table (M6).

## 8. Acceptance

```bash
python3 开发工具/通用工具/审查/perception/pb_static.py --selftest
```

Self-verification covers: ① active-root count = 164 (matching the `PhysBoneAudit.cs` comment), with the grep-basis comparison;
② dynamically constructs two pieces, `工程A.tail` (tail) and `工程A.skirt` (`kaguya_cloth` skirt),
both `has_pb=true` with non-empty `chains[]`; ③ U7 (a missing `LeftUpperLeg` collider must be reported,
with PB path and region name; not reported when covered); ④ `--diff` reports additions/removals/changes against a hand-edited runtime table.
