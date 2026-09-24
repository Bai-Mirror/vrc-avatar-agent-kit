# perception/ — 感知机制离线工具（Python）

T-01～T-32 的离线部分；只读工程、不启动 Unity。共用件 `unity_yaml.py`（Unity 多文档 YAML）。

| 文件 | 任务 | 作用 |
|---|---|---|
| `unity_yaml.py` | T-04 抽公共件 | Unity YAML/`.controller` 读取、GUID 索引、名字还原 |
| `clip_writes.py` | T-11 辅助 | clip 曲线解析（`m_FloatCurves`/blend tree/状态机） |
| `writers_static.py` | T-11 | 静态写者图 `writers.json`（含变体链/嵌套 prefab 的 MA 组件，宿主解析到场景实例路径） |
| `static_rules.py` | T-11/E-T11-01 | 在 `writers.json` 上跑 6 类静态规则出候选（K1 同键多写者…K6 越界），不重扫、不判对错；`--selftest` 用 工程A/工程B真数据验已知样本 |
| `key_class_blender.py` | T-17 | 键类别标定（Blender 侧） |
| `profile_keys.py` | AQ | 把 T-05 盘点的 `body_keys` 写进素体档案 `all_keys:`（SEM-07 用全量键表） |
| `sync_audit.py` | T-09 | 审查代码同步（`--from-git <rev>` 从指定修订取源，隔离工作区半成品） |
| `strip_audit.py` | T-23 | 交付前剥离审查残留：`--check` 列出、`--apply` 实删＋零残留自检 |
| `muscles.py` | T-26 | 95 肌肉固定表、手指名映射、部位、库 B 关节组 |
| `pose_frames.py` | T-26 | 姿势帧库 `pose_library.json` |
| `pb_static.py` | T-30 | PhysBone 静态清单 `pb.json` |
| `pose_plan.py` | T-29 | 姿势×状态计划：每部件姿势子集、两趟、按秒预算分批 → `request_pose_<n>.json` |
| `decl_draft.py` | T-04 | 声明草案生成器（从生成器表/场景/厂商 clip/T4/素体档案/盘点起草 `声明.yaml` 草稿） |
| `decl_validate.py` | T-02 | 声明校验器（YAML→schema→SEM-01…24→`decl.json`） |
| `verdict.py` | T-14 | 校验器：声明 × T1/geo/写者 → `verdicts.json`＋汇总 |
| `rules_universal.py` | T-14 | 通用规则 U1–U7＋U-KF、构后改名后备解析（`verdict.py` 的共用件） |
| `thresholds.yaml` | T-14/T-18 | 阈值/单位/来源/达不到怎么办；几何项 `advisory` |
| `key_follow_verdict.py` | AM | 同名键失配判定；`verdict.py` 的 U-KF **直连调用它**（`load_states`+`build_result`） |

---

## 姿势库（T-26；实现 `muscles.py` + `pose_frames.py`）

```bash
python3 perception/pose_frames.py --selftest                 # 工程A 数据自验（约 50 s）
python3 perception/pose_frames.py --project <工程根>          # 写 <工程>/_感知/out/pose_library.json
python3 perception/pose_frames.py --envelope extreme ...      # 额外生成 HumanDescription ±1 档（默认不生成）
python3 perception/muscles.py --selftest                     # 95 名表 / 手指映射 / 库 B=66 条
```

### 三个库（03 §8.1）

* **库 A 真实静态姿势**：SDK `Packages/com.vrchat.avatars/**/ProxyAnim/*.anim` **全部 79 个**
  （其中 `landing`/`hands_idle2`/`empty`/`rotate90_right` 长度非零）；GoGo Loco 固定 7 条
  （装了才收）；**工程私有** = 头像描述符接到的控制器（descriptor 5 层 + `ModularAvatarMergeAnimator`
  并入，复用 `writers_static.ProjectScan`）里引用到的全部人形 clip，SDK/GoGo 包单独走上面两条
  固定清单、不重复计入。Additive 层（`AnimatorLayer.m_BlendingMode==1`）的 clip 标 `additive: true`，
  值是增量（基线按 0 算 `moved_regions`），由 T-27 叠加在 `stand_still` 上。
* **库 B 关节扫掠（恰 66 条）**：7 个左右分关节组 × {25,50,75,100}% × 左右 = 56；脊柱前屈
  4 档；6 组合（坐/深蹲/跪坐/抱胸/高举/盘腿）。剂量 = 其余肌肉取 `stand_still` 的值，被扫肌肉从
  `stand_still` 值向该方向的**库 A 包络极值**线性插值（agy D5：不用 HumanDescription ±1）。
  该方向在库 A 无位移时退反方向，记进 `stats.envelope_fallbacks`（工程A 为空）。
* **库 C 真动作 clip**：GM 自带 16 个多帧表情；GoGo `go_jump_in_place`/`go_knockback`/
  `go_manual_afk_idle`；声明 `poses.extra_clips`（未给则空）。同一「观察肌肉 argmax/argmin +
  `RootT.y` 最低帧 + `Foot Up-Down` 极值帧、L∞<0.05 去重、每 clip ≤6 帧」规则。

### 读法与关键约定

* 只读 `m_FloatCurves`（带 `attribute` 名），不读 `m_EditorCurves`。
* 手指名 `LeftHand.Index.1 Stretched` → `Left Index 1 Stretched`（显式映射，`muscles.clip_attr_to_muscle`）。
* 缺的手指曲线取 `proxy_hands_idle` 的值，**不填 0**；缺的身体曲线取 `stand_still`；additive clip 缺的取 0。
* 每条目 `{id, source, clip, frame, time, group, kind, muscles[95], root_t[3], root_q[4],
  builtin_params, moved_regions, tags, additive, …}`。
* `moved_regions` 离线 = 肌肉组 |Δ vs 基线| > 0.1 → 部位（I10）；T-27 在 Unity 里补算骨骼旋转差写
  `moved_regions_bones`。

### 一个实测更正

04 T-26 写「每 clip 49 肌肉＋7 Root 曲线，与 `genericBindings` 条数一致」并不普遍成立：
`genericBindings` 会含没有 float 曲线的**常量绑定**（本工程 proxy 里 `attribute==1/2` 各若干）。
判据改为肌肉**序号集合**相等——全部 79 个 proxy clip 都过（`attribute == 肌肉序号 + 42`）。
条数不一致只有 `proxy_land_quick 96/100`、`proxy_landing 96/100`、`proxy_sit_down 130/131`，
selftest 以 `[note]` 报出、不判失败。

### 95 名顺序的出处

Unity 2022.3.22f1 的 `HumanTrait.MuscleName` 在原生代码里，C# 拿不到；本表用
`genericBindings[].attribute == 肌肉序号+42` 对 79 个 proxy clip 做过集合自证（selftest 每次重跑）。
表内容与 Kafe_CVR_Mods `GrabbyBones/MuscleData.cs` 一致；手指 1,Spread,2,3 的顺序由
`HumanBodyBones`（Proximal/Intermediate/Distal）× `MuscleFromBone` 的 DoF 顺序决定。

