# 交付文件清单与已做的机器验证 <!-- nav -->

> 旧称：T1 `AuditStateDriver` / T3 `AuditTurntable` 等（原 `审查/README.md`） §0 / §0.1 / §0.2。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 下一页：[部署（sync_audit.py）与调用方式](deploy.md) <!-- nav -->

## 0. 交付物与已做的机器验证

### 0.1 文件

> T-09 起源码按 asmdef 分家：`.cs/.shader` 在 `开发工具/通用工具/审查/unity/Editor/`，
> `unity/Runtime/` 目前只放 asmdef（`AuditMappingProbe` 待 T-12）。部署不再手工 `cp`，
> 统一走 §1 的 `perception/sync_audit.py`。

> ⚠ **DSH 正在改 `审查/unity/` 源码时，别从工作区同步**（2026-09-19 工程F：AN 改到一半的 `AuditStateDriver.cs` 被拷进工程 → 编译失败 → MCP 桥起不来）。改用 `sync_audit.py --from-git <rev>`：逐文件 `git show <rev>:<源路径>` 取指定修订（任务 AR，2026-09-19 落地），工作区有未提交改动时会警告并逐条列出；手工 `for f in $(git ls-tree …); do git show HEAD:$f > …; done` 的旧办法不再需要。也可先 `git status 开发工具/通用工具/审查/unity` 自查。

| 文件 | 作用 |
|---|---|
| `AuditIO.cs` | 公共层：手写 JSON 解析/序列化、`status.json`、头像按名解析、GestureManager/SDK 反射桥、菜单入口与 `EditorApplication.update` 状态机泵 |
| `AuditStateDriver.cs` | T1 状态驱动器（仅 Play 模式；含 `pre_probe_blendshapes` 探针前临时形态键，任务 U） |
| `AuditProbes.cs` | T1 附带的纯数据探针（任务 R/U）：`grab_chain` 抓屏链 / `coincident` 重合网格 / `containment` 包含率 + 表面穿越计数 / `range` 形态键越界；任务 BQ 起 `delete_coverage` 转调 AuditDeleteCoverage.cs |
| `AuditDeleteCoverage.cs` | 探针 `delete_coverage`（任务 BQ，B-补-20；任务 BV 改为**编辑模式量测**）：MA ShapeChanger `Delete` 写者的删除区有没有被写者自己那件盖住；菜单 `Tools/AvatarAudit/Delete Coverage (Edit Mode)` + 请求文件 `Library/AvatarAudit/delete_coverage_request.json`；Play 里 T1 调用返回 `undecidable: MA 已处理网格` |
| `AuditTurntable.cs` | T3 环绕渲图 + 透明排序检测（含 `only_renderers` / `hide_renderers` 渲图过滤，任务 U） |
| `T3ArmFreeze.cs` | T3 前置（C-12）：冻结 Animator + 按请求手设身体收缩键，再做 T3 渲图；工程F `t3_arm` 手工 `execute_code` 的复跑脚本；菜单 `Tools/AvatarAudit/T3 Arm Freeze (Edit Mode)`，请求 `Library/AvatarAudit/t3_arm_freeze_request.json`，报告 `<out>/report.json`；示例 `unity/examples/t3_arm_freeze_request.json` |
| `T3RpSyncSim.cs` | T3 前置（C-12）：手动模拟 MA BlendshapeSync（读 `Bindings` 把参照键值抄到件本地键；`mode=nosync` 归零复现修前），再做 T3 渲图；工程E `t3_rp_*` 的复跑脚本；菜单 `Tools/AvatarAudit/T3 RP Sync Sim (Edit Mode)`，请求 `Library/AvatarAudit/t3_rp_sync_sim_request.json`，报告 `<out>/report.json`；示例 `unity/examples/t3_rp_sync_sim_request.json` |
| `NipplePatchFrames.cs` | 给衣物补形态键帧（C-12）：身体键 0/100 `BakeMesh` 位移场 → 最近 4 点反距离加权 → 蒙皮矩阵逆 → `AddBlendShapeFrame` 存 `.asset`；工程D乳贴约 40 行 `execute_code` 的复跑脚本；菜单 `Tools/AvatarAudit/Nipple Patch Frames (Edit Mode)`，请求 `Library/AvatarAudit/nipple_patch_frames_request.json`，报告 `<out>/report.json`；示例 `unity/examples/nipple_patch_frames_request.json` |
| `AvatarAuditFlat.shader` | T3 专用：不受光照的纯色材质（掩码纯白 / ID 图唯一色），`ZWrite On` |
| `AvatarAuditInvisible.shader` | T3 专用：什么都不输出（`ColorMask 0`、`ZWrite Off`、`ZTest Always`），用来隔离材质槽 |
| `AvatarAudit.Editor.asmdef` | Editor 程序集定义（T-09）：引用 NDMF / MA core / AAO api.editor / VRC.SDK3A + `0Harmony.dll` precompiled；`versionDefines` 按 MA `[1.18.1]`、AAO `[1.9.16]`（方括号=精确匹配，裸版本号在 Unity 里是 ≥；B-补-15）定义 `AUDIT_MA_1_18_1` / `AUDIT_AAO_1_9_16` |
| `AvatarAudit.Runtime.asmdef` | Runtime 程序集定义（T-09）：`AuditMappingProbe` 的容器，引用 `VRC.SDKBase` + `VRCSDKBase.dll`（实现 `VRC.SDKBase.IEditorOnly`，构建期由 SDK 自动删） |
| `README.md` | 本文件 |

