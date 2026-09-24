# 条件表达式、姿势 id、往返序列与语义规则（perception/0.2）

> 配套 `perception-0.2.schema.json`（T-01，含 T-32 的 schema 部分）。schema 管结构、类型、词表、必填与互斥；**本页管 schema 表达不了的部分**：条件与往返序列的语法（EBNF）、求值语义与期望可见性模型、姿势 id 命名、引用完整性等语义规则（SEM-xx）、展开规则、反例头注释与报错路径约定。实现方是 `decl_validate.py`（T-02）。改动记录见同目录 `CHANGELOG.md`。
> 设计来源 03a Q1-①，以 `03_研究与方案.md` §3 更正清单与 §8（v3，22:30）为准。

## 1. 条件表达式 EBNF

用于 `deps[].when`、`cases[].when`、`expect.variant.options[].when`、`waivers[].states`。求值对象是「状态」＝菜单参数向量＋其它参数（VRChat 内置、厂商）＋体型轴＋姿势（历史由往返序列表达，不进条件）。

```ebnf
cond          = disj ;
disj          = conj , { "|" , conj } ;
conj          = unary , { "&" , unary } ;
unary         = "!" , unary | primary ;
primary       = "(" , cond , ")" | atom ;
atom          = "true" | "false" | vis_atom | chain_atom | slot_atom | outfit_atom
              | ctl_atom | param_atom | pose_atom | pose_tag_atom | body_atom ;
vis_atom      = "vis" , "(" , part_ref , ")" , [ "." , component ] ;
component     = "V1" | "V2" | "V3" | "V4" ;
part_ref      = "any." , ident | part_id ;
chain_atom    = "chain" , "(" , part_ref , "," , part_ref , { "," , part_ref } , ")" ;
slot_atom     = "slot" , "(" , ident , ")" , eq_op , bit ;
outfit_atom   = "outfit" , eq_op , label | "outfit" , "in" , "{" , label , { "," , label } , "}" ;
ctl_atom      = "ctl" , "(" , ident , ")" , eq_op , ctl_value
              | "ctl" , "(" , ident , ")" , "in" , "{" , ctl_value , { "," , ctl_value } , "}" ;
ctl_value     = label | slot_ref | bit ;
param_atom    = "param" , "(" , param_name , ")" , cmp_op , number ;
pose_atom     = "pose" , eq_op , pose_id | "pose" , "in" , "{" , pose_id , { "," , pose_id } , "}" ;
pose_tag_atom = "pose_tag" , eq_op , tag | "pose_tag" , "in" , "{" , tag , { "," , tag } , "}" ;
body_atom     = "body." , ident , "in" , interval ;
interval      = ( "[" | "(" ) , number , "," , number , ( "]" | ")" ) ;
eq_op         = "=" | "!=" ;
cmp_op        = "=" | "!=" | "<=" | ">=" | "<" | ">" ;
bit           = "0" | "1" ;
slot_ref      = "#" , digit , { digit } ;                 (* 槽号 i，从 0 起 *)
label         = quoted | bare_label ;
param_name    = quoted | bare_param ;
quoted        = '"' , qchar , { qchar } , '"' ;           (* qchar = 除 " 与换行外任意字符 *)
bare_label    = lchar , { lchar } ;    (* lchar = 除空白与 ( ) { } [ ] , | & ! = < > " : 外的任意字符；首字符不能是 # *)
bare_param    = pchar , { pchar } ;    (* pchar = A–Z a–z 0–9 _ / . $ # + - 及任意非 ASCII 字符 *)
pose_id       = kchar , { kchar } , [ "@" , digit , { digit } ] ;   (* kchar = A–Z a–z 0–9 _ 与汉字；不能整个是数字；@k＝多帧 clip 的第 k 个取样帧 *)
tag           = tchar , { tchar } ;                     (* tchar = A–Z a–z 0–9 _ *)
ident         = lower , { lower | digit | "_" } ;
part_id       = seg , { "." , seg } ;                     (* 声明里至少两段；片段里可单段 *)
seg           = idchar , { idchar } ;                     (* idchar = A–Z a–z 0–9 _ *)
number        = [ "-" ] , digit , { digit } , [ "." , digit , { digit } ] ;
```