---

## 姿势×状态计划（T-29；实现 `pose_plan.py`）

读 `decl.json`＋`pose_library.json`＋`inventory.json`＋`pb.json`＋`pose_timing.json`（T-27 实测，
缺席退默认 0.2/5.0/0.7 s），按 03 §8.4 决定「跑哪些 (状态, 姿势, PB 模式) 帧、量哪些件、花多少秒、
分几批」。**只规划，不测量**；不改工程。

```bash
python3 perception/pose_plan.py --selftest                    # 工程A＋假 pose_timing
python3 perception/pose_plan.py --project <工程根>              # 写 <工程>/_感知/out/
python3 perception/pose_plan.py --project <工程根> --out <目录> --total-budget-min 20
python3 perception/pose_plan.py --project <工程根> --pass1 <poke_patches.json>
```

* **配对**：只配 `moved_regions(pose) ∩ covers(part) ≠ ∅`。`covers`（`LeftUpperLeg/Hips/…`）经
  `COVER_TO_REGIONS` 映到 `moved_regions` 词汇（`thigh/knee/…`）；**`Hips` 同时算 `thigh`＋`spine`**
  ——否则 `MMN.pants`（只 covers Hips/Spine）会被漏配坐姿（`B_combo_sit`）。声明
  `parts[].pose_scope.include` 里的 pose 无条件加入（`kaguya.sailor` 强制 `proxy_stand_still`/`proxy_sit`）。
* **状态**：由 `menu`（outfit/slot/ctl）枚举每件的相关维度（自身可见性 ∪ 同区域它件可见性 ∪
  写者条件引用到的维度），按「同区域可见件集合 ＋ 生效写者集合」分等价类；再对全部
  (部件, 等价类) 做**贪心集合覆盖**取尽量少的全局代表状态。不可见件、没配到姿势的件不占状态。
* **两趟**：趟 1＝库 A ＋ 库 B@100%（含 6 组合）＋ 库 C 极值帧；趟 2＝库 B@{25,50,75}，**只对
  `--pass1` 命中的 (部件, 关节)**（也接受 `poke_patches.json` 风格列表，按 `region` 反查关节）。
* **PB**：`both` 只给有 PB 的件（`pb.json.parts[part].has_pb` 或声明 `parts[].pb`），其余 `rigid`。
  `pb.json` 无 parts 映射时**不猜**、记 warning 全按 `rigid`（工程A 的 T-30 因非活跃头像根为空）。
* **预算**：单帧成本＝稳定 ＋（settle 帧的）settle ＋ 烘焙×该帧可见件数；优先级
  库 A(0) ＞ B@100(1) ＞ C(2) ＞ 趟 2 低档(3)，`--total-budget-min` >0 时从低到高截断，
  每批 ≤ `--budget-min`（默认 20 min，R6）。输出 `request_pose_<n>.json`、`pose_plan.json`
  （每部件表＋状态表）、`pose_plan_skipped.json`（按 (部件, 姿势) 去重的被截断项）。

### selftest 判据与当前输出（2026-09-19）

①每部件表 48 件；②`kaguya.sailor` 无 B_hip/B_knee 扫掠且 `include` 生效；③`MMN.skirt`/`MMN.pants`
配 `B_combo_sit`＋髋前屈；④趟 2 只由假趟 1（`MMN.pants×hip_fb`、`MMN.socks×knee`）驱动，未命中件 0；
⑤预算先砍 C 再砍 B（只砍 C 时 B/A=0；再砍 B 时 A=0）。

```
[2] kaguya.sailor：covers=['Chest','UpperChest','Spine'] regions=['chest','spine','upperchest']
    趟1=170，无 B_hip/B_knee=True，含 proxy_sit=True
[3] MMN.skirt/MMN.pants 配坐姿：True / True（B_combo_sit=True）
[4] 趟 2（假趟 1: MMN.pants×hip_fb, MMN.socks×knee）：
    MMN.pants 趟2 6 条：B_hip_fb_L_25, B_hip_fb_L_50, B_hip_fb_L_75, B_hip_fb_R_25, …
    MMN.socks 趟2 6 条：B_knee_L_25, …；MMN.skirt 趟2 0 条（应为 0）
[5] 预算压缩：A=32984.8s B100=1517.1s C=25980.8s，帧 18329
    预算 34502.4 s：砍 C=7761 B=0 A=0     预算 32984.9 s：砍 C=7761 B=939 A=0
    预算 10 min：帧 112，批 1，砍 18217 帧（C=7761, B100=939, A=9517）
[汇总] 状态 73（覆盖需求 132）、趟1 姿势 285、帧 18329、估算 60482.7 s、批 51
ALL PASS
```

### 实测两处与 03/04 的偏差（T-29 报出，供 T-31/T-19 排期）

1. **库 A 是 155 条不是「≈33 条」**：T-26 把 SDK 全部 79 个 proxy 都收进 A（`library_a_pose` 标签 85
   条＋未打标 70 条），加 CERP 展开帧。全量趟 1 在 工程A 是 **18329 帧 / ≈16.8 h**，
   是 §8.4「200–250 帧」的 ~90×；**必须**用 `--total-budget-min` 截断，20 min 只够 233 帧（≈1 个状态）。
2. **`pb.json` 无 parts**：T-30 对 工程A 跳过了非活跃头像根，`both` 无处可给；T-27 的
   `pose_timing.json` 未产出前用默认耗时，数字仅供排序、不是承诺。

---

## 声明草案生成（T-04；实现 `decl_draft.py`）

从工程里**能读到的事实**起草 `<工程>/_感知/声明.yaml` 草稿，人只补 `human:` 项。
原则：**厂商写者一律 `confidence.correct: unknown`；拿不准的机制标 `human:`，不编。**
来源（03a §Q1-⑤ S1–S9）：

* **S1 生成器表**：`MenuGen*.cs` 的 `OUTFITS/OUTFIT_HIDE/PARTS/ACCPARTS/HEADPARTS/HAIRS/
  EARTAILS/HALOS/HEADDRESSES/PART_SHAPES/CHEST_PARTS/VENDOR_CLIP/VENDOR_ALT/CONFLICTS`
  ＋ `Suppress`/`ShowInRange` 调用。
* **S2 场景/prefab**：MA ShapeChanger / BlendshapeSync / ObjectToggle（复用 `writers_static`）。
* **S3 厂商 clip**：`VENDOR_CLIP` 指向的 `<件> ON/OFF.anim` 曲线。
* **S7 T4 `params.json`**：参数默认值（`menu` 段仍以生成器表为准）。
* **S9 素体档案/片段**：`Kaguya.yaml`（baseline/键类别/厂商惯例/alt_pieces）、`*.decl.yaml`。
* **T-05 盘点**：`inventory.json`（covers/closed/切换方式/渲染器路径）。

