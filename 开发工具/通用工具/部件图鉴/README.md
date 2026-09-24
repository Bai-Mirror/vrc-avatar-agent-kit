# 部件图鉴 · 逐部件拍照工具（PartAtlasCapture）

**用途**：给一件衣服的**每个 Renderer** 出「长什么样 / 贴在哪 / 在整套里多显眼」的图，并写一份
`部件清单.json`。工具**只出图出数，不判断「这是什么部件」**；换单只改工程的 `_交付/部件图鉴_配置.json`。

## 文件
- 通用源 `PartAtlasCapture.cs` ＋叠字 `part_atlas_overlay.py`（PIL 左上角印商品名/路径/视图/tris/mats）；
  工程副本放 `Assets/Editor/PartAtlas/`，**两份必须逐字节一致**。
- 每工程 `_交付/部件图鉴_配置.json`（输入）与 `_交付/部件图鉴_拍摄报告.md`（读数，末行 `DONE`/`FAIL`）。
- 产物 `开发工具/素材包说明/<商品名>/部件图/`＋`部件清单.json`。

## 怎么跑
1. Unity 菜单 `Tools/PartAtlas/Capture`（**每次会话只发一次**）。
2. 重活全挂 `EditorApplication.delayCall`，菜单立刻返回，不卡 MCP。
3. 单飞锁 `_dsh_tmp_mergeqa/lock`：已存在即拒绝；跑完（含异常）必删。
4. 场景零改动：克隆拍、拍完销毁、不存盘；报告记「层级 md5 一致 / isDirty / 场景 md5 未变」。

## 配置字段
| 字段 | 含义 |
|---|---|
| `avatarRoot` | 场景里头像根 GameObject 名（outfit 没写 `avatarRoot` 时用这个） |
| `outputRoot` | 产物根目录（绝对路径） |
| `commonClipDirs` | 额外扫描动画 clip 的资产目录 |
| `bodyRoots` | 素体身体网格所在节点名，缺省 `["Body","Body_b"]`；**换素体必须点**（Milfy 是 `["Body","Body_base"]`：`Body`＝脸/头部网格、`Body_base`＝躯干四肢） |
| `outfits[]` | 每套：`root` 克隆里服装根名（**含 `/` 时按相对头像根的路径解析**，用于 `_Outfit/1` 这种会撞车的名字）、`avatarRoot`（可选，本套所属头像根，缺省用顶层 `avatarRoot`）、`product` 商品名（=输出目录名）、`vendorImageDir`、`vendorPrefab`（厂商预制件资产路径，不填则场景反查） |
| `maxRenderersPerOutfit` | 调试小样：>0 每套只拍前 N 件；正式 0 |
| `onlyParts` | 只拍 `gameObject.name` 命中这些名字的 Renderer（空＝全拍）；**序号仍按完整列表算**，文件名/清单里的 `NN_` 不变。用于上游修正后的局部重拍（H-03）；本套无命中就整套跳过 |
| `cloneBlendshapeSync` | true 时在克隆上按 `ModularAvatarBlendshapeSync` 把 `LocalBlendshape` 跟到参照网格当前值（构建期语义）。编辑模式里 NDMF 预览跑没跑、跑完没跑完都不确定，拍照克隆必须先落到「构建期同步后」的形态键，不能信场景实例的编辑期读数 |
| `mergeExistingManifest` | 只拍子集时，把命中条目的新读数整块并回已存在的 `部件清单.json`，保留同套其余条目与套级字段（否则整份清单会只剩命中的几条） |
| `partFrameExpand` | 整套按部件取景的扩展倍数，默认 2.5（<=0 用默认） |
| `partFrameMinRatio` | 整套按部件取景的部件投影占画幅下限，默认 0.05 |

**一套配置可跨多个头像根**（2026-09-22 H-05 起）：按每套的 `avatarRoot` 分组，每组各克隆一次、拍完销毁再下一组；
`场景外泄核对`/`素体顶点索引` 按组分记。克隆仍整体挪到 x=+10。