- 词法：token 间空白忽略；运算符最长匹配（`!=` 先于 `!`，`<=` 先于 `<`）；裸词取最长。**一个裸词若整个匹配 `number`，它就是数，不是标签**——长得像数字的标签（如 `"1"`、`"2.5"`）必须加引号；`#` 加数字是槽号。
- 关键字 `true false vis chain slot outfit ctl param pose pose_tag body in` 只在原子开头位置有意义；部件 id 只出现在 `vis(…)`/`chain(…)` 里，所以唯一的保留是**首段 `any`**（`any.<kind>`）。`body.ears` 这样的部件 id 合法。
- 优先级：`!` ＞ `&` ＞ `|`，二元运算左结合；需要别的顺序就加括号。
- 引号：标签含空格或符号（`Petal Drape`、`NOEM 卫衣`）写 `outfit = "Petal Drape"`；参数名含空格或符号（`CERP Pose`、`Breast size`）写 `param("CERP Pose") = 1`。
- YAML：条件字符串一律加引号。裸 `when: true` 会被 YAML 解析成布尔，schema 按类型拒（`/deps/<i>/when`）。

## 2. 语义

### 2.1 原子

| 原子 | 含义 |
|---|---|
| `vis(p)` | 部件合成可见：∃ 物体 o∈p.objects，使 V1(o) activeInHierarchy ∧ V2(o) renderer.enabled ∧ V3(o) 未被材质整块遮罩 ∧ V4(o) 顶点保留比例 ≥0.5 全部通过 |
| `vis(p).Vk` | 单看第 k 分量是否「通过」：∃ o 使 Vk(o) 通过。用于查分量错配，如 `vis(p).V1 & !vis(p)`（激活但不可见） |
| `any.<kind>` | 所有 kind 为该值的部件（含备选件）的并：`vis(any.shoes)` ≡ ∨ vis(p)。当前档位之外的部件本来不可见，不必再按档位过滤 |
| `chain(a,b,…)` | 布尔值 ≡ vis(a) ∨ vis(b) ∨ …；同时定义 **leader**＝按书写顺序第一个可见成员（鞋＞袜＞光脚）。配合 `expect_by_leader`；无 leader 走 `else`。约束见 SEM-04 |
| `slot(x)=v` | 部位开关参数的原始值（bool）。开关为 1 不等于有件可见（当前整套可能没有该部位的件） |
| `outfit = L` / `outfit in {…}` | 整套选择器当前槽号对应的标签；float_slots 按 [i/n,(i+1)/n) 取槽号，int 取整数值 |
| `ctl(c) = v` / `ctl(c) in {…}` | `menu.controls.c` 的当前档：int/float_slots 比标签（或 `#i` 槽号，槽号换算同 outfit）；bool 比 0/1；float 控件不能用 ctl（用 param） |
| `param(P) op x` | 任一参数原始值（Bool 按 0/1）；P 须是 menu 里某控件的 param、`body_axes.*.param`，或 VRChat 内置参数（IsLocal、PreviewMode、VRMode、TrackingType、Grounded、Seated、AFK、InStation、Upright、GestureLeft/Right(Weight)、Viseme、Voice、MuteSelf、Earmuffs、IsOnFriendsList、IsAnimatorEnabled、AvatarVersion、ScaleModified、ScaleFactor、ScaleFactorInverse、EyeHeightAsMeters、EyeHeightAsPercent、VelocityX/Y/Z、VelocityMagnitude、AngularY）与 SDK 默认参数（VRCEmote、VRCFaceBlendH/V） |
| `pose = x` / `pose in {…}` | 当前施加的姿势 id（§3；T1 请求的 pose 字段） |
| `pose_tag = t` / `pose_tag in {…}` | 当前姿势的 tags 含 t（任一） |
| `body.<轴> in I` | `body_axes.<轴>` 归一到 [0,1] 的值落在区间 I（`[`/`]` 闭、`(`/`)` 开） |

