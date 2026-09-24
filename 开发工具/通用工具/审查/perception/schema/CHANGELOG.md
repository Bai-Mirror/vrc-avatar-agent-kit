# perception schema v0.2 · 改动记录

> 配套 `perception-0.2.schema.json` 与 `CONDITION_GRAMMAR.md`。新条目加在最上面。

## 2026-09-19 任务 AQ（素体档案全量键表）

**改动**：SEM-07 支持素体档案新段 `all_keys:`（T-05 盘点 `body_keys` 落下来的身体网格全量键表，
由 `perception/profile_keys.py` 写入）。档案有 `all_keys` 时，声明里目标为身体网格的键不在表内
→ **error**（`key_classes` 只用于分类）；没有 `all_keys` 时维持旧口径（`key_classes` + `baseline`
+ `keys`，缺失降为**警告**）。schema 本身不动（素体档案仍无 schema），只改 `CONDITION_GRAMMAR.md`
§5 的 SEM-07 行与末段说明。

**配套**：T-05 `AuditPartInventory.cs` 每头像新增 `body_keys`/`body_key_count`；新增
`perception/profile_keys.py`（只替换 `all_keys:` 段、保留其余注释；已存在且不同时默认只报告差异，
`--force` 才覆盖）。`--selftest` 增加 SEM-07 专项：features_misc + 注入 profile 的正/反例。

**不影响**：其余 SEM 规则、schema 反例集合与 `--selftest` 的 8+250 计数不变。

## 2026-09-18 rev 2（审稿回收）

**依据**：独立审稿意见 P1–P15 与「§6 文字不符」两处；审稿之后 03 升到 v3（22:30），§8 与 04 T-32 也改了，本版一并对齐（凡与审稿建议冲突，以 04 v3 为准，逐条写在下表）。

### 逐条处置