```bash
python3 perception/decl_draft.py --project <工程目录> --out <草案.yaml> \
        [--profile <素体档案.yaml>] [--inventory <inventory.json>] [--params <params.json>] \
        [--scene <场景.unity>] [--menu-gen <MenuGenA2.cs>]
python3 perception/decl_draft.py --selftest        # 对 工程A 起草并与人写声明比对（只读工程）
python3 perception/decl_draft.py --selftest-blind  # 盲起草预演（git show ceb4070b^ 的旧源，只读 git）
```

临时文件写 `_长程任务_20260918/派工/tmp/ai/`；`--selftest` 会顺带调 `decl_validate.py` 验草案。

### selftest 判据与当前输出（2026-09-19，C-K 补严格口径；CK2 落实 B-T04b 六条裁决）

`--selftest` 用 工程A 真工程起草，再跑 `decl_validate.py` 与人写声明比对
（只读工程、只写 `派工/tmp/`）。**验收口径**（04 §T-04，B-T04 签字）：
草案过 `decl_validate.py` **0 error**；`parts` 件覆盖率 ≥90%；D1/D3/D4a/D6 一致性
双口径 ≥80%——口径 A（旧）= kind＋目标重叠，口径 B（严格）= kind＋**目标集合全等**
（按对象路径）＋when 同＋expect 同（含下表规范化与 CK2 裁决的排除项）。

判定依据（CK 裁决 1，写进验收口径）：**草案只读工程事实，不读自己的下游产物**。
B-T07a 把生成器表/层搬进 `_感知/声明.yaml` 后，像 `PART_SHAPES`、`CHEST_PARTS`/
`SK_NIPPLE` 与三条 `SuppressBoolGated` 的事实，在 `MenuGenA2.cs`/场景/clip 里已不存在；
唯一还写着它们的是 `Gen/Clip/Decl_*.anim`、`gen_writers.json`——那是本声明的**下游**，
读了等于抄答案。故这 5 条记 `human_only`、**不进严格口径分母**、单独列一行计数：
`RePoppin.shirt_under_parker`、`工程A.default_hat_hides_added_ear`、
`工程A.head_acc_hides_ears`、`工程A.hood_hides_head_items`、
`kaguya.nipple_hidden_when_chest_covered`（名单是 `decl_draft.HUMAN_ONLY_IDS` 数据常量，
不写进比较逻辑）。识别走声明条目自身的 `origin`/`human_only` 字段，退而扫
`source`/`note` 里的迁移标记；名单里有、声明里识别不出的在 selftest 点名「需 Claude
补标」，不猜。反证：`--selftest-blind`（`ceb4070b^` 旧源）能命中其中 3 条——不是草案
不会写，是当前源里这条事实已被 B-T07a 删。

```text
[selftest] draft -> .../派工/tmp/ai/draft_工程A.yaml（parts=58 deps=16 includes=2）
[selftest] decl_validate(draft): OK（0 error）
  件覆盖 40/42 = 95.2%（阈值 90%）
  kind  A 人写          A 草案          B 人写          B 草案
  D1    3/3           4/4           3/3           3/3
  D3    3/4           3/3           2/3           3/3
  D4a   2/3           2/2           2/2           2/2
  D6    4/7           4/4           1/3           2/4
  A 旧口径：人写命中 12/17 = 70.6%；草案命中 13/13 = 100.0%
  B 严格口径：人写命中 8/11 = 72.7%；草案命中 10/12 = 83.3%（均阈值 80%）
  human_only（迁移，不计分母）5 条：RePoppin.shirt_under_parker 工程A.default_hat_hides_added_ear 工程A.head_acc_hides_ears 工程A.hood_hides_head_items kaguya.nipple_hidden_when_chest_covered
  被取代（不计分母）1 条：MMN.socks_foot_flat
  pending_cleanup（不计精确率分母）1 条：d1.kaguya_outer_sailor_shrink
  草案佐证（计入命中）0 条：—
  未命中且未分类（非迁移/非取代，逐条交 Claude 裁决）：工程A.holeheel_foot_hiheel 工程A.holeheel_hides_shoes 工程A.holeheel_shown
[FAIL] 覆盖率或一致性未达标
```

> **当前工作树还有 3 条 2026-09-19 未提交的 HoleHeel 声明条目**
> （`工程A.holeheel_{shown,hides_shoes,foot_hiheel}`，A-工程A-15/CL 在做），
> 草案尚无对应规则，故落到「未命中且未分类」。去掉这 3 条（回到 CK 的 14 条人写集），
> 严格口径为 **人写 8/8 = 100%、草案 10/12 = 83.3%**。它们 source 里没有迁移标记，
> 不是 B-T07a 迁移，按裁决 1 不纳入 `human_only`——列表交 Claude 裁定，不猜。
> CK 的 9 条逐条差异与证据见 `_长程任务_20260918/派工/tmp/ck/diff_9.md`。

#### 严格口径的比较规则（语义等价、文本不同才归并；目标集合仍要求全等）

1. **cases 展开**：带 `cases:` 的 dep 用每条非 `dont_care` case 的 `(when, expect)` 作比较
   单元，`else`/`dont_care` 不参与。人写常把守卫放 `cases`、顶层写 `when: true / expect: null`。
2. **when 布尔规范化**：顶层 `|` 拆析取集合、子句内 `&` 拆原子集合并排序、去多余括号、
   `and`→`&`、`{...}` 内排序。`vis(a) and vis(b)` ≡ `vis(b) & vis(a)`、
   `outfit in {B,A}` ≡ `outfit in {A,B}`。
3. **when 析取覆盖**：人写 `A|B` 可由草案 `A`、`B` 两条共同覆盖；反向草案一条被某人写条
   的析取集合包含即命中。**每条覆盖仍须 kind／目标集合／expect 全同**。
4. **expect 规范化**：`100` ≡ `100.0`；省略 `tol` ≡ `tol: 0.5`（schema 默认）；其余键
   （`class`/`deleted`/`hidden`/`shown`…）原样比，不丢。
5. **件类别别名（CK 裁决 2）**：厂商素体自带的外套开关 clip **同一 clip 里
   `outer_shlink` 与 `outer_shrink` 两个键都在**，profile `key_classes.shrink` 只收了
   后者。`shlink` 是厂商拼写，按别名处理，与 `shrink` 同义补 `expect.class`（草案生成
   与比较两侧一致）；证据见该 clip（每档两键都有曲线）。
6. **部件身份按对象路径（CK 裁决 3）**：目标 `part: <id>` 与 `when` 里 `vis(<id>)` 先经
   各自声明的 `parts[].objects[].path`（规范化后的根相对路径）解析成路径集合再比；
   id 文本不同、路径相同即同一件（人写 `Kitty.shirt_a` ≡ 草案 `Kitty.kaguya_shirt_big`）。
   声明里查不到该 id 的才退回 id 文本。
7. **可见件过滤（CK 裁决 5）**：比较 targets 前，用声明里的 `outfit` 显隐关系，把 when
   条件下**必然不可见**的件从两边剔掉（hood 类「不可见件不列」）。保守判定：某件有显式
   outfit 档、而 when 每个析取子句都把 outfit 限到与它不相交的档（且无 `vis(<该件>)`）才
   剔；拿不准就保留。**已知局限**：只用到 outfit 档，不建模 `ctl(...)` 开关层，比人写的
   语义口径略粗（例：hood 条目里人写保留的 `Kitty.cat_ear` 会因 outfit=Kitty 档被剔）；
   该条目是 `human_only`，不影响当前数值。