### 2.2 期望可见性模型 E(p, s)

静态展开（SEM-22、DepCompiler、verdict 的「期望可见部件集」回读断言，03 §4.4 ②）不做 Play，用菜单推出每件**应当**可见与否：

1. `alt_of` 备选件：E＝假（默认不激活；何时换件由 `expect.variant` 约束，不进模型）。
2. 否则 E＝ [outfit 为 null，或当前整套标签 ∈ p.outfit] ∧ [slot 为 null，或 `slot(p.slot)=1`] ∧ [无 toggle，或 `ctl(toggle.control)` 命中 `toggle.shown_at`]。片段引入的件用 include 的 outfit。
3. 单趟修正：按声明顺序，对 target 为 `{part}` 且在该状态下结果是 `hidden`/`shown` 的依赖（用第 2 步的 E 求它的 when/cases），把该件的 E 改成假/真；不迭代。
4. 静态求值时 `vis(p).Vk` 一律等于 E(p, s)。实测（verdict）时 vis 用 T1 的四分量，E 只用于回读断言。

### 2.3 期望的求值顺序

每条 dep、每个状态：`when` 为假 → `else`；为真时按 `expect` ｜ `cases`（有序，取第一个成立的，都不成立 → `else`）｜ `expect_by_leader`（无 leader → `else`）。`when` 缺省 `true`；`else` 缺省：声明里 `baseline`，片段里 `dont_care`。`baseline` 对键＝素体档案 baseline；对 `{part}` 目标＝可见性等于 §2.2 的 E(p, s)（菜单说该显示就显示）。`dont_care` 不出判定；`pending` 一律出 undecidable 并附 `human`。`variant.options`：第一个成立的选项 o 要求「组内可见件 ⊆ {o.use}」（use 自己不可见不算违例）；`exclusive: true` 另要求组内至多一件可见。

**写法约定**：同一键被多件、多整套写时（如脚型键），各 dep 只管自己的件可见时，`else` 写 `dont_care`；「全部写者宿主不可见时回基线」交给通用规则 U3。否则 SEM-22 会在别的整套的状态上报冲突。

## 3. 姿势 id 与 tag（以 T-26 `pose_library.json` 为准）

条件、`pose_scope`、`waivers[].pose` 里的姿势名都解析到 T-26 `pose_frames.py` 产出的 `<工程>/_感知/out/pose_library.json` 的 `id` 与 `tags`。下表按 `pose_frames.py`（2026-09-18 22:58 版，sha256 前缀 1c37aef22aa92673；`muscles.py` e94f2dd29d75e15e）实际生成的写法整理；T-26 交付若改了命名，以其 selftest 输出为准并同步本表与例子。

| 来源 | id | 例 | tags |
|---|---|---|---|
| SDK proxy（`ProxyAnim/*.anim`，79 个，全部入库） | 文件名原样（带 `proxy_`） | `proxy_stand_still`、`proxy_sit`、`proxy_crouch_still`、`proxy_walk_forward`、`proxy_hands_fist` | `proxy`；03 §8.1 点名的 15 条另有 `library_a_pose` |
| GoGo Loco 库 A（7 个） | 文件名原样 | `go_sit_crossed_leg`、`go_laydown_side` | `gogoloco`、`library_a_pose` |
| 工程私有（描述符 5 层控制器引用的人形 clip，P14） | 文件名规范化，**无前缀** | `cerp_pose_10`、`a2_抱熊姿势`（工程A 实跑所见） | `private`；CERP 另加 `cerp`、`gesture_pose`；抱熊加 `bearhug`；Additive 层加 `additive`，否则加 `library_a_pose` |
| 库 B 扫掠 | `B_<关节>_<L\|R\|C>_<25\|50\|75\|100>`（脊柱是 C） | `B_knee_L_75`、`B_spine_fb_C_100` | `sweep`、关节名、部位名、`dose_<剂量>` |
| 库 B 组合（6） | `B_combo_sit`、`B_combo_deep_squat`、`B_combo_kneel_sit`、`B_combo_arms_crossed`、`B_combo_arms_up`、`B_combo_cross_legged` | — | `combo`、组合名、各关节的 `dose_<剂量>` |
| 库 B extreme（`dose_envelope: extreme` 才生成） | `B_<关节>_<侧>_extreme_<m1\|p1>` | `B_elbow_R_extreme_p1` | `sweep`、`extreme`、关节名、部位名 |
| GM 表情（`Resources/Gm/Animations/Emote/`，16 个） | `C_emote_<文件名规范化>` | `C_emote_emote_1_wave` | `emote`、`gesturemanager` |
| GoGo 动作（库 C） | `C_<文件名>`：`C_go_jump_in_place`、`C_go_knockback`、`C_go_manual_afk_idle` | — | `gogoloco`、`motion` |
| `poses.extra_clips` | `C_extra_<文件名规范化>` | `C_extra_walk_loop` | `user`、`extra` |
| 多帧 clip 的取样帧 | `<id>@<k>`（取样序号，从 0 起，≤5）；去重后只剩一帧的仍用不带 `@` 的 id | `proxy_hands_idle2@3`、`C_emote_emote_1_wave@0`、`cerp_pose_10@2` | 同该 clip |

