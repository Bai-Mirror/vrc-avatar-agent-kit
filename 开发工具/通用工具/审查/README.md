# VRChat 头像视觉审查工具 · T1 `AuditStateDriver` / T3 `AuditTurntable`

> 设计依据：`_长程任务_20260918/审查工具设计.md` 的 T1、T3 两节。
> 运行环境：Unity 2022.3.22f1（Editor 程序集；T-09 起在 `AvatarAudit.Editor` asmdef，不再编进 `Assembly-CSharp-Editor`）。
> 本轮**只写代码、未启动 Unity**；代码已用 Unity 自带的 Roslyn/Mono 编译器对着 Unity 2022.3.22f1 的
> 参考程序集编译通过（见 §0.2），运行期行为待 Claude 在 工程A 工程里验收。

---

## 这个目录是什么

VRChat 头像**视觉/数据审查工具集**：在 Unity 里驱动菜单状态、读显隐与形态键、跑几何探针、环绕渲图、导出菜单树与部件清单（`unity/`，C# Editor 程序集），再用 Python 脚本离线生成请求、合并与分析结果（本目录 `*.py`、`perception/`）。目标是把「开关对不对、衣服穿没穿模、菜单承诺兑现没有」从肉眼比对变成可复跑的数据。

| 位置 | 内容 |
|---|---|
| `unity/` | Unity 侧源码（`Editor/`、`Runtime/`，部署到工程 `Assets/AvatarAudit/`）与编辑模式小工具请求样例（`examples/`） |
| `t5_shapekey_matrix.py` · `menu_expect_check.py` · `dual_root_diff.py` | 离线脚本：形态键依赖矩阵、编译态菜单断言、双头像根差异普查 |
| `perception/` | 感知机制离线工具（声明校验、写者图、校验器、姿势库、同步/剥离），见 [perception/README.md](perception/README.md) |
| `replay/` | 缺陷回放库，见 [replay/README.md](replay/README.md) |
| `docs/` | 全部说明（见文档目录） |

## 依赖

- **Unity 2022.3.22f1** + VRChat SDK3 Avatars。`AvatarAudit.Editor.asmdef` 引用 NDMF、Modular Avatar core/editor、AAO `api.editor`、`VRC.SDK3A`、`AvatarAudit.Runtime`，预编译引用 `0Harmony.dll`、`VRCSDKBase(-Editor).dll`、`VRCSDK3A.dll`、`System.Collections.Immutable.dll`；`versionDefines` 按 MA `[1.18.1]` / AAO `[1.9.16]` 精确匹配。GestureManager 与 SDK 大部分走反射，缺了降级并写进输出（见 [交付文件清单](docs/deliverables.md)）。
- **Python 3**：`t5_shapekey_matrix.py`、`menu_expect_check.py`、`dual_root_diff.py` 只用标准库；`perception/` 需要 **PyYAML**（`unity_yaml.py`、`decl_draft.py`、`decl_validate.py`），`jsonschema` 可选（没有时 schema 层报 skipped），`key_class_blender.py` 只在 Blender 内跑（`bpy` + `numpy`）。

## 快速上手

```bash
# 1) 部署到工程（先看计划；同步后 Unity 里 refresh、Console 0 error）
python3 开发工具/通用工具/审查/perception/sync_audit.py "<工程>" --dry-run
python3 开发工具/通用工具/审查/perception/sync_audit.py "<工程>"
# 2) 写 <工程>/Library/AvatarAudit/request.json，Play 模式下点菜单 Tools/AvatarAudit/Run Request
#    （请求格式见 docs/state-driver-request.md；进度与结果在请求 out 目录的 status.json）
# 3) 由 T4 params.json 生成开关 sweep 请求，T1 跑完后分析形态键依赖矩阵
python3 开发工具/通用工具/审查/t5_shapekey_matrix.py sweep --params <t4>/params.json --slots <run>/slots.json ...
python3 开发工具/通用工具/审查/t5_shapekey_matrix.py analyze --t1 <run>/sweep --sweep <run>/sweep/t1_request_sweep.json ...
# 4) 交付前：菜单承诺 ↔ 构建后实测逐条比对
python3 开发工具/通用工具/审查/menu_expect_check.py check --delivery --expect 期望.json --t1 <T1 输出目录> ...
# 5) 交付前剥离审查代码
python3 开发工具/通用工具/审查/perception/sync_audit.py "<工程>" --strip
```