| # | 处置 | 落点 |
|---|---|---|
| P1 姿势段 | **采纳，有一处改动**：顶层 `poses {libraries, extra_clips, pb_default, dose_envelope, private_clips}`；`parts[].pb`、`parts[].pose_scope {include, exclude}`（姿势 id 或 `tag:`）；`geo.no_poke {region, max_depth_mm, min_area_cm2}`；waiver 加可选的 `pose`（选择子或列表）与 `pb_mode`（rigid/settle）；`03a_project-c` 的 D8 改用 no_poke 与库 id。审稿建议的 `sweep_max: 75\|100` 没加：04 v3 T-32 把 P13 改成了 `dose_envelope: libraryA\|extreme`，照 04。另加了 `private_clips`（P14 开关，缺省 true） | schema `$defs/poses`、`geoNoPoke`、`poseScope`、`waiver`；CONDITION_GRAMMAR §1（pose/pose_tag 原子）、§3（姿势 id 与 tag，按 T-26 实际命名） |
| P2 no_poke 默认生成 | 采纳：`geo_defaults.cover: no_poke\|none`（缺省 no_poke），生成项 id 为 `geo.<件>.poke` | schema `$defs/geoDefaults`；§6 第 2 步 |
| P3 片段与声明矛盾 | 采纳三项：① 片段 dep 的 else 缺省改为 dont_care；② 加 SEM-22（同一 (网格, 键) 在任一可达状态下非 dont_care 的期望必须相容，状态按 §6.1 临界点取样枚举，可见性用 §2.2 的期望可见性模型 E）；③ 加 `supersedes`（被取代的不进期望矩阵，也不能再被豁免；引用检查为 SEM-24）。另加写法约定：多个整套共用的键，各 dep 的 else 写 dont_care，回基线交给 U3 | schema `dep.supersedes`、`else` 描述；§2.2、§2.3、§5 SEM-22/24、§6 |
| P4 往返语法歧义 | 采纳：`->` 是整体记号；参数名与标签里不许出现 `: , " →` 和 `->`，带这些字符的要加引号；int/float_slots 只许写标签或 `#i` 槽号，不许写裸数；长得像数字的标签加引号。schema 里的往返正则按这套 EBNF 重写。**顺带修了一个问题**：参数名原来不许有空格和括号，但真实工程里有 `CERP Pose`、`kaguya ear`、`…/Middle(Big0)…##7`（工程A 与工程D的 t4_menu/params.json 实查），现在允许，在条件和往返里加引号写 | schema `$defs/param`、`dep.roundtrip`；§1 词法、§4 |
| P5 条件语法细节 | 采纳：pose、kind 改成普通标识符，由 SEM-03 查词表或姿势库（缺 `pose_library.json` 时按 §3 的内置清单：`proxy_`/`go_`/`B_`/`C_emote_`/`C_go_` 这几个固定家族必须在清单里，工程私有与 extra 离线查不了只出警告）；加 `pose_tag`；保留字只剩首段 `any`（`body.ears` 合法）；加 `ctl(<控件>) = 标签 \| #i \| 0/1` 与 `ctl(…) in {…}` | §1、§2.1、§3、§5 SEM-03 |
| P6 sem18 连带 SEM-08 | 两条都做：底稿 menu 补 bottom 槽；SEM-18 写明片段不合格就不合并、后续规则不再看它。另加 `sem08_fragment_part_slot`，专门演示片段部件的 SEM-08 和带 `#` 的报错路径 | `bad/sem18_*`、§5 SEM-18 |
| P7 variant.options 误报 | 采纳：options 的语义改为「组内可见件 ⊆ {use}」（外套关着不算违例）；`exclusive: false` 且不写 options 时 schema 拒 | schema `expectation.variant`；§2.3 |
| P8 头饰抓屏 | 采纳：顶层 `render.grab_point_min`（缺省 3050）；期望加 `grab {point_min, hidden_behind_max}`；target 加 `submesh`（只随 part、只配 grab）；dep kind 加 `R`（渲染/抓屏，03 Q10 的 kind 扩展）；waiver 的 dep 和 `rule: U1…U7`＋`parts` 二选一；指标加 `grab.point_queue`（用新加的 `limit.min`）、`grab.hidden_count`、`poke.area_cm2`、`poke.max_depth_mm`、`opening.max_shrink_mm`。`工程A_min` 写了 `工程A.grab.headdress_color_chain`（回放库的 dep_id）和 PixelBoot 的 U4 规则豁免 | schema `grab`、`render`、`target`、`waiver`；`ok/工程A_min.yaml` |
| P9 取值漏洞 | 采纳：`{class, tol}` 被拒（tol 只随 value/values）；key 与 meshPath 的任何一段都不许以 `AAO_Merged_` 或 `$$AAO_` 开头；片段 dep 的写者只许 vendor_*，confidence 的 correct 固定为 unknown，也不许写 correct_basis | schema `KEY`/`MESH_PATH`、`fragmentDep`、`fragmentConfidence` |
| P10 部件与控件绑定 | 采纳，但**改了键名**：`parts[].toggle {control, shown_at}`，与 slot 互斥，SEM-08 核对。建议里的 `on` 会被 YAML 1.1 解析成布尔 True（初写时实测撞上：`/parts/3/toggle/True`），和 `vendor_clip` 不用 on/off 同理；为此加了反例 `schema_part_toggle_on_yaml_bool` | schema `$defs/toggle`；§2.2、SEM-08 |
| P11 展开规则 | 采纳：covers 为空（或减掉开口后为空）就不生成；有 openings 的件另生成 `geo.<件>.opening`，可用 `geo_defaults.opening` 关掉；inside/no_pierce/no_poke 的区域都是 covers 减 openings。区域运算按叶子算：LeftFoot＝四个子部位，新加的聚合名 LeftFingers/RightFingers＝各 15 节指骨；不按叶子算，手套减指尖就减不动 | schema `geoDefaults`、`region`；§6 第 2 步 |
| P12 胸部 | 采纳两项：`sync` 加 `scale/offset` 或分段 `map`（两者互斥，map 的源值升序由 SEM-13 查）；body_axes 加 `samples` | schema `$defs/sync`、`bodyAxis` |
| P13 片段展开 | 采纳：片段里衣物网格一律用 `{part, key}`，`mesh` 只能写身体网格，而且必须等于 avatar.body（SEM-18），不拼 mount；片段来源的报错路径统一写 `/includes/<i>/fragment#<片段内路径>`；片段单独校验时跑哪些规则也写明了 | §5 末段、§6 第 1 步、§8 |
| P14 expect_by_leader | 采纳：chain 必须是 when 的顶层合取项（不能在 `!` 或 `\|` 下面）；键集合必须**恰好等于**成员集合。选严格相等，不选「缺的走 else」：漏写一个成员通常是笔误，不该静默放过 | §5 SEM-04 |
| P15 文档 | **本任务里做不了**：03 §3 FootNail 那一行要改 03，不在本任务可写的文件里（正例已按 `美甲清点.md:6` 写 `FootNail_Default Variation`）。素体档案 schema 也不在 T-01 的范围里，见「遗留」 | — |
| §6 note 与实际不符 | 采纳：schema 反例的 `# note:` 改由生成脚本算出来：跳过 schema、直接跑语义层时还会命中哪些规则，或者语义层会崩，写进 note。188 个 schema 反例里 44 个带 note：28 个写「另会命中 SEM-xx」，16 个写「语义层会崩」；其余 144 个跳过 schema 跑语义层也不会多报。§8 写明：schema 不过的文档不跑语义层 | §8；`bad/schema_*` 头注释 |
| §6 「路径落在后出现的字段」 | 采纳：互斥规则一律改成按规范顺序**单向**写（expectation 的主形式、geo 度量、sync 的 map 等），同写两个互斥字段时只在排在后面的那个字段上报；§8 列出了全部规范顺序 | schema `exclusive_chain`；§8 |

### 审稿之外的改动