- 规范化（`_sanitize`）：字母数字与汉字以外的连续字符换成一个 `_`，去首尾 `_`，转小写；撞名时后加 `_1`、`_2`。
- 关节名（8）：`hip_fb` 髋前屈、`hip_io` 髋外展、`knee` 膝、`shoulder_up` 肩上举、`shoulder_fb` 肩前举、`elbow` 肘、`ankle` 踝、`spine_fb` 脊柱前屈；部位名：`thigh knee shoulder elbow ankle spine`。
- **tag 词表**：`proxy library_a_pose gogoloco private cerp gesture_pose bearhug additive sweep extreme combo emote gesturemanager motion user extra dose_25 dose_50 dose_75 dose_100`，加上 8 个关节名、6 个部位名、6 个组合名。姿势类别（坐、蹲、趴）不做 tag：要按类别选就列 id。
- **解析**（SEM-03、SEM-23）：有 `pose_library.json` 时以它为准，id 与 tag 都必须在库里。没有库时按内置清单核对：`proxy_`、`go_`、`B_`、`C_emote_`、`C_go_` 开头的 id 必须在上表的固定清单里（SDK 79 个、GoGo 7＋3、库 B 66＋30、GM 16；这些家族里带 `@k` 的只接在 SDK 的 4 个多帧 proxy——`landing`、`hands_idle2`、`empty`、`rotate90_right`——和 GM、GoGo 动作的 id 后面且 k ≤5，多帧 clip 不带 `@` 的 id 也接受——离线不知道去重后剩几帧），否则报错；`C_extra_` 开头的和其它 id（工程私有，含带 `@k` 的）离线查不了，只出警告。tag 必须在上面的词表里。

## 4. 往返序列 EBNF（`deps[].roundtrip`）

```ebnf
sequence   = segment , { "," , segment } ;
segment    = rt_param , ":" , rt_value , arrow , rt_value , { arrow , rt_value } ;
rt_param   = quoted | rt_bare ;
rt_value   = slot_ref | quoted | rt_bare_v ;
rt_bare    = rchar , { rchar } ;             (* rchar = 除空白与 : , " → 外的任意字符，且不得出现 "->" *)
rt_bare_v  = rchar - "#" , { rchar } ;       (* 裸值不以 # 开头；#数字 是槽号 *)
arrow      = "→" | "->" ;                     (* "->" 是一个整体记号 *)
```

