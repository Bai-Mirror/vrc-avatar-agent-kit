> ← [工具索引](../工具索引.md) <!-- tools_index.py 自动生成：整页覆盖，勿手改 -->

# 工具索引 · 顶层-Unity脚本（20 个文件）

由 `python3 开发工具/通用工具/tools_index.py --write` 从各脚本文件头的「用途 / 可复用性」生成，整页覆盖；要改内容请改脚本文件头。路径相对 `开发工具/`。

### 通用工具（顶层）

| 路径 | 用途 | 可复用性 |
|---|---|---|
| `通用工具/AvatarDump.cs` | 头像只读导出合集：BlendShape 名与权重、渲染器包围盒（找撑大 AABB 的元凶）、渲染器材质槽与主贴图 | ★★★ 自动识别头像，换单直接能用 |
| `通用工具/AvatarPortrait.cs` | 自带相机与布光，渲染角色形象定妆照（正面/四分之三/背面/面部）+ 规格 JSON | ★★★ 换个单子直接能用 |
| `通用工具/BakeTest.cs` | 不上传、不进 Play，直接跑一遍 NDMF 手动烘焙来复现构建期错误 | ★★★ 自动识别头像，换单直接能用 |
| `通用工具/BuildBlockerScan.cs` | 找出会中止 NDMF 构建的配置问题，以及可安全回收的空转 PhysBone | ★★★ 自动识别头像，换单直接能用 |
| `通用工具/FindDupComponents.cs` | 按类型全名找出头像上的重复组件，并删除多余的 | ★★★ 改 TypeNames 就能查别的组件 |
| `通用工具/FitAAO.cs` | 反射方式挂 TraceAndOptimize 并 dump 它的私有序列化设置。AAO 运行时程序集没开 Auto Referenced，直接 using 编不过 | ★★★ 换个单子直接能用 |
| `通用工具/FixAPSBounds.cs` | 把 AvatarPoseSystem 抓取手柄故意撑到 9.6 米的 localBounds 改回网格真实包围盒，修 AABB 超限。 | ★★ 改开头的目标物体名就能用于其他把 localBounds 撑大的插件 |
| `通用工具/FixAaoMergePhysBone.cs` | 体检头像上的 AAO MergePhysBone，删掉配置无效、会中止构建的那些 | ★★★ 自动识别头像，换单直接能用 |
| `通用工具/FixMipStreaming.cs` | 批量开启 Mip Streaming（VRChat 强制要求，不开 NDMF 构建会报错） | ★★★ 换个单子直接能用 |
| `通用工具/FixNullMaterials.cs` | 把空材质槽（渲染成洋红）从**预制体源头**取回材质补上 | ★★★ 换个单子直接能用 |
| `通用工具/McpAutoStart.cs` | 让 MCP 桥在 Unity 冷启动后自动恢复，免去每次手动点 Transport | ★★★ 任何装了 MCP for Unity 的工程都能用 |
| `通用工具/ParamAudit.cs` | 审计表情参数——每个参数占多少位、是否被菜单引用、是否被动画层使用，找出可删的 | ★★★ 自动识别头像，换单直接能用 |
| `通用工具/PerfReport.cs` | 走 VRChat SDK 的 AvatarPerformance API 出性能报告；含按顶层分组的面数分布。报告同时落盘（Console 会截断多行日志） | ★★★ 换个单子直接能用 |
| `通用工具/PhysBoneTools.cs` | PhysBone 工具合集：审计（清点/Dump）、查删重复、挂 AAO MergePhysBone（同父组/精确点名）、编辑期硬合并、压到 256 上限内 | ★★★ 自动识别头像，换单直接能用（ShedPhysBones 需改开头目标表） |
| `通用工具/PlayTest.cs` | 动画层逻辑回归测试。里面记了两条走不通的路：animator.SetFloat 够不到 VRC 的 FX 参数（那是 PlayableGraph 挂的）、animator.playableGraph 在 GestureManager 下返回无效图。能走通的是把 controll… | ★★★ 换个单子直接能用 |
| `通用工具/SceneViewShots.cs` | 按 Head/Foot 骨骼世界坐标定位 Scene View 机位，跨改动可复现的 A/B 对比截图 | ★★★ 换个单子直接能用 |
| `通用工具/State70.cs` | 70 · 「按一组参数把头像摆成交付状态」的共用求值器，验收渲图/脚型测量/组合遍历三处共用同一套语义。 | ★★ 求值器通用，参数表按素体填 |
| `通用工具/TexOptimize.cs` | 历史参考，仅保留压缩格式处理；贴图分档已由 tex_tier_plan.py / tex_tier_apply.py 取代。 | ★★★ 换个单子直接能用 |
| `通用工具/TraceParam.cs` | 追一个参数到底驱动了什么——参数→动画层→片段→曲线目标，并检查目标是否还存在 | ★★ 改开头的参数名表就能用 |
| `通用工具/TrimDeadParams.cs` | 把素体自带但已无对应网格的死参数剔掉，腾出同步位 | ★★ 改开头的参数名表就能用 |