## 出图清单与命名
`NN_<Renderer名>_<视图>.png`（768²，1-based 序号按服装根遍历顺序）：
- **在身上-正面/侧面/背面**：只开该部件＋素体 `Body`/`Body_b`；**克隆之外场景里的一切
  Renderer/ParticleSystem 也一律关**。
- **仅部件-正面**：身体也关。
- **整套-有/无-正面**（部件重心偏背面时另有 `-背面`）：整套按厂商默认开关；
  **按部件包围盒取景**（扩到 ≥2.5 倍＋并进相邻身体部位），有/无同机位。
- **整套全身-有/无-正面**（同上背面）：原来的全身取景（H-02b 起从 `整套-*` 改名）。
每图左上角叠 `商品名 / 路径末两级 / 视图 / tris= / mats=`。

## 数据口径（写进清单的「口径」字段）
- **front**：读 Head 骨水平 forward；`正视夹角=0°` = 正脸朝镜头。
- **包围盒三级退化**（`包围盒世界.口径`）：① 网格可读 → 蒙皮按
  `Σ w·(bone.localToWorld·bindpose)·v` 逐顶点算；② 网格不可读（厂商 FBX 关了 Read/Write，
  The Velour 9 件全中）→ `renderer.bounds`；③ `renderer.bounds` 退化成 2×2×2 → 骨骼并集。
- **主导骨**：读得到 `boneWeights` 用真权重；读不到退化为「骨骼到包围盒距离」，清单逐条标口径，
  只当弱证据，覆盖部位以图为准。
- 取景**不信** `Renderer.bounds`（编辑期对未激活蒙皮常虚报 2×2×2）。

## 坑（触发时刻＋怎么避免）
### H-02 抓到的 4 个
1. **`Renderer.bounds` 虚报**：拍蒙皮件、读包围盒/取景时读到 2×2×2。→ 自己按骨权重算顶点；
   不可读再退化，口径写进清单。
2. **厂商 FBX 关了 Read/Write**：想拿顶点/权重时 `mesh.isReadable=false`（Velour 9 件）。
   → 退化到 `renderer.bounds`/骨距口径并逐条标注；要真权重得开 Read/Write 重导（会改工程资产，另议）。
3. **厂商预制件反查不到**：`kaguya_cloth` 在场景里是手工节点，反查得到整台素体 prefab；
   从克隆反查直接 null。→ 配置点名 `vendorPrefab`，反查只作兜底且必须从**场景原对象**反查。
4. **菜单回调里跑重活卡 MCP**：整个拍摄远超 20 s。→ 菜单只挂 `delayCall`＋单飞锁，跑完删锁。

### H-02b 这 2 个取景坑
5. **「在身上-侧面」混入白熊**：视图沿 ±x 正交拍时，克隆正后方还立着原头像（乃至另一台正在编辑的
   头像），相机 `cullingMask=~0` 把它们一起拍了；正/背视沿 z、横向错开 10 单位故不中，所以只有侧视
   出问题——**只关克隆的配饰不够**。→ 拍前 `SceneHide`：把克隆之外场景里所有 Renderer
   （含 ParticleSystemRenderer）与 ParticleSystem 全关，拍完恢复；报告记「关闭 N / 恢复 N」。
6. **「整套-有/无」太小**：小部件（乳贴/项圈/包扣）在全身图里只有几个像素。→ 对比两张改按部件包围盒
   取景（≥2.5 倍＋相邻身体部位；部件投影外接框 <5% 画幅就往里收，但绝不切件），全身两张保留并改名
   `整套全身-*`。注：乳贴「有/无」看着一样是它整套下被抹胸完全遮住（可见条件问题），不是图小。

### H-05 这 4 个（多头像根 / 换素体 / 厂商骨名 / 未指派引用）
7. **一个工程多个头像根**：Milfy 拆成衣装 A/B 两根，而一套配置只 `Instantiate` 一个 `avatarRoot`，
   第二个根的服装根在克隆里根本找不到。→ `PacOutfit.avatarRoot`（可选，缺省用顶层）＋按根分组：
   一组克隆一次、拍完销毁再下一组；`场景外泄核对`/`素体顶点索引` 按组分记，收尾报跨组累计。