- 值的类型按该参数所属控件：bool 只许 `0`、`1`；int / float_slots 只许**标签**（裸或引号）或 **`#i` 槽号**，**不许裸数**（原始值写不成精确小数，0.2857≠2/7，00 #5）；float 只许 [0,1] 内的数。裸值整个匹配 `number` 就是数，所以长得像数字的标签要加引号。
- 每个 value 是一步「把该参数设为此值」（与当前值相同则为空步），每步后采样；段按书写顺序接续。例：`A2_Coat:1→0, A2_Outfit:素体水手服→MMN→#0, A2_Coat:0->1`、`"CERP Pose":0→1`、`RJ_Outfit:"Petal Drape"→"NOEM 卫衣"`。
- 校验器展开成 T1 `reset:none` 的显式序列（[审查 docs/state-driver-reset.md](../../docs/state-driver-reset.md)，原 README §3.0.3），int/float_slots 的标签与槽号换成参数值 i 或 i/n。`roundtrip: []` 表示该条不跑往返；不写则用 `roundtrip_default`。schema 用正则管语法（`$defs/dep/properties/roundtrip`），SEM-15 管引用与类型。

## 5. 语义规则（schema 之外，decl_validate 必查）

| 编号 | 规则 | 报错路径 |
|---|---|---|
| SEM-01 | `parts[].id`、`deps[].id` 各自唯一（includes 引入后按全局 id；本文件覆盖片段同 id、手写 `geo.*` 覆盖生成项属合法覆盖）；生成项之间撞 id 报在后一个部件上；手写 `geo.` 开头的 dep id 必须恰好是某个会生成的 id | 后出现的那条的 `/id` |
| SEM-02 | 条件与 `waivers[].states` 符合 §1 EBNF（含 chain ≥2 成员、槽号/数/标签的词法区分） | 该字符串字段 |
| SEM-03 | 条件引用存在：部件 id、`any.<kind>` 的 kind、`slot(名)`∈menu.slots、outfit 标签∈menu.outfit.labels、`ctl(名)`∈menu.controls 且非 float、ctl 的值是该控件的标签/合法槽号/（bool）0 或 1、`param(名)`（§2.1）、`body.<轴>`∈body_axes、pose id 与 pose_tag 按 §3 解析。**片段里**的条件只许 vis/chain/pose/pose_tag/true/false 原子（菜单属于各单） | 该条件字段 |
| SEM-04 | chain 成员不重复；用 `expect_by_leader` 时 `when` 恰含一个 chain，且它是 `when` 的**顶层合取项**（不在 `!` 或 `|` 之下）；`expect_by_leader` 的键集合**恰好等于**该 chain 成员集合（缺的报在 `/expect_by_leader`，多的报在 `/expect_by_leader/<键>`） | `/when`、`/expect_by_leader` 或 `/expect_by_leader/<键>` |
| SEM-05 | `target.part` 存在；`target.mesh`＝avatar.body 或某部件 `renderer: smr` 物体的 path；`{part, key|keys}` 的部件至少有一个 smr 物体；`body_axes.*.key.mesh`、`sync.from.mesh` 同理 | `/target/part`、`/target/mesh`、`…/sync/from/mesh` |
| SEM-06 | target 形状与期望匹配（expect、cases、expect_by_leader、else 全查）：hidden/shown/variant/geo 要 `{part}` 不带键与 submesh；grab 要 `{part}` 或 `{part, submesh}`；value/range/class/not_written/sync/deleted/no_writer_other_than 要带 key 或 keys；values 要不带 key/keys；pending 两可；submesh 只配 grab | 该期望字段 |
| SEM-07 | 身体网格上的键须在素体档案里存在：档案有 `all_keys:`（T-05 `body_keys` 落的身体网格全量键表）时，不在表内 → **error**，`key_classes` 只用于分类；没有 `all_keys` 时维持旧口径（`key_classes`+`baseline`+`keys`，缺失降为**警告**）。缺 `--profile` → skipped | `/target/key` 或 `/target/keys/<i>` |
| SEM-08 | `parts[].outfit` 标签∈menu.outfit.labels；`parts[].slot`∈menu.slots；`toggle.control`∈menu.controls 且不是 float 控件；`toggle.shown_at` 是该控件的标签（int/float_slots）或 0/1（bool）。片段部件在引入时按本声明的 menu 查 | 该字段（`/parts/<i>/toggle/control`、`…/toggle/shown_at`） |
| SEM-09 | `alt_of` 指向存在且自身不是备选件的部件；备选件 outfit 与主件相同 | `/parts/<i>/alt_of` |
| SEM-10 | `variant.options[].use` ∈ 目标部件 ∪ 以它为 alt_of 的部件；变体组 ≥2 件 | `…/options/<i>/use` 或 `…/variant` |
| SEM-11 | 同一 (path, submesh) 至多属于一个部件 | 后出现的那个 `/objects/<i>/path` |
| SEM-12 | inventory.json 可用时 `objects[].path` 必须在盘点里且渲染器类型一致；`target.submesh` 小于材质槽数 | `/objects/<i>/renderer`、`/target/submesh` |
| SEM-13 | 有序：`range` lo≤hi；条件区间 lo≤hi；`deleted` 同写 min/max 时 min≤max；`sync.map` 的源值严格升序 | 该字段 |
| SEM-14 | float_slots 的 default＝某个 i/n（误差 1e-6）；int 的 default 为 0…n−1 整数 | `…/default` |
| SEM-15 | 往返序列的参数是 menu 里某控件的 param；取值合该控件的类型（§4：bool 0/1，int/float_slots 标签或 `#i` 且 i<n，float 在 [0,1]） | `/roundtrip/<i>` |
| SEM-16 | `waivers[].dep` 是存在的 dep id（声明、片段引入、或 geo_defaults 会生成的），且没被 `supersedes` 取代；`waivers[].parts` 里的部件存在 | `/waivers/<i>/dep`、`/waivers/<i>/parts/<j>` |
| SEM-17 | `geo_defaults.exclude` 里的部件存在 | `/geo_defaults/exclude/<i>` |
| SEM-18 | includes：片段文件存在并按 perception-fragment/0.2 通过 schema；`package.body` 与 avatar.profile 的素体一致；`as` 互不重复；片段 deps 里的 `target.mesh` 与 `sync.from.mesh` 都等于 avatar.body。**不合格的片段不合并**，后续规则不再看它 | `/includes/<i>/fragment` |
| SEM-19 | cases / else / expect_by_leader 里任一处用 `pending` 时 dep 必须有 `human`（顶层 expect 由 schema 管） | `/deps/<i>/human` |
| SEM-20 | menu 里 outfit / slots / controls 的 param 两两不同 | 后出现的那个 `…/param` |
| SEM-21 | fit 为 closed/tight 且 covers 为空的部件，在 geo_defaults 开启时给**警告**（不拒；这种件不生成几何项） | `/parts/<i>/covers` |
| SEM-22 | **期望冲突**：展开后（片段合并、supersedes 生效、geo 生成）同一 (网格, 键) 在任一可达状态（§6.1 枚举）下，两条非 dont_care/pending 期望不相容即报：区间型（value±tol、range、values 里该键）两两无交集；class 不同（与状态无关）。baseline 有素体档案时按其值 ±0.5 参与比较，没有档案时不比。报在两条里展开顺序靠后的那条，附第一个冲突状态 | 后一条的 `/deps/<j>/id`（两条都来自片段时 `/includes/<i>/fragment#/deps/<j>/id`） |
| SEM-23 | 姿势引用：`parts[].pose_scope` 与 `waivers[].pose` 里的 id/`tag:` 按 §3 解析（有库以库为准，无库按内置清单）；`poses.extra_clips` 非空而 `libraries` 不含 C 时给**警告**（这些 clip 不会被收） | `/parts/<i>/pose_scope/<include|exclude>/<j>`、`/waivers/<i>/pose[/<j>]` |
| SEM-24 | `supersedes`：每个 id 是存在的 dep（片段引入、生成项或本文件的其它 dep），不是自己；不成环（A 取代 B 且 B 取代 A） | `/deps/<i>/supersedes/<j>` |