- **对齐 03 v3 的几何口径（F26）**：U1 的主判据已改为静态穿出斑块。`geo.inside`/`no_pierce` 的语义同步改为「斑块数＝0」，加 `min_area_cm2`；包含率降为参考列。waiver 指标删掉 `geo.intersections`、`geo.max_depth_mm`、`geo.outside_ratio`：参考列不设阈值，豁免它们没有意义。
- **`baseline` 用在 `{part}` 目标上的含义**原来没定义，现在定为「可见性等于期望可见性模型 E」（§2.3）。
- **SEM-22 在初稿里抓到一个真冲突**：`03a_milfy` 初稿中，`snowflake.foot_by_leader` 的 else 写的是「全 0」，在 LUNALICE 整套下和 `milfy.lunalice.foot`（Foot_highheels＝100）冲突（`/deps/3/id`，outfit＝9）。已拆成「按 leader」和「本套光脚」两条，多套共用的脚型键 else 一律改 dont_care。工程C `violet.toe_highheels` 也同样改成 dont_care。
- 内置参数表补齐（PreviewMode、IsAnimatorEnabled、AvatarVersion、ScaleFactorInverse、EyeHeightAsMeters/Percent、VelocityMagnitude、VRCEmote、VRCFaceBlendH/V）。
- **姿势 id 对齐 T-26 的实现**：写本版时发现 DSH 已在同目录写了 `pose_frames.py`（任务 AB，22:46–22:58），它的命名是 `proxy_*`、`go_*`、`B_<关节>_<L|R|C>_<剂量>`、`B_combo_*`、`C_emote_*`、`C_go_*`、`C_extra_*`，工程私有 clip 不加前缀，多帧 clip 用 `@<取样序号>`。T-26 的任务书没规定命名，我起草的 §3（`sw_*`/`cb_*`/`gm_*`/`prv_*`）会和它冲突，所以改成照它的实现写，没去改它的文件。姿势 id 的正则放宽到大小写字母、数字、下划线和汉字（私有 clip 名里有「抱熊」）。用它实跑 `--envelope extreme` 得到的 工程A 库（360 条）交叉核对：内置清单 0 条误判、65 条工程私有只出警告；库里的 tag 全在 §3 词表里；例子里用到的姿势 id 都在库里（输出见下）。`poses.dose_envelope` 的取值 `libraryA|extreme` 与它的 `--envelope` 参数一致。
- 新正例 `fragment_features.decl.yaml`（示意片段），覆盖片段专用字段（alt_of、openings、owner_writers、pb、pose_scope、toggle、vendor_clip、targets、cases、expect_by_leader 含 `any.<kind>`、else、human），由 `features_misc` 以 `as: FX` 引入。
- `工程A_min` 改成 T-03 的样板：引入 MMN 片段并整条覆盖 MMN.shoes（写回人判答案），`MMN.foot_flat` 用 `supersedes` 取代片段依赖；加上头饰、发饰控件与 toggle、`pose_scope`、R 抓屏依赖、PixelBoot U4 豁免。豁免的 `by` 写的是「待用户确认」：施工记录只写了「09-03 记为可接受残留」，没写是谁定的。

### 遗留问题

1. **03 §3 FootNail 行**与 `工程A/Assets/_Work/美甲清点.md:6` 矛盾：带渲染器的是 `FootNail_Default Variation`，没有渲染器的包装物体是 `FootNailToggle_Default Variation`。要改的是 03 §3 那一行，交主会话处理。
2. **素体档案没有 schema**：SEM-07（身体键存在）和 SEM-22 的 baseline 比较都依赖它，03 §3「删带计数 aliases」也没有地方强制。建议加一个 T-01b（Claude，S），在 T-03 起草 `Kaguya.yaml` 之前补上；在那之前，SEM-07 按本页降为警告，SEM-22 不比 baseline。
3. **回放库 `replay/grab_headdress/expect.json` 的 `dep_kind: "U4"`** 写的是规则号；声明里这条依赖的 kind 是 `R`，规则 U4 是另一回事。建议 T-15 的负责人改成 `R`，或在回放格式里把 kind 和 rules 分开写（它已经有 `rules: ["U4"]`）。本任务不改回放库。
4. **PixelBoot 的渲染器类型**按 MeshRenderer 写（模型实例、无蒙皮，属推断）；豁免的批准人待用户确认。这两处都在 `工程A_min` 的 source/by 里标明了，T-05 盘点出来后由 SEM-12 核对。
5. **§3 是按 `pose_frames.py` 22:58 版（sha256 前缀 1c37aef22aa92673）写的**，T-26 还在进行。它交付时如果改了命名，要同步改 §3、`POSE_SEL` 的正则（放宽后一般不用动）、内置清单，以及 `project-c`、`features_misc`、`fragment_features`、`工程A_min` 里的姿势 id。另外，离线校验认不出工程私有 clip 的拼写错误：它们没有前缀，只能出警告。要想离线也能判错，可以让 T-26 给私有 clip 加前缀（如 `P_`），这要主会话拍板，本任务不改它的文件。
6. **审稿人的 `sem.py` 已过时**：它写死了旧的 7 个姿势词、只认 dep 豁免，对新版会误报 `project-c` 的 SEM-03，并在 rule 豁免上崩溃（KeyError: 'dep'）。它的 `sv.py`（schema 层）仍然可用，结果见下。
7. 本任务中途，工作区的周期提交（9ac10c63 等，不是本任务做的）把我当时的半成品版本也扫进了 git；最终版以工作区现状为准，按任务要求本任务没有提交。
8. 语义层原型 `check.py` 与生成脚本都在 scratchpad（会话临时目录 `scratchpad/t01/`，未入库：`build_schema.py`、`gen_bad.py`、`check.py`、`coverage.py`），**不是交付物**，T-02 应按 CONDITION_GRAMMAR 重写。它们只证明了规则可以实现，也证明了例子符合规则。

### 校验

本机 `python3 3.14.4`、`jsonschema 4.19.2`、`PyYAML 6.0.3`。载入 YAML 时去掉时间戳的隐式解析，报错路径按 §8 规范化。

