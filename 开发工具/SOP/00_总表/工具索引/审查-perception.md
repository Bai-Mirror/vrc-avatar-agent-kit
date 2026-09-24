> ← [工具索引](../工具索引.md) <!-- tools_index.py 自动生成：整页覆盖，勿手改 -->

# 工具索引 · 审查-perception（22 个文件）

由 `python3 开发工具/通用工具/tools_index.py --write` 从各脚本文件头的「用途 / 可复用性」生成，整页覆盖；要改内容请改脚本文件头。路径相对 `开发工具/`。

### 通用工具/审查/perception

| 路径 | 用途 | 可复用性 |
|---|---|---|
| `通用工具/审查/perception/clip_writes.py` | 从 AnimatorController + AnimationClip 抽「(状态, 路径, 键) → 值」，T-11 的子模块。 | ★★ 审查工具链的一环 |
| `通用工具/审查/perception/clip_writes_diff.py` | 比对迁移前后两份 clip_writes.py 输出的写者集合，T-07 回归用。 | ★★ 审查工具链的一环 |
| `通用工具/审查/perception/decl_draft.py` | 感知声明草案生成器：从工程里能读到的事实起草 _感知/声明.yaml，人只补 human 项。 | ★★ 改写者来源表即可复用 |
| `通用工具/审查/perception/decl_validate.py` | 感知声明校验器（perception/0.2）：声明 YAML → decl.json，并校验字段与引用。 | ★★ 按 schema 复用 |
| `通用工具/审查/perception/key_class_blender.py` | T-17 形态键类别标定（Blender 离线）：量刚体拟合残差与法向内收均值，判 pose/shrink/other。 | ★★ 按素体档案复用 |
| `通用工具/审查/perception/key_follow_verdict.py` | key_follow 候选 × T1 实测状态 → 同名键失配判定 mismatch/benign/no_data。 | ★★ 审查工具链的一环 |
| `通用工具/审查/perception/key_gaps.py` | key_follow 盲区补检：件上缺身体被写的键、写者挂错件。 | ★★ 审查工具链的一环 |
| `通用工具/审查/perception/muscles.py` | 人形 95 肌肉固定顺序表与部位映射、姿势元数据；pose_frames.py 依赖它。 | ★★★ 换个单子直接能用 |
| `通用工具/审查/perception/pb_static.py` | PhysBone 静态清单与 U7 判据：解析 VRCPhysBone/Collider，算每个覆盖件的链与碰撞体。 | ★★ 审查工具链的一环 |
| `通用工具/审查/perception/pose_frames.py` | 姿势帧库：把 SDK/GoGo Loco/工程私有/关节扫掠统一成「95 肌肉向量 + RootT/RootQ」帧库。 | ★★ 按工程姿势来源复用 |
| `通用工具/审查/perception/pose_plan.py` | 姿势×状态计划：按 03 §8.4 生成 T1 姿势请求批，并出 pose_plan.json 与被预算截断项。 | ★★ 审查工具链的一环 |
| `通用工具/审查/perception/profile_keys.py` | 把 T-05 盘点的身体全量形态键写进素体档案的 all_keys 段。 | ★★ 按素体档案复用 |
| `通用工具/审查/perception/rules_universal.py` | T-14 通用规则（U1 起，与声明无关、每批必跑）＋构后改名解析。 | ★★ 审查工具链的一环 |
| `通用工具/审查/perception/selftest_r9_indistinguishable.py` | R9「不可分辨」分流纯函数离线自检（不起 Unity），区分候选真等价与键没写进去。 | ★ 针对特定任务的离线自检，主要供参考 |
| `通用工具/审查/perception/selftest_shrink_cover.py` | shrink_cover「遮挡集合名单 + 自检 + 外向射线几何」纯离线自检（不起 Unity）。 | ★ 针对特定任务的离线自检，主要供参考 |
| `通用工具/审查/perception/shrink_host_scan.py` | 收缩键宿主静态扫描：每个 MA ShapeChanger 挂在谁身上、写了哪些键，按宿主件名与影响身体段初筛可疑。 | ★★ 审查工具链的一环 |
| `通用工具/审查/perception/static_rules.py` | T-11 静态规则候选表，在 writers.json 上离线跑。 | ★★ 审查工具链的一环 |
| `通用工具/审查/perception/strip_audit.py` | 交付前剥离审查残留 + 零残留自检（T-23）：--check 列出、--apply 实删/改。 | ★★ 审查工具链的一环 |
| `通用工具/审查/perception/sync_audit.py` | 把 审查/unity/ 同步到某个 Unity 工程的 Assets/AvatarAudit/，并清理旧落点（--strip 剥离残留）。 | ★★ 审查工具链的一环 |
| `通用工具/审查/perception/unity_yaml.py` | Unity 多文档 YAML 读取共用件，被 writers_static.py / clip_writes.py 复用。 | ★★★ 换个单子直接能用 |
| `通用工具/审查/perception/verdict.py` | T-14 校验器：声明（应该怎样）× T1/geo/写者（实际怎样）→ 对账并归因。 | ★★ 审查工具链的一环 |
| `通用工具/审查/perception/writers_static.py` | 离线静态写者图：合并我方控制器、厂商 clip、场景/prefab 的 MA 写者（不重实现 MA 胜负规则）。 | ★★ 审查工具链的一环 |