8. **被取代条目不进分母（CK 裁决 4）**：人写后条 `supersedes: [前条]` 时，前条
   （`MMN.socks_foot_flat`）不进严格口径分母。
9. **迁移条目不进分母（CK 裁决 1）**：见上「判定依据」，5 条 `human_only` 单独计数。

**草案侧两条（CK 裁决 6）**：场景里待清的旧冗余 SC（`d1.kaguya_outer_sailor_shrink`，
A-工程A-12 在清）标 `pending_cleanup`、不进精确率分母（`PENDING_CLEANUP_IDS`，标在
`note` 上，schema 无此字段）；草案多出条目若与某条 `human_only` 迁移条目 when 等价、
targets 重叠 ≥80%（Jaccard），记「草案佐证」计入命中，否则单列。工程A 当前无佐证
条目——`d6.layer_1/2` 的 when（`ctl(hair)`/`ctl(head)`）与 5 条迁移条目都不等价，单列。

* `--selftest-blind`：用 `git show ceb4070b^` 的旧 `MenuGenA2.cs` + 场景起草，
  `MMN.socks_foot_flat` 仍能以 `when='vis(MMN.socks)'` 出现、备选外套带 `human:` 说明，
  草案过校验 0 error——对应 **E11 盲起草**（完整版在 T-16 做）。旧源还能出
  `d4a.RePoppin_shirt_Parker_on` / `d6.layer_4/5`，是「迁移条目不可自动」的反证。
* **已知取舍**：T-05 盘点只导 SMR、不导 MeshRenderer，PixelBoot 的 `windowA–E` 在 prefab
  实例内部拿不到全路径，这类选择器记进草案头「未解析选择器」。厂商写者的
  `correct` 一律 `unknown`，需人判。片段件 `frag_parts` 已保留 `slot/fit/covers/toggle`
  （来自 `开发工具/素材包说明/*.decl.yaml`），按 slot 聚合的规则不再漏片段件。

---

## 声明校验（T-02；实现 `decl_validate.py`）

```bash
python3 perception/decl_validate.py --selftest                 # 正例 8/8、反例 250/250（约 2 s）
python3 perception/decl_validate.py --selftest --mini-yaml     # 同一批，强制走自带 YAML 解析
python3 perception/decl_validate.py --in <声明.yaml> [--report json]
python3 perception/decl_validate.py --in <声明.yaml> --out <工程>/_感知/decl.json
python3 perception/decl_validate.py --in <声明.yaml> \
        --profile 开发工具/素体档案/Kaguya.yaml \
        --inventory <工程>/_感知/out/inventory.json \
        --pose-library <工程>/_感知/out/pose_library.json
```

校验顺序与 `schema/CONDITION_GRAMMAR.md` 对齐：**YAML 载入 → schema（不过就不跑语义层，§8）→
includes 合并 → SEM-01…SEM-24 → 展开 decl.json**。

### 素体全量键表（任务 AQ；实现 `profile_keys.py`）

SEM-07 要的「身体键存在」不该只看 `key_classes`（那是 T-17 已分类子集），而应来自身体网格本身。
T-05 盘点现在每个头像输出 `body_keys`，本脚本把它落到档案新段 `all_keys:`：

```bash
python3 perception/profile_keys.py --inventory <工程>/_感知/out/inventory.json \
        --profile 开发工具/素体档案/Kaguya.yaml
python3 perception/profile_keys.py ... --force     # 已有 all_keys 且不同时强制覆盖
python3 perception/profile_keys.py --selftest      # 临时文件，不碰仓库
```

* 只动 `all_keys:` 这一段：首次追加到文件末尾，已存在则按「顶层行 + 其后缩进行」精确替换，
  其它字节与 YAML 注释一字不动；键序 = 网格顺序，重复运行字节一致。
* 已存在且与盘点不同：默认**只报告差异、不覆盖**（退出码 2），`--force` 才写——档案是多人改的，
  静默覆盖会抹掉人工补的键。
* 头像选择：`--avatar` 优先；否则用档案 `mesh` 匹配盘点 `body_path`（或路径基名）；再否则取第一个
  有 `body_keys` 的头像。
* 不依赖 PyYAML（按行读 `mesh:` 与 `all_keys:`）；`all_keys` 是 list 才被 SEM-07 认，空表代表
  「身体确实没有键」。

### 载入与退路（取舍）

* **PyYAML 在就用 PyYAML**：`SafeLoader` 保留 YAML 1.1 的 `on/off/yes/no` 布尔、裸 `1.06` 浮点，
  只**去掉 timestamp 隐式解析**——`2026-09-18` 一律按字符串载入（否则 schema 的 `date` 全崩）。
  因此裸日期/裸 `1.06` 仍是给读者看的陷阱：声明里字符串一律加引号。
* **无 PyYAML 时退到自带 `_MiniYaml`**：只覆盖声明/片段用到的子集（注释、块映射/序列、行内与
  跨行 flow、引号与 `\"` 转义、YAML 1.1 标量），不支持锚点/标签/多文档/多行标量 `|`/`>`。
  该路径由 `--mini-yaml --selftest` 每次自验，当前 8+250 全过；不保证覆盖声明之外的 YAML。
* **jsonschema 在就用**（Draft 2020-12）；不在时 schema 层报 `SKIPPED`、`--out` 不写 decl.json，
  只跑语义层。报错路径按 §8 规范化：`context` 递归展开取叶子、`required` 补缺名、
  `additionalProperties` 补多出的键、`propertyNames` 补出错的键名。
* **姿势库**：按 `avatar.project` 自动找 `<工程>/_感知/out/pose_library.json`（也认
  `*<project>*/_感知/out/`）；找不到就按 GRAMMAR §3 的内置清单（SDK 79 + GoGo 7+3 + 库 B 66+30
  + GM 16）核 id 与 tag。工程私有 clip 离线查不了，只出警告。

### 语义规则（GRAMMAR §5）与「skipped 不是 pass」

SEM-01…SEM-24 全部实现，报错路径按 §5 表；片段单独校验只跑片段内可判的规则
（SEM-01/02/03/04/05（mesh 除外）/06/09/10/11/13/19），报错路径是片段自己的；被声明引入时
片段的错报成 `/includes/<i>/fragment#<片段内路径>`，不合格的片段不合并。

* **SEM-07（素体档案）/ SEM-12（T-05 盘点）依赖外部数据**：不传 `--profile` / `--inventory`
  时状态是 **skipped**（不是 pass），报告里单列。
  **SEM-07 两档口径**（任务 AQ）：档案有 `all_keys:`（T-05 `body_keys` 落下来的身体网格全量键表）
  时，声明里目标为身体网格的键**不存在 → error**，`key_classes` 只用于分类；没有 `all_keys` 时
  维持旧口径——键缺失只降为**警告**（素体档案还没有 schema，见 CHANGELOG「遗留问题 2」），存在性
  取自 `key_classes` + `baseline` + `keys`。SEM-12 只核对 `objects[].path` 是否在盘点、`type` 是否
  与 `renderer`（smr/mesh）一致、`submesh` 是否小于材质槽数，不因 `part_like` 跳过。