- 正例 8/8：schema 通过，语义层（SEM-01…24；SEM-22 枚举的状态数：工程A_min 8 064、03a_工程A 6 720、features_misc 120 960、03a_milfy 1 040、03a_project-c 256、03a_h3 3）0 错。
- 反例 250：schema 层 188 个，全部被拒，期望路径都在规范化路径集合里；语义层 62 个，全部先通过 schema，再被语义层拒，每个都只命中头注释里写的那一条规则，而且报出了期望路径。审稿人的独立脚本 `sv.py`（未改）结果相同：188 GOOD、62 SCHEMA_PASS。
- 字段覆盖：233 个（上下文, 字段）里有 232 个在正例里出现；唯一例外 `menu.slots.*.labels` 是故意的，bool 开关不许写 labels，它由反例 `schema_menu_bool_labels` 覆盖。按字段名统计，每个字段都至少有一个反例。
- 姿势 id：拿 `pose_frames.py --envelope extreme` 实跑出来的 工程A 库（360 条）逐条过内置清单，0 条误判，65 条工程私有只出警告；库里的 tag 全在词表里；例子里用到的姿势 id 都在库里。
- 封闭性：除根以外，所有结构对象都是 `additionalProperties:false`。报出的两处「开放对象」是 `if` 条件子模式，不是字段定义。没有 description 的 29 处也都在 if/then 条件子模式里。

<details><summary>完整输出（2026-09-18 23:09）</summary>

