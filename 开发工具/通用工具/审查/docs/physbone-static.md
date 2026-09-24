# PhysBone 静态清单 pb_static.py 与 U7 <!-- nav -->

> 旧称：T-30（原 `审查/README_T30.md`） 全文。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->

# T-30 · PhysBone 静态清单与 U7 `pb_static.py`

> 目标：把「这套衣服/裙子上有没有动骨、动骨链是哪几根骨、碰撞体盖在哪个关节、
> rigid 与 settle 差异该不该归因到动骨」从**目视猜**变成**离线数据**。
> 依附：T-27 `AuditPoseDriver.cs`（settle 收敛只吃本产物的 `chains[]`）、
> T-29 `pose_plan.py`（`both` 只给 `has_pb=true` 的件）、T-14 `verdict.py`（U7 通用规则）。
> 本工具是**纯 Python 3 + PyYAML** 脚本：不启动 Unity、不进 Play、不碰工程；只读输入、只写 `--out`。
> 复用 `perception/unity_yaml.py`；设计依据 `04 §T-30`、`03 §8.3`。

---

## 1. 交付物

| 文件 | 作用 |
|---|---|
| `开发工具/通用工具/审查/perception/pb_static.py` | 本工具（唯一代码文件） |
| `README_T30.md` | 本页 |
| `<工程>/_感知/out/pb.json` | 静态清单（默认输出） |
| `<工程>/_感知/out/pb_runtime_diff.json` | 与 T-27 运行时表的差异（仅 `--diff` 时写） |

## 2. 用法

```bash
PB=开发工具/通用工具/审查/perception/pb_static.py
# ① 静态清单（工程A）
python3 $PB --project 工程A
#    读 <工程>/_感知/decl.json（有则给 parts[].pb），写 <工程>/_感知/out/pb.json

# ② 与 T-27 运行时 PB 表比对（M6）
python3 $PB --project <工程> --diff <run>/pb_runtime.json
#    → <工程>/_感知/out/pb_runtime_diff.json（added / removed / changed）

# ③ 自验（工程A；只读工程，不写产物）
python3 $PB --selftest
```

`--scene/--decl/--out` 可覆盖默认；`--diff` 接受三种运行时表形态：
`[ {...} ]`、`{"physbones":[...]}`、`{"by_key":{...}}`。

## 3. 解析口径（与 Unity 对齐的点）

- **活跃头像根**：场景根上源 prefab 带头像描述符、且 `m_IsActive` 覆盖不为 0 的
  `PrefabInstance`。工程A 场景有两个同一素体 prefab 的实例，
  `Kaguya-工程A`（基座）根 GO `m_IsActive:0` 被跳过，
  只算 `Kaguya-工程A-FaceTracking[...]`。
- **含 `m_AddedComponents`**：`VRCPhysBone` / `VRCPhysBoneCollider` 一律按脚本 GUID
  `2a2c05204084d904aa4945ccff20d8e5` + 类 fileID（PB `1661641543`、
  Collider `-1631200402`）识别。**不能靠 `m_EditorClassIdentifier`**：
  经 `m_AddedComponents` 落的组件该字段为空（工程A 里 164 个 PB 只有 36 个带标识符）。
- **头像根子树**：头像 prefab 自身 + 其嵌套 prefab（`tail_mofu9`/`ear`/`kaguya_cloth`…）
  + 场景里挂在头像实例下的子 prefab 实例（头发/配饰/衣服/功能件），**含 inactive 子物体**
  ——与 `PhysBoneAudit.cs` 的 `GetComponentsInChildren(true)` 同口径。
- 每个组件记：根骨、链（`rootTransform` + 层级后代）、`colliders` 引用、
  `immobile/immobileType`、`isAnimated`、`resetWhenDisabled`、`allowCollision`、`m_Enabled`。

## 4. 工程A 计数核对（重要）

当前源场景（活跃头像根）**PhysBone 164 / VRCPhysBoneCollider 21**。
`_工程状态.md:197` 的 **158 是 2026-09-01 的快照**；`PhysBoneAudit.cs` 注释记
当前源场景 **164**、烘焙后 229（现 `Assets/_Work/动骨审计.md` 记 227）。
`--selftest` 以 164 为断言。

> `grep -c "VRCPhysBone"` 在 工程A 上只得到 ≈36，因为 `m_AddedComponents`
> 落的组件 `m_EditorClassIdentifier` 为空。核对组件数请用 GUID 口径；
> `pb.json` 的 `checks.grep_like` 同时给出两个数。

## 5. 输出 `pb.json` 结构（v1）

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

- **`chains[]` 就是 T-27 要的「被测件映射到的 PB 链」**；链按本地树 `m_Children`
  展开到 64 节点（含分叉；`multiChildType` 未细分，宁可多监控）。
- `parts[].pb`：根骨→部位用**父链/路径映射**（`objects[].path` 与根骨路径
  段前缀/后缀匹配）；没有 `objects` 的草案片段才退回 `covers` 的 region 匹配。

## 6. U7（归因线索，不单独判违例）

覆盖区域 R 的件若挂 PB，而其碰撞体没落在 R 关节链上（`REGION_CHAIN`，如
裙→`LeftUpperLeg`/`LeftLowerLeg`/`Hips`，袖→`LeftUpperArm`/`LeftLowerArm`/`LeftShoulder`），
报 `pb_no_collider(R)`，每条带 PB 路径与缺的 region 名。它解释
`rigid ✗ / settle ✓` 的 `pb_dependent`（碰撞体在兜），本身不进卡口。

## 7. 已知离线限制（写进 `warnings`，由 T-27 的运行时表补齐）

Unity 只把 FBX 节点名存在**二进制 FBX** 里；prefab/场景 YAML 对这些节点只有
`stripped` 引用，`.fbx.meta` 的 `internalIDToNameTable` 为空。于是
**prefab 内出自 FBX 的骨节点拿不到名字与完整层级**，本工具用 `#<fileID>` 占位
（`name_source:"placeholder"`），链可能退化为 `[自身]`，碰撞体的 `region` 为 `null`。
非 FBX 的纯 prefab（如 工程A 的 `Outfit_RePoppin`）能拿到真名与完整链
（工程A：46/164 有名）。运行时由 T-27 导出真名表，`--diff` 与本表对齐（M6）。

## 8. 验收

```bash
python3 开发工具/通用工具/审查/perception/pb_static.py --selftest
```

自验覆盖：① 活跃根计数 = 164（与 `PhysBoneAudit.cs` 注释一致）并给 grep 口径对照；
② 动态造 `工程A.tail`（尾）与 `工程A.skirt`（`kaguya_cloth` 裙）两件，
都 `has_pb=true` 且 `chains[]` 非空；③ U7（缺 `LeftUpperLeg` 碰撞体必须报、
带 PB 路径与 region 名；已覆盖时不报）；④ `--diff` 对手改过的运行时表报出增删改。
