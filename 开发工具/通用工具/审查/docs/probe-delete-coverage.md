# 探针 delete_coverage（MA ShapeChanger 删除区覆盖） <!-- nav -->

> 旧称：T1 `AuditStateDriver` / T3 `AuditTurntable` 等（原 `审查/README.md`） §3.2.7。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[工程A 回归验收口径](regression-工程A.md) · 下一页：[探针 shrink_cover（收缩键遮挡一致性）· 请求与参数](probe-shrink-cover.md) <!-- nav -->

#### 3.2.7 `delete_coverage`——MA ShapeChanger 的删除区有没有被宿主件盖住（任务 BQ，B-补-20）

`ModularAvatarShapeChanger` 的 `ChangeType=Delete` 会在构建期处理目标网格（通常身体 `Body_base`）的某个
形态键：常驻（constant active）走 `RemoveVertices` 删图元，可开关的走 NaNimation。被这个形态键移动过的
图元（=**删除区**）如果在新状态下没有被**写者自己那件**盖住，就会露出缺口。2026-09-19 工程B档 6 雪花
罗曼史就是这型：无脚长袜 `Socks` 删身体 `Ankle_L/R`，脚踝其实靠靴子盖；「鞋关袜开」时脚踝被删却无人盖
（`审查产出/工程B/seq_snowflake_delete/09_*`），修法是把 Delete 挪到 `Boots`。本探针把它变成数字。

**量测口径（任务 BV 返工）**：**只在编辑模式量**，菜单 `Tools/AvatarAudit/Delete Coverage (Edit Mode)`。
Play/构建后 MA 的 Delete 已经生效——常驻 Delete 走 `RemoveVertices` 删顶点，可开关 Delete 走 NaNimation
（骨骼 scale=NaN），原始网格已不存在、顶点下标也对不上；所以 T1 探针名 `delete_coverage` 保留，但在
Play 里被调用时直接返回 `{ "undecidable": "MA 已处理网格", ... }`，不做几何量测。编辑模式里原网格与
MA `ModularAvatarShapeChanger` 组件都还在，用写者宿主的 `activeSelf` 组合模拟「件开/件关」，不需要进 Play。

请求文件（可选）`<工程>/Library/AvatarAudit/delete_coverage_request.json`；菜单会自动读它，输出写
`<工程>/Library/AvatarAudit/delete_coverage_edit.json` 并打 Console：

```json
{"tool":"delete_coverage",
 "delete_coverage_threshold_mm":15, "delete_coverage_min_ratio":0.2,
 "states":[{"id":"s6_sok_on_sho_off","params":{"Socks":true,"Boots":false}}]}
```

`states[].params`（别名 `hosts`）把「写者宿主」按相对路径 / 叶名 / 子串匹配到 开/关（bool 或 0/1），
没点到的宿主保持编辑场景现值；缺 `states` 时只跑一个「当前编辑态」。

**判据（对齐 MA 1.18 Delete 语义，不再自己拍脑袋）**：删除区 = 写者 `ModularAvatarShapeChanger.m_threshold`
（字段经反射读；默认 `0.01`，**网格局部单位**）为阈值，取目标形态键原始 delta 长度² > `m_threshold²`
的顶点，再按图元级选择（`VertexFilterByShape` 默认 AnyVertex：图元任一顶点命中即整块）把命中图元的
**全部顶点**纳入；位置取该键**权重 0** 的世界坐标（缺口位置）。delta 优先读
`Mesh.GetBlendShapeFrameVertices`（与 MA 同源），网格不可读时退回 `BakeMesh(m,true)` 0/100 的局部差值
（`region_source` 记 `*_fallback`）。宿主 = **写者 GameObject 及其子树**的全部 Renderer（SMR / MeshRenderer）
——只认写者自己那件，靴子不算袜子的宿主；`uncovered_ratio` = 删除区顶点到宿主表面最近距离（顶点到三角形，
30 mm 空间哈希 + 暴力退路）超过 `threshold_mm` 的占比，另给 `p50_mm` / `p95_mm` / `max_mm` / 前 5 个未盖
顶点世界坐标 `sample_uncovered`。写者挂在**无网格容器**上时照样出行，标 `host_has_no_mesh:true`，不跳过。
宿主不可见（`activeInHierarchy && enabled` 全 false）时照样算，标 `host_visible:false`（MA 反应式：宿主
隐藏时删除本就不生效，该行只作参考）。