SEM-07、SEM-12 依赖外部数据（素体档案、T-05 盘点），examples/bad 不含其反例；SEM-07 的 `all_keys` 正/反例由 `--selftest` 专项覆盖（features_misc + 注入 profile：空表全 error、列全 0 错、少一键盘 error、无 all_keys 只 warning）。SEM-21 只警告。**片段文件单独校验**时跑能在片段内判的规则（SEM-01/02/03/04/05（mesh 除外）/06/09/10/11/13/19），报错路径是片段自己的路径；被声明引入时，片段内的错报成 `/includes/<i>/fragment#<片段内路径>`，该片段不合并，不另报 SEM-18。

## 6. 展开（decl.json）与状态枚举

decl_validate 输出的 decl.json 是展开后的形态，按下列顺序：

1. **includes 合并**：局部 id 加 `<as>.` 前缀（条件、target、alt_of、expect_by_leader 的键同步改写）；`objects.path` 前拼 `mount/`；部件写入 include 的 outfit；片段 dep 的 `target.mesh`/`sync.from.mesh` 是身体网格，不拼 mount（片段里的衣物网格一律用 `{part, key}` 引用）；片段 dep 不写 else 的补 `dont_care`。本文件同 id 的部件/依赖整条覆盖片段的。
2. **geo_defaults 生成**（规则见 schema `$defs/geoDefaults`）：区域运算按叶子——`LeftFoot`＝`LeftFoot.{forefoot,arch,heel,ankle}`，`LeftFingers`＝15 节左手指骨，其它骨名是叶子；R＝covers 叶子集 − openings 叶子集，结果按叶子列出（整只脚的四个子部位都在时写回 `LeftFoot`）。生成 `geo.<p>`（静态主项）、`geo.<p>.opening`（开口项）、`geo.<p>.poke`（姿势项）；手写同 id 覆盖生成项。
3. **supersedes**：被取代的 dep 不进期望矩阵，条目保留并加 `superseded_by: [<id>…]`。
4. **缺省值写实**：`when: "true"`、`else`（声明 baseline／片段 dont_care）、`tol: 0.5`、`roundtrip_default`、`poses` 与 `render` 的缺省、`geo_defaults` 的缺省项。
5. 按 id 排序、键排序；每条 dep 带 `origin: declared|fragment|geo_default`、生成项带 `generated_from: <部件 id>`（这两个字段只存在于 decl.json，不许在 YAML 里写）。