8. **素体网格不都叫 `Body`/`Body_b`**：Milfy 是 `Body`（脸/头部，带 viseme 形态键）＋`Body_base`（躯干四肢）。
   只中其一 → 身体部位索引只有 5 个部位（缺上臂/手/腿/脚），整套取景没有腿脚上下文。→ `bodyRoots` 配置点名。
9. **厂商自带骨架名带部件后缀**：00capettiya 四套是 `Hand.L(KemoHandMB)`（Modular Avatar 就按
   `骨名(部件名)` 合并回素体）；旧表按骨名精确匹配全落「其它」。→ `BoneRegions.RegisterHumanoid` 用
   Animator 人形骨映射补全，`RegionOf` 再对尾部括号做一次去后缀重查。
10. **未指派的序列化引用**：`FieldsOf` 对 fake-null 的 `UnityEngine.Object` 读 `.name` 会抛
    `UnassignedReferenceException`（MA `ModularAvatarMenuItem.menuSource_otherObjectChildren`），
    整套抛异常、0 图。→ 用 Unity 重载的 `uo == null` 先判空再取名字（`Str()` 也包 try/catch）。

### H-03 这 2 个（编辑期形态键 / 副本脱节）
11. **编辑模式里 MA `BlendshapeSync` 的生效值不可依赖**：参照键改好后，NDMF 编辑器预览可能在若干帧后
    把衣服键从厂商预制件默认值改成跟身体一致的值，也可能还没跑；同一个场景
    实例不同时刻读到不同值。→ 局部重拍一律开 `cloneBlendshapeSync`，在克隆上显式按绑定落值，并把
    「厂商预制件默认 / 场景实例当前 / 克隆同步后」三个读数写进报告。
12. **工程副本会跟通用源脱节**：H-05 只同步了 Milfy 的副本，工程A 的副本整段落差（少了
    `bodyRoots`/多头像根）。→ 动工具前先 `diff -q` 通用源与目标工程副本；改完两份一起同步、
    `diff -q` 报 SAME 再编译。

## 在别的工程怎么用
1. 把 `PartAtlasCapture.cs` 复制到目标工程 `Assets/Editor/PartAtlas/`（`part_atlas_overlay.py` 留通用目录）。
2. 在目标工程写 `_交付/部件图鉴_配置.json`：至少 `avatarRoot`、`outputRoot`、`outfits[].root/product`。
3. Unity 刷新编译 → 菜单 `Tools/PartAtlas/Capture`。
4. 看 `_交付/部件图鉴_拍摄报告.md` 末行是否 `DONE`，并核对收尾三条读数（md5 一致 / isDirty=False /
   场景文件 md5 未变）。

## 查档脚本（check_parts_doc.py）
派工前查一件商品**有没有图鉴**（判法见 SOP 50 第一节）；只读。
```
python3 开发工具/通用工具/部件图鉴/check_parts_doc.py --item <商品号> [--avatar Kaguya]
python3 … --name "The Velour"   # 目录名/预制件名/场景根名
python3 … --selftest
```
- 查 `<素材库>/*-<号>`（目录名可含方括号，用 `listdir` 过滤后缀）、
  `素材包说明/*/部件图鉴.md`（grep 号或名）、`<商品名>/部件清单.json` 与 `部件图/`。
- 四态：有图鉴（含/缺本素体）／只有清单和图／都没有，附命中路径；`--json` 结构化输出。
- 退出码 0/10/20/30 对应四态（多查询取最不完整态）；自身出错 2。
- `dsh_task.js` 命中「装配|菜单|部件图鉴|换装|服装」时自动跑它、结果追加到任务书末尾并打到
  stderr（失败只告警；`--no-parts-check` 关，`--dry-run` 只打印拼好的任务书）。

## 已知限制
- 网格不可读时包围盒/主导骨是退化口径，别当权重结论。
- 面积口径对极扁部件（如双手指甲 46:1）数学上到不了 5%：工具保住整件可见，最长边口径 ≥ ~22%。
- 「整套有/无」当部件被外层完全遮住时两图相同（判可见条件要配合厂商开关/形态键，见 SOP）。