``Editor/` 下的 8 个 `.cs`（T-05 起含 `AuditPartInventory.cs` / `AuditBatch.cs`）全部只依赖
`UnityEngine` / `UnityEditor`（`AuditProbes` / `AuditFitProbe` / `AuditPartInventory` 另用 `Unity.Collections`）；
对 GestureManager 与 VRChat SDK 一律**反射**访问，不写 `using`，
因此这几个 `.cs` 在不装 GM、SDK 版本不同的工程里也能编译（只是会降级并写进输出）。asmdef 里对 MA/AAO/NDMF 的
引用是给 T-12（构建期截获）预留的，当前代码不直接用到。两个 `.shader` 由
`AuditTurntable` 用 `Shader.Find` 按名取用，缺了只会关闭透明检测并写 warning，不影响环绕渲图。

### 0.2 本轮已经验证过的东西（可复现）

1. **编译通过**（0 error / 0 warning）。用 Unity 自带的 Mono `csc.exe`，`-nostdlib+` + Unity 的
   `Data/NetStandard/ref/2.1.0` + `shims` + `Managed/UnityEngine/*.dll` + `UnityEditor.dll` 作参考程序集：

   ```bash
   MONO=<Unity安装根>/Editors/2022.3.22f1/Editor/Data/MonoBleedingEdge/bin/mono
   CSC=<Unity安装根>/Editors/2022.3.22f1/Editor/Data/MonoBleedingEdge/lib/mono/4.5/csc.exe
   BASE=<Unity安装根>/Editors/2022.3.22f1/Editor/Data
   REFS="-nostdlib+ -r:$BASE/NetStandard/ref/2.1.0/netstandard.dll"
   for f in $BASE/NetStandard/compat/2.1.0/shims/netstandard/*.dll \
            $BASE/NetStandard/compat/2.1.0/shims/netfx/*.dll \
            $BASE/Managed/UnityEngine/UnityEngine*.dll \
            $BASE/Managed/UnityEditor.dll; do REFS="$REFS -r:$f"; done
   $MONO "$CSC" -nologo -target:library -langversion:9 -warn:4 -out:audit.dll $REFS \
        开发工具/通用工具/审查/unity/Editor/AuditIO.cs \
        开发工具/通用工具/审查/unity/Editor/AuditStateDriver.cs \
        开发工具/通用工具/审查/unity/Editor/AuditTurntable.cs \
        开发工具/通用工具/审查/unity/Editor/AuditFitProbe.cs \
        开发工具/通用工具/审查/unity/Editor/AuditMenuDump.cs \
        开发工具/通用工具/审查/unity/Editor/AuditProbes.cs
   ```

   （任务 G 后又按同一条命令重编过 4 个 `.cs`：0 error / 0 warning；临时脚本 `_长程任务_20260918/派工/tmp/compile_audit_G.sh`。）
   （任务 R 用同一命令编 6 个 `.cs`（含新文件 `AuditProbes.cs`）：0 error / 0 warning；脚本 `_长程任务_20260918/派工/tmp/compile_audit_R.sh`，日志 `R_compile.log`。）
   （任务 T 改 `containment` 三处后，用同一命令编 6 个 `.cs`：0 error / 0 warning；脚本 `_长程任务_20260918/派工/tmp/compile_audit_T.sh`，日志 `T_compile.log`。配对 token 逻辑另用反射小测在 mono 下跑过 13 项 `ALL PASS`，见 §3.2.3。）
   （任务 U 给 `containment` 加穿越计数、给 T1 加 `pre_probe_blendshapes`、给 T3 加 `only_renderers`/`hide_renderers` 后，用同一命令编 6 个 `.cs`：0 error / 0 warning；脚本 `_长程任务_20260918/派工/tmp/compile_audit_U.sh`，日志 `U_compile.log`。AAO 形态键名还原与 T3 子串匹配另用反射小测在 mono 下跑过 13 项 `ALL PASS`，见 §3.2.3。）
   （任务 V（T-09）把代码迁到 `审查/unity/Editor/` 后，用新路径版脚本 `_长程任务_20260918/派工/tmp/compile_audit_V.sh` 重编 6 个 `.cs`：0 error / 0 warning，日志 `V_compile.log`。）
   （任务 AN（T-13 T1 v4）用 `_长程任务_20260918/派工/tmp/an/compile_audit_AN.sh` 编 `Editor/` 下**全部 8 个 `.cs`**
   （含 T-05 的 `AuditPartInventory.cs` 与 `AuditBatch.cs`）：0 error / 0 warning，日志 `an/AN_compile_baseline.log`。
   v4 纯逻辑 + 83 态请求重放自检：`an/compile_t1v4_selfcheck.sh` 编 exe、`an/run_t1v4_selfcheck.sh` 跑
   （`MONO_PATH` 指 Unity 托管程序集；自检只调纯逻辑），**40 PASS / 0 FAIL**，日志 `an/AN_selfcheck.log`。
   运行期待 Claude 在 Unity/Play 验，见 §9.2。）

   过程中真抓到一个错：`Texture2D.GetPixels32(Color32[])` 这个填充重载在 2022.3 的参考程序集里不存在
   （编译报 `cannot convert from 'UnityEngine.Color32[]' to 'int'`），已改为
   `_readTex.GetPixelData<Color32>(0).CopyTo(dest)`（顺带避免了每次渲染分配 4 MB 托管数组）。

2. **JSON 层运行时测试全过**（28 项 `ALL PASS`）。用上面的参考程序集把 3 个文件编成 `audit.dll`，
   再编一个小测试 exe 在 mono 下跑纯逻辑：任务书里两条请求 JSON 原样解析、转义/负数/嵌套/空对象/空数组/
   `null` 往返、`IDictionary` 序列化、同一对象两次序列化逐字节一致、坏 JSON 抛 `FormatException`。
   测试用的临时文件在 `_长程任务_20260918/派工/tmp/` 下，已删。

3. **反射符号逐条核对**（19/19 OK）——见 §8。

4. **任务 I（T3 第二版：按子网格 + 透光率模型）重编通过**：同一条命令编 4 个 `.cs`，
   `-warn:4` 下 0 error / 0 warning（`_长程任务_20260918/派工/tmp/compile_audit_I.sh` + `I_compile.log`）。
   本轮同样**未启动 Unity、未调 MCP**，运行期行为待 Claude 在 工程A 工程里验收。

---