* **SEM-21 只警告**（fit 为 closed/tight 但 covers 空）；ok 例子允许警告，不允许 error。
* **SEM-22 期望冲突**是唯一做状态枚举的规则：按 (网格, 键) 分组，**按 §6.1 枚举全部维**
  （`outfit/slot/ctl/axis/param/pose` 的笛卡尔积；实测状态数 工程A_min 8064、03a_工程A
  6720、03a_milfy 1040、03a_project-c 256、03a_h3 3），可见性用 §2.2 的 E（含 hidden/shown
  单趟修正），逐条 dep 求值，不剪枝。只有状态数 >50 万时才退到「只枚举手头这组 dep 用到的维」
  并在报告里注明（当前例子都不触发）。比较区间型（`value±tol`、`range`、`values` 里该键、有档案
  时的 `baseline±0.5`）与显式 `class`；命中时报在展开顺序靠后的那条 `/deps/<j>/id`。连续维取样
  见 §6.1（临界点＋相邻中点＋边界，空常数缺省 `{0, 0.5, 1}`；body 轴再并上 `samples`）。
* `supersedes` 取代的 dep 不进期望矩阵；`decl.json` 里保留并加 `superseded_by`。

### decl.json（确定性）

`json.dumps(..., ensure_ascii=False, sort_keys=True, indent=2)`；数组按 id 排序。展开按 §6：
includes 合并（局部 id 加 `<as>.` 前缀、条件/target/alt_of/expect_by_leader 键同步改写、
`objects.path` 拼 `mount/`、片段部件写入 include 的 outfit、片段 dep 缺 else 补 `dont_care`）、
geo_defaults 生成 `geo.<件>` / `.opening` / `.poke`（区域按叶子算，手写同 id 覆盖生成项）、
supersedes 标注、缺省写实（`when`、`else`、`tol`、`poses`/`render`/`geo_defaults`/`roundtrip_default`）、
每条带 `origin`（生成项带 `generated_from`）。同一输入两次输出字节一致（selftest 每个正例都比）。

### selftest 判据

头三行 `# rule:` / `# layer:` / `# expect_error_path:` 是判据：`layer: schema` 要求被 schema 拒
且期望路径 ∈ 规范化路径集合；`layer: semantic` 要求 schema 先通过、语义层**只命中头注释那一条**
SEM 规则、且报出期望路径。当前输出：

```
ok files: 8  ok failures: 0   bad files: 250  bad mismatches: 0
ALL PASS
```

---

## 校验器（T-14；实现 `verdict.py` + `rules_universal.py` + `thresholds.yaml`）

声明说「应该怎样」、T1/geo/写者说「实际怎样」，本器对账并归因，是「不靠看图」的判定核心。
它**独立展开期望矩阵**（不读 `gen_writers.json`，只用它归因）；输入缺席时对应判定降级 `no_data`
并单列，**不报 pass**。

```bash
python3 perception/verdict.py --selftest                 # 仓库内 工程A 数据自验（83 状态）
python3 perception/verdict.py --selftest --out <工程>/_感知/out/verdicts.json
python3 perception/verdict.py --decl <工程>/_感知/decl.json --t1 <T1 目录> \
        [--profile 开发工具/素体档案/Kaguya.yaml] [--geo <geo_*.json|目录>] \
        [--writers writers.json] [--ma-analysis ma_analysis.json] \
        [--fx-final fx_final.json] [--mapping mapping.json] \
        [--inventory inventory.json] [--pb pb.json] [--key-follow key_follow.json] \
        [--thresholds perception/thresholds.yaml] [--out verdicts.json]
python3 perception/verdict.py --diff a.json b.json       # 两次运行 diff
```

### 期望与判定形式（对齐 schema `outcome`）

`baseline`｜`dont_care`｜`{value, tol}`｜`{range}`｜`{values}`｜`{class}`｜`{sync}`｜`{hidden|shown}`｜
`{deleted}`｜`{variant}`｜`{geo}`｜`{grab}`｜`{not_written}`｜`{no_writer_other_than}`｜`{pending}`。
判定可出 `pass / violation / no_data / undecidable / unmatched / dont_care`；判定覆盖率 =
已判 /(已判+判不了)，`dont_care` 不计。

### 依赖输入缺席时的降级（硬要求）

| 判定 | 需要 | 缺席时 |
|---|---|---|
| 键值/基线/同步/显隐/变体/grab | T1 `state_*.json` | 无 T1 → 没有状态可判，报告为空 |
| `not_written` / `no_writer_other_than` / U3 归因 | `writers.json`（T-11） | `no_data`（不猜宿主） |
| `deleted`（Delete 比例） | T1 v4 V4 桶/键存在表（T-13） | `no_data` |
| `geo.*` / U1 静态斑块 | `geo_*.json`（T-10/T-28a） | `no_data`（advisory 期本就不进卡口） |
| U6 顶点数 | T1 v4 | `no_data` |
| U7 | `pb.json`（T-30） | `no_data`；规则本身只报 `info` |
| 冻结四分（frozen/frozen_meaningless） | `mapping.json`（T-12） | 退化为 存在/写0/不存在；报告单列 |
| 胜者归因（MA 段） | `ma_analysis.json`＋`fx_final.json`（T-12） | 只报写者集合与静态胜者，标 low |

### 通用规则（与声明无关）

U1 静态穿出斑块（T-28a，advisory）｜U2 两件重合 <50%｜U3 无写者回基线｜U4 抓取点（命中数 =
`hidden_materials` 条数；`grab_point_lt_3000` 只记 info）｜U5 权重 0–100｜U6 顶点数不变｜
U7 PB 碰撞体（`info`，归因线索）｜**U-KF 同名键失配**（见下）。

### U-KF 同名键失配（任务 AO 规格）

输入 `--key-follow`（T-05/AK 的 inventory 或 key_follow JSON）：件带身体同名键、**件可见时**
`|件值 − 身体值| > 阈值（thresholds `U_KF.mismatch_tol`，默认 5）` → violation；遍历全部 T1 状态，
无重叠记 `benign`，件在所有状态不可见记 `no_data`，件/键名解析不上记 `unmatched`（不猜）。

**直连 AM（已交付）**：`verdict.py` 检测到 `perception/key_follow_verdict.py` 时优先调用其
`load_states(t1_dirs)` + `build_result(inventory_path, t1_dirs, states)`（也认自定义
`analyze(key_follow, t1_dirs)`）；调用失败或模块缺席才退本模块内联实现（判据相同，见
`rules_universal.key_follow_verdict`）。findings 带 `source` 字段标明走了哪条路
（`key_follow_verdict.py` / `verdict.py:inline`）。当前 selftest 走 AM：FootNail 21 态、
stocking 33 态，两条 `benign`。

