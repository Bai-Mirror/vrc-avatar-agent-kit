# 部署（sync_audit.py）与调用方式 <!-- nav -->

> 旧称：T1 `AuditStateDriver` / T3 `AuditTurntable` 等（原 `审查/README.md`） §1 / §2。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[交付文件清单与已做的机器验证](deliverables.md) · 下一页：[T1 状态驱动器 · 请求格式](state-driver-request.md) <!-- nav -->

## 1. 部署

T-09 起统一走 `开发工具/通用工具/审查/perception/sync_audit.py`。落点（用户 21:40 拍板，P4）是
`<工程>/Assets/AvatarAudit/{Runtime,Editor}`，各带 asmdef；旧的 `<工程>/Assets/Editor/AvatarAudit/`
（无 asmdef，编进 `Assembly-CSharp-Editor`）由脚本自动清掉。

```bash
# 1) 先看计划（不改盘）
python3 开发工具/通用工具/审查/perception/sync_audit.py "<工程>" --dry-run
# 2) 真同步
python3 开发工具/通用工具/审查/perception/sync_audit.py "<工程>"
# 2b) 源码工作区是半成品时：从指定修订取（任务 AR）
python3 开发工具/通用工具/审查/perception/sync_audit.py "<工程>" --from-git HEAD
# 3) 交付前剥离（T-23）
python3 开发工具/通用工具/审查/perception/sync_audit.py "<工程>" --strip --dry-run
python3 开发工具/通用工具/审查/perception/sync_audit.py "<工程>" --strip
# 4) 脚本自检（临时假工程 + 临时 git 仓，不碰真工程）
python3 开发工具/通用工具/审查/perception/sync_audit.py --selftest
```

`--from-git <rev>`（默认关）：不 rsync 工作区，改为逐文件 `git show <rev>:<源路径>` 取内容，
`VERSION` 的 hash 也按 git 内容算；陈旧文件仍按 `--delete` 语义清；工作区有未提交改动（含未跟踪）
时打印 ⚠ 警告并逐条列出。它的用途是「DSH 正在改 `审查/unity/` 时，别把半成品拷进工程」。

同步做三件事：

1. `rsync -a --delete` 把 `审查/unity/`（`Editor/` + `Runtime/`）铺到 `<工程>/Assets/AvatarAudit/`。
   `*.meta` 与 `VERSION` 被排除在同步**和删除**之外——`.meta` 由 Unity 生成，重跑时若被 rsync 删掉
   GUID 会全变；源里删掉一个文件时，脚本另外清掉它的孤儿 `.meta`。
2. 删除旧落点 `<工程>/Assets/Editor/AvatarAudit/`（连它自己的 `.meta`）。**只删这两个路径**：
   `Assets/Editor/` 下的其它文件不碰，空掉的 `Assets/Editor/` 也不删。
3. 写 `<工程>/Assets/AvatarAudit/VERSION`：

   ```
   # AvatarAudit deployment marker —— 由 开发工具/通用工具/审查/perception/sync_audit.py 生成，勿手改。
   source: 开发工具/通用工具/审查/unity
   hash: <64 位 sha256>
   time: <UTC ISO8601>
   files: <N>
   ```

   `hash` 是 `审查/unity/` 文件树的确定性摘要（按相对 posix 路径排序，逐文件喂 `<路径>\0<字节>\0`，
   与 mtime/绝对路径无关），T-13 的 `tool_version` 版本戳以此为准。

删除目标目录前有指纹校验：目录里没有本次部署的 asmdef / VERSION / 审查源码就拒绝，除非 `--force`。
`--strip` 是反向操作（供 T-23 交付前剥离）：删 `<工程>/Assets/AvatarAudit/` 与旧落点，不写 VERSION。

- **不要在自己这边直接对工程跑 sync**（Unity 可能开着）——把命令交给 Claude，部署后在 Unity 里
  `refresh_unity` → `read_console` 确认 0 error。
- Unity 会自己生成 `.meta`，不用手写。
- 请求文件放 `<工程>/Library/AvatarAudit/request.json`：`Library/` 不进版本库、也不会被 Unity 导入。
- 输出目录由请求里的 `out`（绝对路径）决定，建议
  `<工作区>/_长程任务_20260918/审查产出/<工程>/<run>/`。

## 2. 调用方式

| 菜单项 | 作用 |
|---|---|
| `Tools/AvatarAudit/Run Request` | 读 `<工程>/Library/AvatarAudit/request.json` → 按 `"tool"` 分派 → 跑到完 |
| `Tools/AvatarAudit/Abort Current Run` | 中止当前运行，`status.json` 写 error，并走一遍 Cleanup |

- 全过程不阻塞主线程：`EditorApplication.update` 每帧推进一步（T1 一个状态阶段 / T3 一个视角）。
- 过程中写 `<out>/status.json`：
  `{"state":"running|done|error|aborted","progress":"3/20","message":"...","tool":"state","time":"..."}`
  （`aborted`＝T-13 哨兵未过 / 状态回读断言不一致，数据保留但整批作废，见 §3.3）
- 出错写进 `status.json` 的 `message`，同时 `<out>/audit.log` 与 Console 各留一份完整堆栈。
- **T1 必须在 Play 模式**。不在 Play 时默认只写一条 error（提示先按 Play）；请求里加 `"auto_play": true`
  才会自动 `EnterPlaymode()` 并在进入后续跑（用 `SessionState` 跨域重载续接）。
  注意：场景有未保存改动时 Unity 会弹保存对话框，自动进 Play 会被卡住 —— 自动化场景下建议由调用方先按 Play。
- **T1 → T3 的串联**：T1 结束时**故意保留最后一个状态的参数值**（不做复位），所以同一轮 Play 里
  T1 跑完直接发 `tool=turntable` 请求即可拍到那批状态；T3 自己不设任何参数。
- **多条请求串成一次触发**：`{"tool":"sequence", ...}` 可在一次菜单触发里按顺序跑多个 T1/T3/T4/fit
  子请求（批量「逐套服装 设状态 → 渲图」不必触发几十次菜单），见 §13。

---
