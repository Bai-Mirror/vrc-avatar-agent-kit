# 项目沉淀

> 跨订单复用的技术资产。**按素体 / 素材包 / 通用工具三个维度索引，不按客户。**
> 下一单要找的是「Kipfel 怎么弄」「Hollow 怎么弄」「性能怎么量」，不是「哪个客户那单」。

工具链基线：`Unity 2022.3.22f1 · VRChat SDK 3.10.4 · Modular Avatar 1.17.1 · NDMF 1.14.1 · AAO 1.9.16 · lilToon 2.3.4 · Blender 5.2`

---

## 目录

```
开发工具/
├─ README.md                    ← 你在这（工具与资产索引）
├─ SOP/                         作业规程，从 SOP/00_总表.md 进
├─ _工具链基准.md                VPM 包冻结版本
├─ _导出规格.md                  把 SOP 改写成公开教程的规格（未执行）
├─ 素材包说明.md + 素材包说明/    按素材包索引：装法与坑
├─ 通用工具/                     跟素体无关，任何单子直接能用
├─ 菜单架构/                     结构可移植，换素体改三张表
├─ 素体_Kipfel（まめふれんず）/
│   ├─ 素体说明.md               ★ 这个素体的全部已知事实
│   ├─ 脚本/                     装配类，与具体素材包绑定
│   ├─ 面部图集/                 合成配方 + 配方依赖文件
│   └─ 参考图/                   判断依据与前后对比
├─ 数据报告/                     基准数据，做同类判断时对照
└─ 版本历史/                     git bundle（33 次提交）
```

每个脚本文件头都标了：**适用素体 / 相关素材 / 工具链版本 / 可复用性评级 / 用途**。

---

## 可复用性评级

| 评级 | 含义 | 文件 |
|---|---|---|
| ★★★ | 换个单子直接能用 | `通用工具/` 里 8 个（见下表） |
| ★★ | 改开头的常量表就能用 | `通用工具/TexOptimize.cs` `TrimDeadParams.cs` `TraceParam.cs`、`菜单架构/` 3 个、`素体_Kipfel/脚本/` 多数、`面部图集/` 4 个 |
| ★ | 只能参考思路 | `ApplyEyePack.cs` `TuneEyeColor.cs` `Colorway.cs` |

> **2026-08-28 更正**：此前把 `通用工具/` 全部标成 ★★★ 是**错的** —— `PerfReport.cs`、
> `FitAAO.cs`、`TexOptimize.cs` 里都硬编码着 `const string AvatarName = "Kipfel"`，
> 换工程直接报「找不到 Kipfel」。现已全部改为**自动识别**（取当前选中物体或场景里
> 激活的 `VRCAvatarDescriptor`），才真正配得上 ★★★。

## 通用工具一览