**B-补-07 几何加权（BF 返工）**：`key_follow_verdict.py` 接 AY 的 `candidates[].geom`
（`AuditPartInventory.AttachFollowGeometry`）。数值失配时再看几何：
`geom.body_piece_dist_mm.p50_delta_mm`（件到身体表面最近距离 p50，身体键 0→100 的差）与
`geom.piece_key_disp_mm.max`（件自身该键 0→100 的最大顶点位移）都 < `GEOM_BENIGN_MM=1 mm`
→ 降 `benign_geometry`；任一 ≥ 阈值 → 维持 `mismatch`；`geom` 缺席/`available=false`/无可比
数值 → **维持数值原判**并标 `no_geometry=true`。原数值判定另存 `numeric_verdict`，几何明细
在 `geometry`（含 `geometry_source`）。阈值来自实测：工程D harness p50 恒 5.8 mm（delta 0）
判 benign_geometry；乳贴修前 5.74→14.95 mm（delta 9.21）判 mismatch。summary 增
`benign_geometry` / `no_geometry` 计数，表格增几何列与 `benign_geometry` 节。

### 构后改名后备（没有 `mapping.json` 时）

声明里的源名用后备匹配实测名，匹配不上记 `unmatched`：路径按 `$<n>` 去尾、`$`→`/` 归一后
做「声明段是实测段子序列」匹配（覆盖 `_Outfit$Outfit_MMN_黑$164/Shoes`、`$$AAO_AUTO_MERGE_SKINNED_MESH_n`）；
键名按 `AAO_Merged_<键>_<n>`、`<n>_<身体名>__<键>`、`__<键>`、`_<键>` 逐级匹配。多义即 `unmatched`。

### 可见性归属：归属不了 → `undecidable`（B-补-12，BF 返工）

`dep.when` 与 `variant` option 的 `when` 都用 **T1 实测可见性** `sv.eval_vis()` 求值，不拿开关值推
（AO 教训 3）。实测可见性按「可归属」三条口径算（`StateView._resolve_parts`）：

1. **独立渲染器**：件可见 = 其任一自有渲染器 `visible`；
2. **只命中 AAO 合并网格**：AAO 只合并 activeness 动画相同的网格，命中块可见性一致才可判；
   有的块可见、有的不可见（如全脱态 `Kitty.shirt_a/b` 命中 `..._0` 可见、`..._1` 不可见）→ 归属不了；
3. **一件多物体**：各物体结论不一致也算归属不了（如 `RePoppin.parker` 的 `(A)Parker` 不可见、
   领带 `(A)Necltie` 可见——按「任一物体可见」会把领带当成外套盖胸）。

**归属不了只落 `undecidable`，不许按不可见判 pass/fail**（BF 返工，取代 AX 的「`vis()` 取
False 走 `else`」）：`vis()` 仍返回 False，但 `verdict.py` 把 `sv.vis_unknown()` 传给
`rules_universal.eval_decl_dep(..., unknown=...)`，条件按三值逻辑求值（`eval_cond_3`）——
`vis`/`chain` 任一 True→True，否则任一 unknown→`None`，`not/and/or` 按 Kleene 短路。
`when`/`cases.when` 求到 `None` 即返回 `UNDECIDABLE`，`judge` 落 `undecidable`；直接比
`visible(pid)` 的 baseline/隐显/variant 判定也先查 `vis_unknown()` 再判。报告新增
「undecidable 清单」（`summary.undecidable` + `summary.visibility_unknown`），归属不了的件
只在里面，禁止查无此人。效果（工程A 83 状态 selftest）：`kaguya.nipple_hidden_when_chest_covered`
4 个全脱态（KittyA/B、RePoppin、RePoppinHood）三键各 3 行落 `undecidable`；`Kitty.shirt_a/b`、
`kaguya.outer_big`、`RePoppin.parker` 出现在 undecidable 清单；`kaguya.outer_variant_by_bust`
因组内 `kaguya.outer_big` 归属不了，83 态全部 `undecidable`（数据缺口，不再按假设判）。真缺陷
`Kitty.base_panties_hidden` 12 条不受影响。

### selftest 判据与当前输出（2026-09-19 BF 返工后）

`--selftest` 用 工程A 的 `t1_full_probes`（83 状态）＋ T-03 声明跑，断言：
外套关闭 14 状态三键 pass；MMN 修后四组合 pass；抓取点/重合 U2/U4 0 命中；**B-补-12 归属不了
落 `undecidable`（KittyA/B、RePoppin、RePoppinHood 三乳头键各 3 行 `undecidable`，相关件在
undecidable 清单里）**；03 §4.5 负样本清单逐条 0（鞋袜全关脚型键不写、**Parker 不可见写 100
无害——B-补-13 遍历 57 个实测样本＋合成样本证明判据非空转**、Kitty/RePoppin 无身体键、83 状态
抓取/重合 0）；并打印判定覆盖率、`no_data` 清单与 `undecidable` 清单。当前：判定行 8705，
pass 2514 / violation 12 / 判不了 4311 / dont_care 1878，覆盖率 37.0%。那 12 条全是
`Kitty.base_panties_hidden`（T-06/T-07 未落地时的应报项）；乳头键/领带那 14 条在 B-补-12 后
不再是 violation，改为按归属不了落 `undecidable`。

### 回放正样本补跑（T-16 后）

T-14 交付时 T-15 回放库与 T-16 那次 Play 未跑，故「4 条正样本全部 violation 且 `writer_blamed`
正确」暂缺。补跑方法（T-16 时由 Claude 执行）：

1. `replay.py apply --all` → 重跑生成器 → 进 Play 采 T1 v4/geo/截获 → 退 Play；
2. `python3 perception/verdict.py --decl <工程>/_感知/decl.json \
      --t1 <修前 T1 目录> --geo <修前 geo 目录> --writers <writers.json> \
      --ma-analysis <ma_analysis.json> --fx-final <fx_final.json> --mapping <mapping.json> \
      --key-follow <key_follow.json> --out <工程>/_感知/out/verdicts_before.json`；
3. `replay.py revert --all` → 同批再跑一次写 `verdicts_after.json`；
4. 判据：`verdicts_before` 里 4 条回放缺陷全 `violation` 且 `writer_blamed.winner` 正确；
   `--diff verdicts_before.json verdicts_after.json` 显示 4 条消失、修后 0 违例。

### 待办（T-32 姿势增补）

期望矩阵加 pose/pb 维、读 `pose_*.json`/`poke_patches.json`、PB 解释表（✗/✓ 信息、✗/✗ 违例、
✓/✗ `pb_induced`）、`static_grown`/`opening_deep`/`pose_changes_state` 归 advisory、`waivers` 加 pose id
——按 T-32 增量接线；当前 U7 与 `waivers.pose/pb_mode` 字段已能读入但不参与判定。

---

## key_follow 盲区补检（B-补-06；实现 `key_gaps.py`）

