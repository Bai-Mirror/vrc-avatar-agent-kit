> ← [60 · 菜单与动画层](../60_菜单与动画层.md) · [00 · 总表](../00_总表.md)

# VRCFury 的参数压缩：256 bit 不是硬墙（2026-09-21 读 VRCFury 1.1414.0 源码）

**触发**：`CalcTotalCost()` 逼近或超过 256，在考虑「砍功能」之前。

## 什么时候启动

`Editor-Avatars/Service/Compressor/ParameterCompressorSolverService.cs` 开头就是：

```csharp
var originalCost = paramz.CalcTotalCost();
if (originalCost <= maxCost) return new ParameterCompressorSolverOutput();   // 不超限 → 一个字节都不压
```

→ **254/256 这种数字是真实的未压缩开销，不是「已经压过了」**。
压缩钩子是 `VrcfAvatarPreprocessor`（`order = int.MaxValue - 100`），跑在 SDK 预处理阶段，
**不在 NDMF `ProcessAvatar` 里**——所以编辑器里手动跑 NDMF 构建读到的开销永远是压缩前的。

## 怎么压

把「绑在菜单 Toggle / RadialPuppet / TwoAxis / FourAxis 上的同步参数」换成
少量**时分复用的槽位**，轮流广播：

```
finalCost = 原始开销 − Σ(被压参数开销) + 数值槽×8 + 布尔槽×1 + 批次索引位
批次数    = max(ceil(数值个数/数值槽), ceil(布尔个数/布尔槽))
索引位    = ceil(log2(批次数 + 1))
一轮同步  = 批次数 × (BATCH_TIME 0.1 s + 1/60 s) ≈ 批次数 × 0.117 s
```

`OptimizationDecision.Optimize()` 会**一直加槽位直到把 256 用满**，
目的是缩短同步时间——所以压缩后的开销总是贴着 255~256，
**「压缩后剩几 bit」是个没意义的数**。

## 压不动的是什么（这才是真正的预算）

Solver 从候选里剔除：控制器根本没用到的、Contact / PhysBone / VRCRaycast 自动参数、
只绑在 Button / SubMenu 上的、既不在菜单里也不被驱动且不以 `FT/` 开头的（OSC-only）。
剩下的才可压。

> **可查问句**：我这 N bit 里，有多少是**绑在菜单开关/轮盘上的**？
> 只有这部分能被压。**压不动的那部分之和 + 9 + 索引位 = 这个模型的真实硬地板。**

## 一份实测（工程B_Milfy，2026-09-21）

| 项 | 值 |
|---|---|
| 同步参数 | 114 个 = **254 bit** |
| 其中可压 | 93 个（12 数值 + 81 布尔）= 177 bit |
| **压不动的硬开销** | **77 bit** |
| 最大压缩地板 | 77 + 8 + 1 + 7 = **93 / 256** |

按 VRCFury 实际会选的方案（槽位加满）：

| 追加 | 原始 | 压缩后 | 批次 | 一轮同步 |
|---|---|---|---|---|
| 不加 | 254 | 255 | 1 | 0.12 s |
| +10 个菜单开关 | 264 | 256 | 2 | 0.23 s |
| +60 个菜单开关 | 314 | 256 | 2 | 0.23 s |
| +20 个菜单轮盘 | 414 | 256 | 2 | 0.23 s |

## ⚠ 这条对**面捕参数**不成立

面捕（VRCFaceTracking / Triturbo）的参数由 OSC 驱动，**不绑任何菜单控件**，
而 VRCFury 的压缩只吃「绑在 Toggle/轮盘上的同步参数」——所以面捕参数**整块压不动**，
每加一个同步参数就是 1:1 的硬开销。

工程B_Milfy 实测（同一工程的两个根）：

| | 非 FT 版 | 面捕版 |
|---|---|---|
| 同步开销 | 254 bit | **398 bit** |
| 其中 `FT/` 前缀 | — | 110 个 = **138 bit**（只有 1 个绑了菜单） |
| **压不动的硬开销** | 77 | **208** |
| 最大压缩地板 | 93/256 | **224/256**（仍能传） |
| VRCFury 实选 / 一轮同步 | 255/256 / 0.12 s | 256/256 / **0.58 s** |

> **可查问句**：我要加的这批参数，**能不能挂到菜单控件上**？
> 挂得上 → VRCFury 吃得下，只是同步变慢；挂不上（OSC 驱动、Contact、PhysBone）→ 1:1 占预算。
> 取舍：装面捕之前先算一次「硬开销 + 面捕参数」，别等上传报错。

**取舍**：设计期不要为 256 砍功能——只要新参数是**菜单绑定的同步参数**，
VRCFury 都吃得下，代价只是切换有延迟。真到上传报错再回来腾位置，
腾的时候优先动那 77 bit 里的：把只给自己看的改成 `networkSynced=false`（本地参数不计入），
以及删掉控制器根本没用到的同步参数。

**Tools → VRCFury → 的压缩开关**有三档（`CompressorMenuItem`）：
`Compress`（默认，自动压）/ `Ask`（弹窗问）/ `Fail`（直接失败）。默认那档就行。

## 量真值只能跑完整 SDK 预处理链（2026-09-21 工程B实测）

压缩器挂在 `VF.Hooks.ParameterCompressorHook`，`callbackOrder = int.MaxValue-100 = 2147483547`，
它是一个 `IVRCSDKPreprocessAvatarCallback`，**不在 NDMF 的 `AvatarProcessor.ProcessAvatar` 里**。

- 只跑 NDMF 量到的是**压缩前**的数。工程B面捕根：NDMF-only 量到 **398**，完整链跑完是 **256**。（09-22 拆分后衣装 A/B 同：NDMF-only 345/324，完整链 256/256）。**上传前卡口报告必须两个数并列并标哪个是上传判据**；可查问句：这个 `CalcTotalCost()` 是压缩前还是压缩后读的？
- 也**不能**拿工程里挂在 descriptor 上那份 `VRCExpressionParameters` 当判据 —— 那只有手写的那些
  （工程B是 22 条 / cost 99），真正的一两百条是构建期 MA MenuInstaller + 面捕包拼出来的。
- 正确做法：`Instantiate` 一份克隆 → 按 `callbackOrder` **逐个**跑所有 `IVRCSDKPreprocessAvatarCallback`
  （别整包调 `VRCBuildPipelineCallbacks.OnPreprocessAvatar`，那个只返回一个 bool，
  「谁拒的、拒之前压缩器跑没跑」全看不见）→ 读克隆上 descriptor 的 `expressionParameters.CalcTotalCost()`。
- **256/256 不是悬崖**：压缩器的算法就是把槽位涨到填满 256 为止，所以「正好 256」是它的正常输出。

⚠ 跑这种重活的菜单项要自带文件锁：MCP 的 `execute_menu_item` 超时会重发，
实测一个构建测量菜单被重发跑了三遍，Unity RSS 从 3 GB 涨到 14 GB 最后 `Exiting early due to double fault` 崩了。
锁要在**跑完时刷新时间戳**而不是删掉——重发排在主线程后面、恰好在删锁之后执行（见 [70 常见坑](../70_回归测试/常见坑.md)）。