### 6.1 状态枚举（SEM-22 与 verdict 的期望矩阵共用）

- 菜单维：outfit 与 int/float_slots 控件取每个槽（float_slots 取 i/n 本身），bool 取 0/1，互相独立（菜单开关就是独立的）。
- 连续维（float 控件、body 轴、菜单外参数）：**临界点取样**——取条件里出现在该维上的全部常数 c，样本＝{c} ∪ 相邻常数的中点 ∪ {最小常数−1, 最大常数＋1}（截到值域内），body 轴再并上 `samples`（缺省 [0, 0.5, 1]）。这样每个比较的真假组合都至少取到一次。
- 姿势维：只在有条件用了 pose/pose_tag 时展开；按 §3 的库（或内置清单）把全部姿势按「各 pose/pose_tag 原子的真值向量」分等价类，每类取一个代表。
- 可见性用 §2.2 的 E；规模＝各维样本数之积（工程A 约 7×2⁶×3×3×2＝8 064），逐条 dep 求值即可，不需要剪枝。

## 7. 03a 未定义字段的处置

| 03a 写法 | v0.2 处置 |
|---|---|
| `rules` | 改写为 `cases`（有序、首个成立的分支胜） |
| `extra` | 删：拆成独立 dep（各自 id/target/expect/writer） |
| `also` | 删：拆成独立 dep |
| `exceptions` | 改写为 `cases`，例外分支排在前面 |
| `shown_if` | 删：按 P1 默认改 `else: dont_care`；要暴露控件时用 `cases` 写 `slot(under)=1 → shown` |
| `flag` | 改写为 `expect: {pending: true}`＋必填 `human` |
| `as_listed` | 删：改 `expect.values`（逐键值映射） |
| `dont_care` | 定义为 outcome 简写（expect / else / cases / expect_by_leader 均可用） |
| `variant.options` | 定义：`variant: {exclusive, options: [{when, use}]}`，语义「组内可见件 ⊆ {use}」；`by`/`of` 删（组＝目标部件＋alt_of 备选件）；`exclusive: false` 必须带 options |
| `targets` | 定义：target 列表，与 target 二选一 |
| `keys` 映射 | 删映射形态；`keys` 只接受列表，逐键不同值用 `expect.values` |
| dep 级 `chain` | 删：优先级链写进 `when: chain(...)`（顶层合取项），配 `expect_by_leader`（键＝成员全集） |