参数详见 [部署](docs/deploy.md)、[T5](docs/shapekey-matrix.md)、[菜单断言](docs/menu-expect.md)。

## 文档目录

各页页首写明「旧称」与原 README 的 § 编号；正文里的 `§x.y` 仍指原编号，按下表查页。代号：T1＝状态驱动器、T2＝贴合探针、T3＝环绕渲图、T4＝菜单导出、T5＝形态键依赖矩阵、W5＝编译态菜单断言、T-05＝部件盘点、T-12＝构建期截获、T-30＝PhysBone 静态清单。

| 页 | 原章节 |
|---|---|
| **总览与部署** | |
| [交付文件清单与已做的机器验证](docs/deliverables.md) | §0 / §0.1 / §0.2 |
| [部署（sync_audit.py）与调用方式](docs/deploy.md) | §1 / §2 |
| **T1 状态驱动器 `AuditStateDriver`（原 README §3–§4）** | |
| [请求格式](docs/state-driver-request.md) | §3 |
| [每个状态做什么、健全性检查、易变形态键](docs/state-driver-steps.md) | §3「每个状态做什么」/ §3.0 / §3.0.1 |
| [回调隔离、头像解析、GestureManager 接管](docs/state-driver-isolation.md) | §3.0.2 /「头像解析规则」/「GestureManager 接管」/ §3.1 |
| [reset 模式与切换残留测试](docs/state-driver-reset.md) | §3.0.3 |
| [版本戳、状态回读断言、档位槽号、哨兵、sequence/history](docs/state-driver-readback.md) | §3.3（原文在 §3.2.8 之后、没有单独标题，§2 以「§3.3」引用） |
| [`state_<id>.json`](docs/state-driver-output.md) | §4 |
| [states.json 汇总](docs/state-driver-states-json.md) | §4「states.json」前段 |
| [states.json 字段口径](docs/state-driver-states-fields.md) | §4「states.json」后段 |
| **T1 纯数据探针 `AuditProbes`（原 §3.2–§3.4）** | |
| [T1 纯数据探针总览 · grab_chain / coincident](docs/probes.md) | §3.2 / §3.2.1 / §3.2.2 |
| [探针 containment（包含率）](docs/probe-containment.md) | §3.2.3 前半 |
| [探针 containment 命中数口径 · 探针 range](docs/probe-containment-crossing.md) | §3.2.3 后半 / §3.2.4 |
| [探针 poke（静态穿出斑块）· 判据、请求与输出](docs/probe-poke.md) | §3.2.5 前段 |
| [探针 poke · 命中数与面积门槛口径、Unity 验收](docs/probe-poke-area.md) | §3.2.5 后段（含「Claude·Unity·Play 验收」） |
| [探针 poke · diag 诊断与外壳/法线修法](docs/probe-poke-diag.md) | §3.2.5.1 |
| [探针 poke · 假阴性两处硬卡与面积口径复查](docs/probe-poke-false-negative.md) | §3.2.5.2 /「任务 CX 复查」 |
| [工程A 回归验收口径](docs/regression-工程A.md) | §3.2.6 |
| [探针 delete_coverage（MA ShapeChanger 删除区覆盖）](docs/probe-delete-coverage.md) | §3.2.7 |
| [探针 shrink_cover（收缩键遮挡一致性）· 请求与参数](docs/probe-shrink-cover.md) | §3.2.8 前段 |
| [探针 shrink_cover · 判据改版记录（CU / CX / CT）](docs/probe-shrink-cover-rule.md) | §3.2.8 中段 |
| [探针 shrink_cover · 输出、诊断、自检与标定](docs/probe-shrink-cover-output.md) | §3.2.8 后段 |
| [R9 脚鞋选型 candidates · 请求、执行与输出](docs/foot-shoe-candidates.md) | §3.4 前段 |
| [R9 脚鞋选型 · 新增字段（CS / D2 / CW）](docs/foot-shoe-candidates-fields.md) | §3.4 中段 |
| [R9 脚鞋选型 · 教训、鞋垫面口径与验收](docs/foot-shoe-candidates-metrics.md) | §3.4 后段 |
| **T3 环绕渲图 `AuditTurntable`（原 §5–§6）** | |
| [T3 环绕渲图 · 请求与输出](docs/turntable.md) | §5 / §6 |
| [透明排序判据](docs/turntable-transparency.md) | §6「透明排序判据」 |
| **T1/T3 自检与局限（原 §7–§10）** | |
| [自检 1 · 反射用到的 GM / SDK 符号出处](docs/selfcheck-symbols.md) | §7 |
| [自检 2 · 临时改动→恢复对照表；自检 3 · 编译期](docs/selfcheck-restore.md) | §8 / §9 / §9.1 |
| [自检 3 · 运行期待验点（1–17）](docs/selfcheck-runtime.md) | §9.2 前半 |
| [自检 3 · 运行期待验点（18–22）与明确没验证的](docs/selfcheck-runtime-2.md) | §9.2 后半 / §9.3 |
| [T1/T3 已知局限](docs/known-limits.md) | §10 |
| **其它 Unity 侧工具（原 §11–§14）** | |
| [范围与口径](docs/part-inventory.md) | §11 / §11.1 |
| [输出骨架](docs/part-inventory-output.md) | §11.2 |
| [同名键跟随 key_follow 与已知局限](docs/part-inventory-key-follow.md) | §11.3 / §11.4 |
| [原理与输出](docs/build-capture.md) | §12 / §12.1–12.3.1 |
| [判据、部署、请求与验收](docs/build-capture-verify.md) | §12.4–12.8 |
| [请求序列 sequence](docs/sequence.md) | §13 / §13.1 / §13.2 |
| [请求序列 sequence · 样例、验收与局限](docs/sequence-example.md) | §13.3–13.5 |
| [单按钮对话框屏蔽 AuditDialogGuard](docs/dialog-guard.md) | §14 |
| **T2 贴合探针 `AuditFitProbe`（旧称 T2，原 `README_T2.md`）** | |
| [部署、分派、请求](docs/fit-probe.md) | 页首 / §1–§3 |
| [算法与判据（1–6）](docs/fit-probe-algorithm.md) | §4 前半 |
| [算法与判据（7–10）、v2 排除与拒绝](docs/fit-probe-algorithm-2.md) | §4 后半 / §4.5 |
| [v3 覆盖范围、输出、性能](docs/fit-probe-scope-output.md) | §4.6 / §5 / §6 |
| [自检 1：API 签名](docs/fit-probe-selfcheck-api.md) | §7 |
| [自检 2/3：恢复对照、运行期自检 A/B](docs/fit-probe-selfcheck.md) | §8 / §9 / 自检 A / 自检 B |
| [自检 C 与 v3 回归清单](docs/fit-probe-selfcheck-2.md) | 自检 C / §9.5 |
| [已知局限与首跑核对](docs/fit-probe-limits.md) | §10 |
| **T4 菜单导出 `AuditMenuDump`（旧称 T4，原 `README_T4.md`）** | |
| [部署、请求、行为](docs/menu-dump.md) | 页首 / §1–§4 |
| [输出字段](docs/menu-dump-output.md) | §5 |
| [自检与已知局限](docs/menu-dump-selfcheck.md) | §6–§8 |
| **T5 形态键依赖矩阵（旧称 T5，原 `README_T5.md`）** | |
| [流水线与子命令](docs/shapekey-matrix.md) | 页首 / §1–§4 |
| [analyze、分类与候选判据](docs/shapekey-matrix-analyze.md) | §5–§7 |
| [自检、局限、编码](docs/shapekey-matrix-selfcheck.md) | §8–§10 |
| **编译态菜单断言（旧称 W5，原 `README_menu_expect.md`）** | |
| [模式、流水线、期望文件](docs/menu-expect.md) | 页首 / §0–§2 |
| [取值转换、覆盖、匹配、退出码、报告](docs/menu-expect-rules.md) | §2.1–§3 |
| [样例、自测与局限](docs/menu-expect-samples.md) | §4 / §5 |
| **PhysBone 静态清单（旧称 T-30，原 `README_T30.md`）** | |
| [PhysBone 静态清单 pb_static.py 与 U7](docs/physbone-static.md) | 全文 |