`key_follow` 只查「件**自带**身体同名键、却没人驱动」。它对另两类形态键缺陷天然失明：

* **件上缺键**：工程D Rurune-Black 鞋缺平脚键（B1）、乳贴缺 `Breast_small` / `Breast_big(limit)`
  （B2/B3）；
* **写者挂错件**：工程A MMN 平脚键挂在袜子上（A3）、工程B垂耳兔 11 个收缩键挂在整套根上（R1）。

`key_gaps.py` 用离线 inventory（`审查产出/key_follow/<工程>.json`）补这两类检查，只读、不启 Unity：

```bash
python3 perception/key_gaps.py --inventory <...>/COMM-xxx.json [--out gaps.json] [--md gaps.md]
python3 perception/key_gaps.py --all <key_follow 目录> --out gaps_7.json --md gaps_7.md
python3 perception/key_gaps.py --selftest
python3 perception/key_gaps.py --requests     # 打印对 AuditPartInventory 的需求清单
```

判据（全部 `advisory`，需人判；BF 返工后**覆盖部位以 inventory `covers` 为准**）：

* **覆盖部位**：`foot` → `LeftFoot/RightFoot/LeftToes/RightToes`；`bust` →
  `Chest/UpperChest/Spine`。`covers=Other/unknown/空` 的件**不参与判定**，另进
  `unknown_cover` 单列（B-补-18 的 MA MergeArmature covers 映射重导后才有具体部位）。
  件 slot（path/name token）只用于 `unknown_cover` 分组，不再当判定依据。
* `missing_key`：对每个「有件级、且该件确实覆盖该键部位」的身体被写键 K，覆盖同部位的件里
  既非 K 宿主、也不在 `synced`/`candidates` 里的报缺键（键在件上只是没人写的归 key_follow）。
  没有「覆盖该部位的件级宿主」时不报，避免把本来不需要该键的件全报一遍。身体渲染器
  （`body_path`）不算「该带键的服装件」。
* `misplaced_writer`：**只报宿主不在任何覆盖该键部位的件上的情况**——① 宿主是**祖先/根或
  MA 控制物体**（路径不是渲染器）→ 挂错（R1，confidence=high）；② 全部宿主件都不覆盖该
  键部位、而某个宿主件覆盖已知的其他部位 → 该宿主挂错（A3，confidence=mid）；只要有一个
  宿主在覆盖件上，就认为键挂对了地方，不再对同键的其它宿主报挂错（避免「袜子也需要这键」
  误报）。覆盖未知的宿主不报、单列。输出三张表都**按置信度 high→mid→low 排序**。

`--selftest` 两路取证：① 手工最小 fixture（带 covers）精确复现 B1/B2/B3/A3/R1、负样本
（键同时挂鞋与袜）0 误报、`unknown_cover` 单列、置信度排序；② 真数据「撤销已修」——现有
inventory 是**修后版且 covers 还是 Other**，离线既没有修前 inventory 也不能重跑 Unity，故在
工程D/工程A/工程B真数据上：先按 B-补-18 重导后的形态补 covers，再删掉已知的修复
（`ugly_shoes` 的 SC、乳贴 `Breast_small` 宿主、MMN `Shoes` 的 SC、11 收缩键换回整套根宿主）
当修前等价物，B3 本就是修前。5 例全部命中，且 工程A 修后 `MMN/Socks` 不再报挂错。

### 当前 0/0 的原因（covers 未知）与 B-补-18 生效后的复验

现版 7 单（旧 inventory，covers 仍全 `Other`）跑 `key_gaps.py --all` 得
`missing_key 0 / misplaced_writer 0 / unknown_cover 354`。**这不是「无缺陷」**：件级覆盖部位
全部未知（`covers=['Other']`），`missing_key` 的「先有覆盖该部位的件级宿主」门槛与
`misplaced_writer` 的「宿主件覆盖与该键部位不相交」判据都无从成立，所有件被单列进
`unknown_cover`、不计入判定。0/0 = 「工具按设计拒绝在覆盖未知时下结论」，不是数据干净。

B-补-18 的 MA MergeArmature covers 映射**要用新工具重导 inventory 才生效**。复验步骤与预期：

1. 打回修前：`replay.py apply b1_rurune_flatfoot b23_esmera_nipple r1_lopear_shrink mmn_foot`
   （apply/revert 前先过「回放清单文件脏就停」闸门）。
2. `sync_audit.py` 同步新工具进 工程D / 工程B / 工程A；Unity 批量导出到
   `_长程任务_20260918/审查产出/key_follow_replay/`（命令见下条步骤书）。
3. `key_gaps.py --all <该目录> --out ... --md ...`，再逐工程核对 `covers` 是否已不再全 `Other`。

| 缺陷 | 工程·件·键 | 预期类别 | 从数据读的判据 |
|---|---|---|---|
| B1 | 工程D Rurune-Black 鞋 缺 `Foot_heel_OFF…` | `missing_key` | 鞋 `covers` 含 Foot/Toes 却不是宿主 |
| B2/B3 | 工程D Esmera 乳贴 缺 `Breast_small` / `Breast_big(limit)` | `missing_key` | 乳贴 `covers` 含 Chest/UpperChest/Spine |
| A3 | 工程A MMN 平脚键挂袜 | `missing_key`（鞋）**或** `misplaced_writer`（袜） | 读导出 `covers`：袜含 Foot→鞋报缺键；袜只含小腿→袜报挂错。**不预设类别** |
| R1 | 工程B垂耳兔 11 收缩键挂整套根 | `misplaced_writer`（high） | 宿主是祖先/根，不是任何盖住该部位的件 |

A3 的预期是从导出 inventory 的 `covers` 读出来的判据（步骤书第 6 步打印实际覆盖件并接受
两类任一），不是夹具里「袜子只盖小腿」的假设。完整逐条命令见
`_长程任务_20260918/派工/tmp/bo/BF_B补06_replay步骤_修正.md`；BF 原版
`tmp/bf/BF_B补06_replay步骤.md` 有 heredoc 变量不展开、缺脏树闸门、A3 预期依赖夹具三处错，
BO 已修（干跑输出在 `_长程任务_20260918/派工/tmp/bo/dryrun_*.log`）。

### B-补-06 需求清单：给 `AuditPartInventory` 补的数据（交 Claude）

1. **每渲染器的形态键名清单**（mesh 上实际存在的 blendshape）——把「件上真缺键」与「键在、只是没人写」
   分到渲染器级；现在只能用有无 `synced`/`candidates` 近似。
2. ~~衣物件的覆盖部位~~ **已做（B-补-18，BF 返工）**：`AuditPartInventory.RegionMapper` 按 MA
   MergeArmature 的 `mergeTarget` + 骨名（直接调其 `GetBonesMapping()`）把服装骨映射到头像人形骨；
   但**要重导 inventory** 才有具体 `covers`，旧数据仍是 `['Other']`。
3. **写者宿主的精确归属**：`body_written_keys[].writers[].component_path` 只有路径、且可能指向根/
   MA 控制物体；补「组件归属到哪个渲染器」，或补 transform 层级让离线能判祖先。