其它结构调整：`alt_objects` → 备选件独立成部件并写 `alt_of`；`closed: bool` → `fit: closed|tight|loose|none`；`vendor_clip {on, off}` → `{on_clip, off_clip}`（YAML 1.1 把 on/off 解析成布尔）；`objects` 字符串 → `{path, renderer, submesh}`（`路径#槽号` → `submesh`）；单栏 `confidence` → `{writer, correct, correct_basis}`；`writer` 自由文本 → 词表值或列表（说明挪到 `note`/`source`）；`menu.part_toggles/other` → `menu.slots/controls`（控件带编码与标签），发型/头饰/配饰与部件的对应写 `parts[].toggle`；`menu.outfit_radial` → `menu.outfit`；`pose in {walk, sit, crouch}` → 姿势库 id（`proxy_walk_forward`、`proxy_sit`、`proxy_crouch_still`，§3）。

## 8. 反例头注释与报错路径约定

`examples/bad/*.yaml` 每个文件由同一个合法底稿改一处得到，只违反一条规则。文件头前三行固定，可再跟一行 `# note:`：

```yaml
# rule: <schema 关键字或 SEM-xx> — <一句话>
# layer: schema | semantic
# expect_error_path: <JSON Pointer，如 /deps/0/confidence/correct>
```

**selftest 判据**：`layer: schema`——schema 必须拒，且期望路径 ∈ 规范化路径集合；**schema 不过的文档不跑语义层**（T-02 必须如此：有的反例缺必填字段，语义层会崩）。`layer: semantic`——schema 必须**通过**，语义层必须拒、报出期望路径，且只命中这一条 SEM 规则。schema 反例的 `# note:` 由生成脚本对「跳过 schema 直接跑语义层」的结果自动写出（「另会命中 SEM-xx」或「语义层不可运行」），只作阅读提示，不参与判据。片段文件（`schema: perception-fragment/0.2`）的反例按 §5 末段单独校验。

**报错路径规范化**（T-02 实现须一致）：对 jsonschema `iter_errors` 的每个错误，有 `context`（oneOf/anyOf 失败）就递归展开其子错误；叶子错误取 `absolute_path` 转 JSON Pointer（段内 `~`→`~0`、`/`→`~1`，RFC 6901），并且：`required` 追加缺失的属性名；`additionalProperties` 追加多出的属性名；`schema_path` 含 `propertyNames` 的错误追加 `instance`（出错的键名）。一个反例报出多条路径是正常的（oneOf/anyOf 展开会带出伴生路径），判据只要求期望路径在集合里。

**互斥规则**在 schema 里按规范顺序**单向**写 `{"not": {}}`（不用布尔 `false`：jsonschema 4.19 对 `false` 子模式会丢掉属性名），所以同写两个互斥字段只在规范顺序靠后的那个字段上报：target `part→mesh`、`key→keys`、`submesh→key/keys`；dep `target→targets`、`expect→cases→expect_by_leader`；期望主形式按 schema `$defs/expectation` 描述里的顺序；geo `inside→no_pierce→no_poke→opening_intact`；sync `scale/offset→map`；waiver `dep→rule/parts`、limit `max→min`；part `slot→toggle`。

**片段来源的报错路径**：`/includes/<i>/fragment#<片段内 JSON Pointer>`，如 `/includes/0/fragment#/deps/1/when`。语义层报错直接给 §5「报错路径」列的路径。YAML 载入时时间戳按字符串处理（去掉 timestamp 隐式解析），`on/off/yes/no` 保持 YAML 1.1 布尔（反例依赖这一点）。