| 文件 | 评级 | 用途 |
|---|---|---|
| `PerfReport.cs` | ★★★ | VRChat 官方评级 API 出性能报告 + 按顶层分组的面数分布 |
| `AvatarDump.cs`·DumpRenderers | ★★★ | 列每个渲染器的材质槽与主贴图 |
| `FixMipStreaming.cs` | ★★★ | 批量开 Mip Streaming（VRChat 强制，不开构建报错） |
| `FitAAO.cs` | ★★★ | 反射方式挂 AAO TraceAndOptimize 并 dump 私有设置 |
| `PhysBoneTools.cs`·DumpPhysBones | ★★★ | 列每根 PhysBone 的影响骨数 × 碰撞体数，定位碰撞检查开销来源 |
| `PhysBoneTools.cs`·DedupePhysBones | ★★★ | 找同物体上重复的 PhysBone，**逐字段比对**确认冗余后才删 |
| `ParamAudit.cs` | ★★★ | 参数审计：每个参数占几位、菜单有没有、动画层有没有 |
| `SceneViewShots.cs` | ★★★ | 按骨骼坐标定位的可复现 A/B 对比机位 |
| `PlayTest.cs` | ⚠ | 动画层逻辑回归（含两条走不通的路的记录）；**测试不完全，不得直接复用**，见上方说明 |
| `TexOptimize.cs` | 历史样本 | 旧文件名分类法已停用；现行入口为 `tex_tier_plan.py` → 审核 CSV → `tex_tier_apply.py`，按 SOP80 回读及回滚 |
| `TraceParam.cs` | ★★ | 追一个参数到底驱动了什么，检查目标对象/形状键是否还存在 |
| `TrimDeadParams.cs` | ★★ | 剔除死参数（参数名表按素体改；复制资产再改，厂商原件不动） |
| `PhysBoneTools.cs`·PhysBoneCensus | ★★★ | 按顶层子物体清点 PhysBone，找 256 上限的下手点 |
| `AvatarDump.cs`·DumpBounds | ★★★ | 找把 AABB 撑出 5×6×6 上限的渲染器（粒子系统尤其容易） |
| `FindDupComponents.cs` | ★★★ | 查/删重复的单例型 NDMF 组件（挂两个会让插件抛异常中止构建） |
| `BuildBlockerScan.cs` | ★★★ | 扫 MA MergeAnimator 空引用 + 空转/重复 PhysBone |
| `FixAaoMergePhysBone.cs` | ★★★ | 体检 AAO MergePhysBone，删掉会中止构建的无效配置 |
| `PhysBoneTools.cs`·HardMergePhysBones | ★★★ | 编辑期真合并同父同设置的 PhysBone（五道闸门，不满足就跳过） |
| `PhysBoneTools.cs`·MergePhysBoneGroups | ★★★ | 找可合并的兄弟 PhysBone 组并挂 AAO MergePhysBone |
| `PhysBoneTools.cs`·MergePhysBoneExplicit | ★★★ | 用 componentsSet 精确点名要合并哪几根 |
| `FixAPSBounds.cs` | ★★ | 修 AvatarPoseSystem 手柄把 AABB 顶到 9.6 米的问题 |
| `PhysBoneTools.cs`·ShedPhysBones | ★★ | 改开头目标表：合并一组刘海骨 / 摘掉挂件上的 PhysBone |

**参数审计与追踪必须在运行模式下跑** —— 编辑期看不到 MA / MapleCloset / VRCFury
构建期生成的那部分。300 的 Milfy 实测：编辑期 24 个参数 108 位，构建后 92 个 177 位。

---

## 从哪儿开始找

| 我要做什么 | 看这里 |
|---|---|
| 接一单新的 Kipfel / まめふれんず | `素体_Kipfel/素体说明.md` 通读一遍 |
| 判断一件衣服能不能穿 | `素体_Kipfel/素体说明.md` §一（比对骨骼名，别看文件名） |
| 做换装菜单 | `菜单架构/MenuGen.cs`，改 `Slots` `Accessories` `SlotVendorParam` 三张表 |
| 防穿模的身体收缩键 | `菜单架构/ShapeBinding.cs`（MA Shape Changer 绑在衣服上） |
| 量性能 / 优化 | `通用工具/PerfReport.cs` 建基线 → `tex_tier_plan.py` 出方案 → 审核 CSV → `tex_tier_apply.py` 应用并保存回滚 → 重新导入/测量；AAO 取舍见 `SOP/80_性能优化.md` |
| 装了某个素材包不知道怎么接 | `素材包说明.md` |
| 按流程干活 | `SOP/00_总表.md` |
| 改面部贴图 | `素体_Kipfel/面部图集/build_face_tex.py`（依赖文件在同目录 `配方依赖/`） |
| 验动画层逻辑 | ⚠ 规程待重写，见 `SOP/70_回归测试.md` 页首 |
| 想看某个决定当时是怎么判的 | `素体_Kipfel/参考图/` + `数据报告/` |

---

## 别在这里找的东西

- **构建被中止怎么查** → `SOP/问题定位/构建被中止.md`
- **贯穿全程的硬规矩**（驱动参数不动网格 / 导入≠用上 / 观测口径 / 先自检再存盘 / 病因没证实别动手）→ `SOP/00_总表.md`
- **回归测试**：`PlayTest.cs` 与 `SOP/70_回归测试.md` 的方法 2026-09-18 被判定为**测试不完全**（身体形态键适配服装没测住），只当正反皆有的样本

---

## 来源

技术内容整理自 Kipfel 素体的一次完整定制（33 次提交），
以及此前 Rurune（IKUSIA）等单的经验。已刻意剥离客户与订单信息。