4. **件开关与身体键触发条件的对应**（现有 `switch.sources` 之上补「哪个档位需要该键 =100/0」），
   用于判「主件（鞋）缺写者」这类条件性缺陷。
5. **件的槽位分类**：仍按 path token 猜（`SLOT_RULES`），现在只用于 `unknown_cover` 分组显示。
6. **素体全量键表**（`开发工具/素体档案/Kaguya.yaml` 的 `all_keys:`，B-补-02）——判断身体是否存在该键。

---

## 90 剥离自检（T-23；实现 `strip_audit.py`）

交付前把审查残留从工程里清掉，并做零残留自检（规格 04 §T-23 / 作业清单 B-T23）：

```bash
python3 perception/strip_audit.py --project <工程根> --check      # 只查不删（退出码 1 = 有残留）
python3 perception/strip_audit.py --project <工程根> --apply      # 实删；ProjectSettings 还原到 --baseline（默认 HEAD）
python3 perception/strip_audit.py --selftest                      # 临时 fixture 全流程自检，不碰真工程
```

* **剥离项**：`Assets/AvatarAudit/`（+`.meta`）、旧 `Assets/Editor/AvatarAudit/`、
  `Assets/ZZZ_GeneratedAssets/`、`Packages/nadena.dev.ndmf/__Generated/`、
  `Library/AvatarAudit/`、`Packages/manifest.json` 与 `packages-lock.json` 里的
  `com.coplaydev.unity-mcp`、`ProjectSettings/` 相对基线的漂移。
* **只报不改**：`_感知/` 在工程根、不在 SOP 90 交付 5 项内（**不随工程 zip 交付**，随 git 留档）；
  场景/prefab 里的审查组件 `AuditMappingProbe` 等（构建期组件，发现即列路径交人处理）。
  注意 Unity YAML 里 MonoBehaviour 只写 `m_Script: {fileID: 11500000, guid: <脚本 guid>}`、
  **不写类名**，所以判据是「先收 `Assets/AvatarAudit/**/*.cs.meta` 的 guid，再按 guid 搜场景/prefab」；
  并且必须**先搜完再删脚本目录**（`--apply` 会把 guid 快照留到第二次 scan 用），否则脚本目录
  删掉后 `.meta` 没了，场景里遗留的组件就查不出来。**「删完再另起一次 `--check`」**时工作树
  `.cs.meta` 已随目录删掉，guid 改从 git 基线读（`git ls-tree` 列路径 +
  `git -c core.quotepath=false show HEAD:<路径>.meta` 读内容）；工作树与基线都取不到就报
  `undecidable` 且退出码非零，**不许报 ok**。`--selftest` 用真工程的 guid 与真 MonoBehaviour
  YAML 块做正样本，断言「删脚本目录后用删前快照仍能命中、现场重收 guid 命中 0」，并**另起进程**
  跑「删后 `--check`」（从基线取回 guid、仍报 RESIDUE）与「无 guid 来源 → undecidable」两例。
  `Captures/`、`Assets/Editor/AvatarGen/`（SOP 90 步骤 1 的清理项，脚本只提示）。
* **零残留判据**：`--apply` 后 `--check` 剥离项为 0；`git status` 里**白名单外**的 tracked 改动为 0
  （白名单 = 本脚本删/改的路径）。在 工程A 的副本上实测：`--check` 命中 6 项 →
  `--apply` 后残留 0、白名单外 tracked 0。
* 不启动 Unity、不改别的工程；`--selftest` 的副本放 `_长程任务_20260918/派工/_scratch/`（已 gitignore），
  `finally` 里删；不留在工作树（会被 `git add -A` 收进库）。


---

## T-11 静态规则候选（E-T11-01；实现 `static_rules.py`）

在既有的 `writers.json` 上离线跑 6 类规则出候选，**不重扫工程、不判对错**（对错要几何/构建期截获/人判；
03 §4.5「静态规则结果不进用户表」）：

```bash
python3 perception/static_rules.py --batch <审查产出/_历史工程> --md 静态规则候选.md   # 批量
python3 perception/static_rules.py --writers <writers.json> [--md one.md --json one.json]
python3 perception/static_rules.py --selftest        # 真数据已知样本（工程A / 工程B）
```

* **K1** 同键多写者（配置型 ShapeChanger/BlendshapeSync/ObjectToggle，标值是否不同）；
  **K2** 同键 Set/Delete 并存（markdown 行内 Delete 写者排在前且不折叠进「…(+N)」）；
  **K3** 档位/整套写者（`Dial_整套` 或同一 layer 多态选择器）
  与逐件/部位写者抢键；**K4** 收缩键目标是身体网格（挂套装根）；**K5** 脚型键 ShapeChanger
  归属（袜/鞋 token + `where` 回读）；**K6** 形态键目标值越界（只认 class_id 137，排属性路径）。
* **K5 的袜/鞋归属（验收 E-T11-01 返工）**：宿主经 `writers_static` 折叠到套装实例根后无区分力
  （工程A MMN 的 Socks/Shoes 都成 `_Outfit/Outfit_MMN_黑`），所以按写者 `where` =
  `<文件>:<行>` 回读该 prefab/场景，解析 ShapeChanger 所在 GameObject 名（stripped 顺着
  `m_CorrespondingSourceObject` 找源 prefab；源是 `.fbx` 只能给 `<文件名#fid>`）。两级都取不到
  **真名**时，结论字段 `sock_owner`/`shoe_owner` 一律**判不了**（`owner_unknown=True`）；按 `where`
  文件类型推的「厂商 prefab 写者=袜、场景补挂写者=鞋」只写进 `sock_owner_guess`/`shoe_owner_guess`
  （验收_20260919_BC至BH.md BG2：兜底猜测不许进结论字段），`owner_kind_source` 写明来源。
* `--selftest` 用**真工程**验证三个正样本：工程B垂耳兔 11 个 `Shrink_*` 挂
  `08_WhitePink_Milfy_MA`（K4）；工程B `Foot` 层 4 档与逐件 SC 抢键（K3）；
  工程A MMN 平脚键在**真修前场景**（git `ceb4070b^` 的 hardlink 影子工程，非手工删写者）
  标 `vendor_only=True` + `sock_owner_guess=True` + `owner_unknown=True`（「只挂袜不挂鞋」只能是猜测），
  live 则 `sock_owner_guess=shoe_owner_guess=True`、结论同样判不了。
  影子工程放 `派工/_scratch/`（已 gitignore），`finally` 删，不留工作树。
* **取舍/盲区**：`.fbx` 源的 GameObject 名在二进制里离线取不到（MMN 的 Socks/Shoes 即此），
  此时只给 `*_guess`，不冒充结论；14 历史工程 31 条 K5 里 19 条属此列（另 12 条按真名判）；
  确需语义级归属仍要回 Unity（`LoadAllAssetsAtPath` + `TryGetGUIDAndLocalFileIdentifier` 把
  fileID 映射回对象名）或读 FBX。