编辑模式输出字段：`tool`、`mode:"edit"`、`avatar`、`scene`、`threshold_mm`、`min_ratio`、`region_rule`、
`writer_count`、`state_count`、`host_has_no_mesh`、`hits`、`states[{id,hosts,writer_count,host_has_no_mesh,hits,
writers[...]}]`；每个 writer 行含
`writer_path,host_path,host_visible,host_renderers,host_has_no_mesh,target,key,threshold_local,threshold_mm,
deleted_vertices,primitive_count,region_source,uncovered_vertices,uncovered_ratio,p50_mm,p95_mm,max_mm,
sample_uncovered,error?`。`hits` = **host_visible 且 deleted_vertices>0 且 uncovered_ratio ≥ min_ratio** 的行数。
Play 里 T1 探针返回 `{undecidable:"MA 已处理网格", writers:[], hits:0}`（探针不炸 T1）。

请求样例（编辑模式菜单读，**不再进 Play**；阈值可选）：

```json
{"tool":"delete_coverage",
 "delete_coverage_threshold_mm":15, "delete_coverage_min_ratio":0.2,
 "states":[{"id":"s6_sok_on_sho_off","params":{"Socks":true,"Boots":false}},
           {"id":"s6_all_on","params":{"Socks":true,"Boots":true}}]}
```

**[Claude·Unity·编辑模式验收 · 工程B档 6（雪花罗曼史）——安全版，不覆盖任何已跟踪文件]**：

> 前置硬规矩：每条命令前先 `git status --porcelain`；只要看到
> `工程B/Assets/_Work/工程B_Milfy.unity` 被改，立即停，别 `git checkout` 覆盖。
> 下面只新建**未跟踪**文件、写 `Library/` 与输出目录。

1. `python3 开发工具/通用工具/审查/perception/sync_audit.py 工程B`（把含本探针的
   `审查/unity/` 同步进工程；若此刻正有别的 DSH 在改 `审查/unity`，先等它交付）。Unity refresh + 编译，
   确认 **0 error**。
2. **修后版（Boots 删 Ankle）**：Unity 打开 `工程B/Assets/_Work/工程B_Milfy.unity`，
   新建未跟踪请求文件 `工程B/Library/AvatarAudit/delete_coverage_request.json`：
   ```json
   {"tool":"delete_coverage","delete_coverage_threshold_mm":15,"delete_coverage_min_ratio":0.2,
    "states":[{"id":"s6_sok_on_sho_off","params":{"Socks":true,"Boots":false}}]}
   ```
   跑菜单 `Tools/AvatarAudit/Delete Coverage (Edit Mode)`。期望：`states[0].writers` 里
   `writer_path` 含 `Boots` 且 `key=Ankle_L/Ankle_R` 的行 `host_visible=true`、**`uncovered_ratio` 低**；
   `region_source` 应为 `asset_delta_primitive`（或 `*_fallback_primitive`），`threshold_local=0.01`。
3. **修前版（Socks 还删 Ankle）对照**：**用只读 `git show` 导一份未跟踪副本工程/场景**（见下），
   在副本里跑同一请求。**不要动真工程文件**。
   - 只导场景（够用，MA 组件在场景里）：
     ```bash
     git show 7bec31a5^:工程B/Assets/_Work/工程B_Milfy.unity \
       > 工程B/Assets/_Work/_BV_parent_check.unity
     ```
     然后 Unity 打开 `_BV_parent_check.unity`（注意 Unity 打开别的场景时会问是否保存当前场景——**取消/不保存**），
     跑同一菜单。期望：`writer_path` 含 `Socks`、`key=Ankle_L/Ankle_R` 的行 **`uncovered_ratio` 高**
     （无脚长袜盖不住脚踝；靴子不算宿主）。
   - 若只导场景不够（HB 引用/依赖），退而用**副本工程**：`cp -al` 整个工程到 `_scratch` 再 `git show` 覆盖那份场景，
     在副本里开 Unity（用完删副本）。
4. 验完删 `_BV_parent_check.unity`（未跟踪）。对照两批 `states[0].writers` 的 `uncovered_ratio` 即可。
   **离线已做 csc 全量两分支 0 error + 纯函数自检 20 PASS / 0 FAIL；编辑模式运行期读数待上面步骤取证。**
