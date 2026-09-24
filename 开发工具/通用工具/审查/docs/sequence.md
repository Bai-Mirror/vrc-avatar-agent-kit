# 请求序列 sequence <!-- nav -->

> 旧称：T1 `AuditStateDriver` / T3 `AuditTurntable` 等（原 `审查/README.md`） §13 / §13.1 / §13.2。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[T-12 构建期截获 · 判据、部署、请求与验收](build-capture-verify.md) · 下一页：[请求序列 sequence · 样例、验收与局限](sequence-example.md) <!-- nav -->

## 13. 请求序列 `sequence`（任务 BB）

一次菜单触发按顺序跑完多个 T1/T3/T4/fit 子请求。批量场景——逐套服装「设状态 → 渲图」×13、
T-16/T-19 批跑——不必再由 Claude 逐个触发 `Tools/AvatarAudit/Run Request`，只需写一个 `sequence`
请求、触发一次。实现见 `unity/Editor/AuditSequence.cs`。

```json
{
  "tool": "sequence",
  "out": "/abs/path/outfits_run",
  "stop_on_error": true,
  "avatar": "Kaguya-工程A-FaceTracking[HD(VIVE)+HD(VIVE)]",
  "steps": [
    { "tool": "state", ...一个完整的 T1 请求... },
    { "tool": "turntable", ...一个完整的 T3 请求... }
  ]
}
```

| 字段 | 默认 | 说明 |
|---|---|---|
| `out` | — | 必填，**汇总目录**绝对路径：写 `sequence_status.json` 与顶层 `status.json` / `audit.log` |
| `steps` | — | 必填，数组；元素是**完整的** T1(`state`)/T3(`turntable`)/T4(`fit`)/`menu` 请求，按数组顺序执行 |
| `stop_on_error` | `true` | 某步不是 `done`（`error` / `aborted`）就停下，后面的步记 `skipped`；`false` 则跳过失败步继续跑，整条序列结束时仍报 `error`/`aborted` |
| `avatar` | 省略 | 顶层写 `avatar` 时，**步骤里省略 `avatar` 的继承它**（不覆盖步骤自己的值）；省去 13 套里重复写头像名 |
| `timeout_seconds` | 各步之和 + 每步 10s | 整条序列的总超时；每步还可用自己的 `timeout_seconds` 单独放宽 |

步骤对象除各工具自己的字段外，多认一个 `id`（可选，缺省 `"01_<tool>"` 之类）和可选的 `out`：

- `id`：只用于 `sequence_status.json` 里标识这一步。
- `out`：省略时自动派生为 `<汇总目录>/<两位序号>_<id>`；写了就**必须是绝对路径**（否则 Begin 直接报错，
  不让相对路径落到 Unity 的当前工作目录）。每个子请求仍照常在自己的 `out` 写 `status.json`、
  `audit.log` 与工具产物，和单独触发完全一致。

**不支持嵌套 `sequence`**（`steps[].tool == "sequence"` 直接报错）：没有「状态机里的状态机」用例，
嵌套会让超时、汇总、清理都难以审计。

### 13.1 行为要点

- **逐帧步进**：完全走 `AuditRunner` 的那套 `EditorApplication.update` 泵，不新开线程，不阻塞主线程；
  每个 Tick 只推进一步，当前子工具 `Tick()` 返回 true、子 `status.json` 写 `done` 之后才开下一步。
- **状态延续**：T1 的 `Cleanup` 故意保留最后一个状态的参数值，所以 `T1(设状态) → T3(渲图)` 配对时
  T3 拍到就是 T1 设出来的那套状态；多步累积时 T1 步骤用 `"reset": "none"`。本工具不搬运状态，
  延续完全靠子工具自己的语义。
- **是否要 Play**：只要有一个子步需要 Play（`state` / `fit` / `menu`），整条序列就要求 Play——与单独跑
  T1 一样，要么已在 Play，要么顶层写 `"auto_play": true`（整条序列都会在进 Play 之后从头跑）。
- **每个子工具的临时改动**在该步结束时立刻调它的 `Cleanup` 恢复（与单请求的收尾时机一致），
  一步失败不影响前面几步已经落盘的产物。
- **顶层 `status.json`**：`{"state":"running|done|error|aborted","progress":"3/26","tool":"sequence",...}`；
  某步 `aborted`（T-13 语义）时顶层也写 `aborted`。

### 13.2 输出 `sequence_status.json`

```json
{
  "tool": "sequence", "out": "/abs/path/outfits_run",
  "state": "running|done|error|aborted", "stop_on_error": true,
  "requires_play_mode": true, "step_count": 26,
  "started_at": "...", "finished_at": "...", "current_index": 7, "failure": null,
  "steps": [
    { "index": 1, "id": "o01_t1", "tool": "state", "out": "/abs/.../01_o01_t1",
      "state": "done", "seconds": 12.34, "started_at": "...", "finished_at": "...", "error": null },
    { "index": 2, "id": "o01_t3", "tool": "turntable", "out": "/abs/.../02_o01_t3",
      "state": "running", "seconds": null, "started_at": "...", "finished_at": null, "error": null }
  ]
}
```

`state`：`pending`（还没开始）/ `running` / `done` / `error` / `aborted` / `skipped`（前一步失败被跳过）。