```
$ date; sha256sum schema/perception-0.2.schema.json
2026-09-18 23:09:15 +1200
be6cdaed34a83ca1d5eed1b8fd23dcc3ac829969894c50d1562ae1faca887074  schema/perception-0.2.schema.json
python 3.14.4 | jsonschema 4.19.2 | PyYAML 6.0.3 | check_schema(Draft 2020-12): ok

$ python3 check.py   # schema＋规范化路径＋SEM-01…24 原型
ok  PASS 03a_工程A.yaml
ok  PASS 03a_h3.yaml
ok  PASS 03a_milfy.yaml
ok  PASS 03a_project-c.yaml
ok  PASS 工程A_min.yaml
ok  PASS features_misc.yaml
ok  PASS fragment_MMN.decl.yaml
ok  PASS fragment_features.decl.yaml
bad OK  schema_avatar_body_path.yaml exp=/avatar/body 
bad OK  schema_avatar_missing_root.yaml exp=/avatar/root 
bad OK  schema_avatar_profile_pattern.yaml exp=/avatar/profile 
bad OK  schema_avatar_project_empty.yaml exp=/avatar/project 
bad OK  schema_avatar_scene_pattern.yaml exp=/avatar/scene 
bad OK  schema_body_axis_both.yaml exp=/body_axes/bust/param 
bad OK  schema_body_axis_param_arrow.yaml exp=/body_axes/bust/param 
bad OK  schema_body_axis_samples_range.yaml exp=/body_axes/bust/samples/1 
bad OK  schema_control_label_empty.yaml exp=/menu/slots/socks/label 
bad OK  schema_dep_also_field.yaml exp=/deps/0/also 
bad OK  schema_dep_as_listed.yaml exp=/deps/0/expect/value 
bad OK  schema_dep_by_leader_key.yaml exp=/deps/0/expect_by_leader/MMN shoes 
bad OK  schema_dep_by_leader_no_chain.yaml exp=/deps/0/when 
bad OK  schema_dep_cases_empty.yaml exp=/deps/0/cases 
bad OK  schema_dep_cases_missing_when.yaml exp=/deps/0/cases/0/when 
bad OK  schema_dep_chain_field.yaml exp=/deps/0/chain 
bad OK  schema_dep_confidence_enum.yaml exp=/deps/0/confidence/correct 
bad OK  schema_dep_confidence_single.yaml exp=/deps/0/confidence 
bad OK  schema_dep_correct_basis_pattern.yaml exp=/deps/0/confidence/correct_basis 
bad OK  schema_dep_else_enum.yaml exp=/deps/0/else 
bad OK  schema_dep_exceptions_field.yaml exp=/deps/0/exceptions 
bad OK  schema_dep_expect_and_cases.yaml exp=/deps/0/cases 
bad OK  schema_dep_extra_field.yaml exp=/deps/0/extra 
bad OK  schema_dep_flag_field.yaml exp=/deps/0/expect/flag 
bad OK  schema_dep_human_empty.yaml exp=/deps/0/human 
bad OK  schema_dep_key_and_keys.yaml exp=/deps/0/target/keys 
bad OK  schema_dep_keys_map.yaml exp=/deps/0/target/keys 
bad OK  schema_dep_kind_enum.yaml exp=/deps/0/kind 
bad OK  schema_dep_missing_confidence.yaml exp=/deps/0/confidence 
bad OK  schema_dep_missing_source.yaml exp=/deps/0/source 
bad OK  schema_dep_missing_writer.yaml exp=/deps/0/writer 
bad OK  schema_dep_no_expect.yaml exp=/deps/0/expect 
bad OK  schema_dep_no_target.yaml exp=/deps/0/target 
bad OK  schema_dep_part_and_mesh.yaml exp=/deps/0/target/mesh 
bad OK  schema_dep_roundtrip_bad_slotref.yaml exp=/deps/0/roundtrip/0 
bad OK  schema_dep_roundtrip_no_arrow.yaml exp=/deps/0/roundtrip/0 
bad OK  schema_dep_roundtrip_unquoted_space.yaml exp=/deps/0/roundtrip/0 
bad OK  schema_dep_rules_field.yaml exp=/deps/0/rules 
bad OK  schema_dep_shown_if_field.yaml exp=/deps/0/else/shown_if 
bad OK  schema_dep_supersedes_empty.yaml exp=/deps/0/supersedes 
bad OK  schema_dep_supersedes_pattern.yaml exp=/deps/0/supersedes/0 
bad OK  schema_dep_target_and_targets.yaml exp=/deps/0/targets 
bad OK  schema_dep_vendor_correct_no_basis.yaml exp=/deps/0/confidence/correct_basis 
bad OK  schema_dep_when_bool.yaml exp=/deps/0/when 
bad OK  schema_dep_when_empty.yaml exp=/deps/0/when 
bad OK  schema_dep_writer_any.yaml exp=/deps/0/writer 
bad OK  schema_exp_class_enum.yaml exp=/deps/0/expect/class 
bad OK  schema_exp_class_tol.yaml exp=/deps/0/expect/tol 
bad OK  schema_exp_class_with_hidden.yaml exp=/deps/0/expect/class 
bad OK  schema_exp_deleted_max_ratio.yaml exp=/deps/0/expect/deleted/max_ratio 
bad OK  schema_exp_deleted_no_ratio.yaml exp=/deps/0/expect/deleted/min_ratio 
bad OK  schema_exp_deleted_ratio_range.yaml exp=/deps/0/expect/deleted/min_ratio 
bad OK  schema_exp_geo_depth_zero.yaml exp=/deps/0/expect/geo/inside/max_depth_mm 
bad OK  schema_exp_geo_inside_area.yaml exp=/deps/0/expect/geo/inside/min_area_cm2 
bad OK  schema_exp_geo_missing_region.yaml exp=/deps/0/expect/geo/no_pierce/region 
bad OK  schema_exp_geo_no_pierce_depth.yaml exp=/deps/0/expect/geo/no_pierce/max_depth_mm 
bad OK  schema_exp_geo_no_poke_area.yaml exp=/deps/0/expect/geo/no_poke/min_area_cm2 
bad OK  schema_exp_geo_no_poke_region.yaml exp=/deps/0/expect/geo/no_poke/region 
bad OK  schema_exp_geo_two_metrics.yaml exp=/deps/0/expect/geo/no_pierce 
bad OK  schema_exp_grab_empty.yaml exp=/deps/0/expect/grab 
bad OK  schema_exp_grab_hidden_negative.yaml exp=/deps/0/expect/grab/hidden_behind_max 
bad OK  schema_exp_grab_point_type.yaml exp=/deps/0/expect/grab/point_min 
bad OK  schema_exp_no_writer_enum.yaml exp=/deps/0/expect/no_writer_other_than/1 
bad OK  schema_exp_not_written_false.yaml exp=/deps/0/expect/not_written 
bad OK  schema_exp_opening_region.yaml exp=/deps/0/expect/geo/opening_intact/region 
bad OK  schema_exp_opening_shrink_zero.yaml exp=/deps/0/expect/geo/opening_intact/max_shrink_mm 
bad OK  schema_exp_pending_false.yaml exp=/deps/0/expect/pending 
bad OK  schema_exp_pending_no_human.yaml exp=/deps/0/human 
bad OK  schema_exp_range_len.yaml exp=/deps/0/expect/range 
bad OK  schema_exp_shown_false.yaml exp=/deps/0/expect/shown 
bad OK  schema_exp_sync_map_and_scale.yaml exp=/deps/0/expect/sync/map 
bad OK  schema_exp_sync_map_point.yaml exp=/deps/0/expect/sync/map/0 
bad OK  schema_exp_sync_missing_from.yaml exp=/deps/0/expect/sync/from 
bad OK  schema_exp_sync_offset_type.yaml exp=/deps/0/expect/sync/offset 
bad OK  schema_exp_sync_scale_type.yaml exp=/deps/0/expect/sync/scale 
bad OK  schema_exp_tol_without_value.yaml exp=/deps/0/expect/tol 
bad OK  schema_exp_two_primaries.yaml exp=/deps/0/expect/hidden 
bad OK  schema_exp_value_range.yaml exp=/deps/0/expect/value 
bad OK  schema_exp_values_bad.yaml exp=/deps/0/expect/values/Foot_Hiheel_____足_ハイヒール 
bad OK  schema_exp_variant_by.yaml exp=/deps/0/expect/variant/by 
bad OK  schema_exp_variant_missing_exclusive.yaml exp=/deps/0/expect/variant/exclusive 
bad OK  schema_exp_variant_nonexclusive_empty.yaml exp=/deps/0/expect/variant/options 
bad OK  schema_exp_variant_options_one.yaml exp=/deps/0/expect/variant/options 
bad OK  schema_frag_dep_correct_basis.yaml exp=/deps/0/confidence/correct_basis 
bad OK  schema_frag_dep_correct_raised.yaml exp=/deps/0/confidence/correct 
bad OK  schema_frag_dep_roundtrip.yaml exp=/deps/0/roundtrip 
bad OK  schema_frag_dep_supersedes.yaml exp=/deps/0/supersedes 
bad OK  schema_frag_dep_writer_gen.yaml exp=/deps/0/writer 
bad OK  schema_frag_menu.yaml exp=/menu 
bad OK  schema_frag_missing_package.yaml exp=/package 
bad OK  schema_frag_package_body.yaml exp=/package/body 
bad OK  schema_frag_package_name.yaml exp=/package/name 
bad OK  schema_frag_part_outfit.yaml exp=/parts/0/outfit 
bad OK  schema_frag_poses.yaml exp=/poses 
bad OK  schema_frag_version_float.yaml exp=/package/version 
bad OK  schema_geo_defaults_cover_enum.yaml exp=/geo_defaults/cover 
bad OK  schema_geo_defaults_extra.yaml exp=/geo_defaults/shoes 
bad OK  schema_geo_defaults_loose_enum.yaml exp=/geo_defaults/loose 
bad OK  schema_geo_defaults_off.yaml exp=/geo_defaults/closed 
bad OK  schema_geo_defaults_opening_enum.yaml exp=/geo_defaults/opening 
bad OK  schema_geo_defaults_string.yaml exp=/geo_defaults 
bad OK  schema_geo_defaults_tight_enum.yaml exp=/geo_defaults/tight 
bad OK  schema_human_missing_q.yaml exp=/parts/1/human/q 
bad OK  schema_include_as_pattern.yaml exp=/includes/0/as 
bad OK  schema_include_ext.yaml exp=/includes/0/fragment 
bad OK  schema_include_missing_mount.yaml exp=/includes/0/mount 
bad OK  schema_key_aao_merged.yaml exp=/deps/0/target/key 
bad OK  schema_menu_bool_default.yaml exp=/menu/slots/socks/default 
bad OK  schema_menu_bool_labels.yaml exp=/menu/slots/socks/labels 
bad OK  schema_menu_control_extra.yaml exp=/menu/slots/socks/values 
bad OK  schema_menu_control_missing_default.yaml exp=/menu/slots/shoes/default 
bad OK  schema_menu_empty.yaml exp=/menu 
bad OK  schema_menu_float_default_range.yaml exp=/menu/controls/light/default 
bad OK  schema_menu_labels_missing.yaml exp=/menu/controls/hair/labels 
bad OK  schema_menu_outfit_type.yaml exp=/menu/outfit/type 
bad OK  schema_menu_param_pattern.yaml exp=/menu/slots/socks/param 
bad OK  schema_menu_slot_name.yaml exp=/menu/slots/Socks 
bad OK  schema_mesh_aao_auto_merge.yaml exp=/deps/0/target/mesh 
bad OK  schema_note_type.yaml exp=/parts/0/note 
bad OK  schema_part_alt_objects.yaml exp=/parts/1/alt_objects 
bad OK  schema_part_alt_with_slot.yaml exp=/parts/2/slot 
bad OK  schema_part_alt_with_toggle.yaml exp=/parts/2/toggle 
bad OK  schema_part_closed_field.yaml exp=/parts/1/closed 
bad OK  schema_part_covers_region.yaml exp=/parts/0/covers/1 
bad OK  schema_part_fit_missing.yaml exp=/parts/0/fit 
bad OK  schema_part_human_object.yaml exp=/parts/1/human/a 
bad OK  schema_part_id_any_prefix.yaml exp=/parts/0/id 
bad OK  schema_part_id_one_segment.yaml exp=/parts/0/id 
bad OK  schema_part_kind_enum.yaml exp=/parts/0/kind 
bad OK  schema_part_objects_empty.yaml exp=/parts/0/objects 
bad OK  schema_part_objects_no_renderer.yaml exp=/parts/0/objects/0/renderer 
bad OK  schema_part_objects_string.yaml exp=/parts/0/objects/0 
bad OK  schema_part_opening_kind.yaml exp=/parts/1/openings/0/kind 
bad OK  schema_part_opening_region.yaml exp=/parts/1/openings/0/region 
bad OK  schema_part_outfit_type.yaml exp=/parts/0/outfit 
bad OK  schema_part_owner_writers_enum.yaml exp=/parts/0/owner_writers/1 
bad OK  schema_part_path_hash.yaml exp=/parts/0/objects/0/path 
bad OK  schema_part_pb_enum.yaml exp=/parts/0/pb 
bad OK  schema_part_pose_scope_empty.yaml exp=/parts/0/pose_scope 
bad OK  schema_part_pose_scope_selector.yaml exp=/parts/0/pose_scope/include/0 
bad OK  schema_part_renderer_enum.yaml exp=/parts/0/objects/0/renderer 
bad OK  schema_part_slot_pattern.yaml exp=/parts/0/slot 
bad OK  schema_part_source_level.yaml exp=/parts/0/source/0 
bad OK  schema_part_submesh_negative.yaml exp=/parts/0/objects/0/submesh 
bad OK  schema_part_subregion.yaml exp=/parts/0/covers/0 
bad OK  schema_part_toggle_control_pattern.yaml exp=/parts/2/toggle/control 
bad OK  schema_part_toggle_on_yaml_bool.yaml exp=/parts/2/toggle/shown_at 
bad OK  schema_part_toggle_shown_at_type.yaml exp=/parts/2/toggle/shown_at 
bad OK  schema_part_toggle_with_slot.yaml exp=/parts/0/toggle 
bad OK  schema_part_vendor_clip_missing_off.yaml exp=/parts/0/vendor_clip/off_clip 
bad OK  schema_part_vendor_clip_onoff.yaml exp=/parts/0/vendor_clip/on_clip 
bad OK  schema_part_vendor_clip_path.yaml exp=/parts/0/vendor_clip/on_clip 
bad OK  schema_poses_dose_envelope_enum.yaml exp=/poses/dose_envelope 
bad OK  schema_poses_extra_clip_path.yaml exp=/poses/extra_clips/0 
bad OK  schema_poses_library_enum.yaml exp=/poses/libraries/1 
bad OK  schema_poses_pb_default_enum.yaml exp=/poses/pb_default 
bad OK  schema_poses_private_type.yaml exp=/poses/private_clips 
bad OK  schema_poses_sweep_max_field.yaml exp=/poses/sweep_max 
bad OK  schema_region_aggregate.yaml exp=/parts/0/covers/0 
bad OK  schema_render_extra.yaml exp=/render/grab_queue 
bad OK  schema_render_grab_type.yaml exp=/render/grab_point_min 
bad OK  schema_root_chain_field.yaml exp=/chain 
bad OK  schema_root_missing_avatar.yaml exp=/avatar 
bad OK  schema_root_version.yaml exp=/schema 
bad OK  schema_roundtrip_default_k.yaml exp=/roundtrip_default/history_k 
bad OK  schema_roundtrip_default_template.yaml exp=/roundtrip_default/templates/1 
bad OK  schema_target_submesh_negative.yaml exp=/deps/0/target/submesh 
bad OK  schema_target_submesh_with_key.yaml exp=/deps/0/target/key 
bad OK  schema_target_submesh_without_part.yaml exp=/deps/0/target/part 
bad OK  schema_waiver_cause.yaml exp=/waivers/0/cause 
bad OK  schema_waiver_date.yaml exp=/waivers/0/date 
bad OK  schema_waiver_dep_and_rule.yaml exp=/waivers/0/rule 
bad OK  schema_waiver_hash_pattern.yaml exp=/waivers/0/decl_hash 
bad OK  schema_waiver_limit_max.yaml exp=/waivers/0/limit/max 
bad OK  schema_waiver_limit_max_and_min.yaml exp=/waivers/0/limit/min 
bad OK  schema_waiver_metric.yaml exp=/waivers/0/limit/metric 
bad OK  schema_waiver_metric_reference_only.yaml exp=/waivers/0/limit/metric 
bad OK  schema_waiver_missing_by.yaml exp=/waivers/0/by 
bad OK  schema_waiver_missing_hash.yaml exp=/waivers/0/decl_hash 
bad OK  schema_waiver_missing_reason.yaml exp=/waivers/0/reason 
bad OK  schema_waiver_missing_states.yaml exp=/waivers/0/states 
bad OK  schema_waiver_no_target.yaml exp=/waivers/0/dep 
bad OK  schema_waiver_parts_with_dep.yaml exp=/waivers/0/parts 
bad OK  schema_waiver_pb_mode_enum.yaml exp=/waivers/0/pb_mode 
bad OK  schema_waiver_pose_pattern.yaml exp=/waivers/0/pose 
bad OK  schema_waiver_rule_enum.yaml exp=/waivers/0/rule 
bad OK  schema_waiver_rule_no_parts.yaml exp=/waivers/0/parts 
bad OK  schema_waiver_tool_version.yaml exp=/waivers/0/tool_version 
bad OK  sem01_dup_dep_id.yaml exp=/deps/1/id 
bad OK  sem01_dup_part_id.yaml exp=/parts/2/id 
bad OK  sem01_geo_prefix_unmatched.yaml exp=/deps/0/id 
bad OK  sem02_chain_one_member.yaml exp=/deps/0/when 
bad OK  sem02_cond_syntax.yaml exp=/deps/0/when 
bad OK  sem02_numeric_label_unquoted.yaml exp=/deps/0/when 
bad OK  sem03_ctl_label.yaml exp=/deps/0/when 
bad OK  sem03_fragment_menu_atom.yaml exp=/deps/0/when 
bad OK  sem03_unknown_axis.yaml exp=/deps/0/when 
bad OK  sem03_unknown_ctl.yaml exp=/deps/0/when 
bad OK  sem03_unknown_kind.yaml exp=/deps/0/when 
bad OK  sem03_unknown_outfit.yaml exp=/deps/0/when 
bad OK  sem03_unknown_param.yaml exp=/deps/0/when 
bad OK  sem03_unknown_part.yaml exp=/deps/0/when 
bad OK  sem03_unknown_pose.yaml exp=/deps/0/when 
bad OK  sem03_unknown_pose_tag.yaml exp=/deps/0/when 
bad OK  sem03_unknown_slot.yaml exp=/deps/0/when 
bad OK  sem04_chain_duplicate.yaml exp=/deps/0/when 
bad OK  sem04_chain_in_disjunction.yaml exp=/deps/0/when 
bad OK  sem04_chain_negated.yaml exp=/deps/0/when 
bad OK  sem04_leader_keys_incomplete.yaml exp=/deps/0/expect_by_leader 
bad OK  sem04_leader_not_member.yaml exp=/deps/0/expect_by_leader/MMN.pants 
bad OK  sem05_body_axis_mesh.yaml exp=/body_axes/bust/key/mesh 
bad OK  sem05_target_mesh.yaml exp=/deps/0/target/mesh 
bad OK  sem05_target_part.yaml exp=/deps/0/target/part 
bad OK  sem06_grab_on_key.yaml exp=/deps/0/expect 
bad OK  sem06_hidden_with_key.yaml exp=/deps/0/expect 
bad OK  sem06_submesh_not_grab.yaml exp=/deps/0/expect 
bad OK  sem06_value_on_part.yaml exp=/deps/0/expect 
bad OK  sem06_values_with_key.yaml exp=/deps/0/expect 
bad OK  sem08_fragment_part_slot.yaml exp=/includes/0/fragment#/parts/2/slot 
bad OK  sem08_part_outfit.yaml exp=/parts/0/outfit 
bad OK  sem08_part_slot.yaml exp=/parts/0/slot 
bad OK  sem08_toggle_control.yaml exp=/parts/2/toggle/control 
bad OK  sem08_toggle_label.yaml exp=/parts/2/toggle/shown_at 
bad OK  sem09_alt_of_unknown.yaml exp=/parts/2/alt_of 
bad OK  sem10_variant_use.yaml exp=/deps/1/expect/variant/options/1/use 
bad OK  sem11_object_twice.yaml exp=/parts/1/objects/0/path 
bad OK  sem13_interval_reversed.yaml exp=/deps/0/when 
bad OK  sem13_range_reversed.yaml exp=/deps/0/expect/range 
bad OK  sem13_sync_map_order.yaml exp=/deps/0/expect/sync/map 
bad OK  sem14_default_off_slot.yaml exp=/menu/outfit/default 
bad OK  sem15_roundtrip_bare_number.yaml exp=/deps/0/roundtrip/0 
bad OK  sem15_roundtrip_label.yaml exp=/deps/0/roundtrip/0 
bad OK  sem15_roundtrip_param.yaml exp=/deps/0/roundtrip/0 
bad OK  sem15_roundtrip_slot_range.yaml exp=/deps/0/roundtrip/0 
bad OK  sem16_waiver_dep.yaml exp=/waivers/0/dep 
bad OK  sem16_waiver_rule_part.yaml exp=/waivers/0/parts/0 
bad OK  sem16_waiver_superseded.yaml exp=/waivers/0/dep 
bad OK  sem17_exclude_unknown.yaml exp=/geo_defaults/exclude/0 
bad OK  sem18_include_body_mismatch.yaml exp=/includes/0/fragment 
bad OK  sem18_include_mesh_mismatch.yaml exp=/includes/0/fragment 
bad OK  sem18_include_missing.yaml exp=/includes/0/fragment 
bad OK  sem19_pending_in_cases.yaml exp=/deps/0/human 
bad OK  sem20_dup_param.yaml exp=/menu/slots/shoes/param 
bad OK  sem22_class_conflict.yaml exp=/deps/1/id 
bad OK  sem22_value_conflict.yaml exp=/deps/1/id 
bad OK  sem23_pose_scope_unknown.yaml exp=/parts/0/pose_scope/include/0 
bad OK  sem23_waiver_pose_unknown.yaml exp=/waivers/0/pose 
bad OK  sem24_supersedes_cycle.yaml exp=/deps/1/supersedes/0 
bad OK  sem24_supersedes_self.yaml exp=/deps/0/supersedes/0 
bad OK  sem24_supersedes_unknown.yaml exp=/deps/0/supersedes/0 

ok files: 8  ok failures: 0   bad files: 250  bad mismatches: 0

$ python3 sv.py ok; python3 sv.py bad | 计数   # 审稿人的独立 schema 层脚本（未改）
OK  03a_工程A.yaml []
OK  03a_h3.yaml []
OK  03a_milfy.yaml []
OK  03a_project-c.yaml []
OK  工程A_min.yaml []
OK  features_misc.yaml []
OK  fragment_MMN.decl.yaml []
OK  fragment_features.decl.yaml []
    188 GOOD
     62 SCHEMA_PASS

$ python3 coverage.py
fields total 233 covered by ok 232
  NOT IN OK: ('menu.slots', 'labels')
field names total 138
fields without a negative (by name): 0
open object schemas (no additionalProperties:false, not a map): ['#/$defs/dep/allOf/3/if/properties/expect', '#/$defs/fragmentDep/allOf/3/if/properties/expect']
properties without description: 29 处，全在 if/then 条件子模式里（不是字段定义）

$ 姿势 id 交叉核对：pose_frames.py --envelope extreme 实跑（工程A）产出的库 vs 内置清单
库条目 360 | 内置清单判错 [] | 只出警告（工程私有） 65
库里的 tag 不在词表: [] | 例子里用到的姿势 id 都在库里: True
```
</details>

## 2026-09-18 rev 1（初稿）

把 03a Q1-① 收成封闭 schema：12 个未定义字段的处置见 CONDITION_GRAMMAR §7；定了写者词表和置信度两栏；objects 必带 renderer；新增 menu 输入段、geo_defaults、waivers 五元组；7 个正例（含 03a 14 条样例的改写）、165 个反例。
