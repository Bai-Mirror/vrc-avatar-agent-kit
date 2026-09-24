# Codex 派工（DeepSeek 高峰期的执行子代理）

> 作者 2026-09-23 定：主理是 Claude；**北京时间工作日 09-12、14-18（DeepSeek 高峰，价格翻倍）执行活改派 Codex**，其余时段照旧 DSH Flash。
> 重活由 Claude 与 Codex 承担；Gemini（agy）与 DeepSeek 仍是**独立第三方证伪源**，不因 Codex 能看图就省掉外评。
> 工具还是 `dsh_task.js`（同一套留痕、快照、锁、流水账、钩子认可），只多一个引擎开关。

## 一、怎么派

```bash
node 开发工具/通用工具/dsh_task.js [--engine auto|dsh|codex] [--model luna|terra|sol|astra|luna6] [--effort low…ultra] \
  --task-file 任务书.md --record <工程> [--lock unity] [--images a.png,b.png] --snapshot-cmd "<只读命令>" --json 结果.json
```

- `--engine auto`（缺省）：按北京时间自动选；脚本按北京时间（UTC+8）换算，与本机时区无关。
- `--model` 写 Codex 别名即自动走 Codex；flash/vision 任务书在高峰期原样派，落到 luna。
- 带图：Codex 全部档位能读图，图作为附件随消息发送；核验看 rollout 里 `input_image` 数，少一张判 FAIL。

## 二、选档（取舍）

| 档 | 模型 | 用在 | 思考档 |
|---|---|---|---|
| luna | gpt-5.6-luna | 日常执行：账本、清点、脚本、构建测试、交付文件 | medium（缺省） |
| terra / sol | gpt-5.6-terra / gpt-6-sol | 改模、Unity 装配、多步复杂代理、疑难排障、图像评审 | high；卡住再 xhigh |
| astra | gpt-6-astra | 与 Fable 协作的复杂创作（创意照策划、饰品设计推演）、思路扩展 | high～max；ultra 只在用户点名时 |

先低档，失败有证据再升档；升档理由写进施工记录。同一批材料的多个问题合并成一次派工（额度按周窗口算，重复摄入同样烧额度）。

## 三、额度与并发

- 订阅（ChatGPT 登录）按**周窗口**限额。脚本从最近 rollout 的 `rate_limits.primary.used_percent` 读余量，**≥85% 拒派**（`CODEX_MAX_USED_PCT` 可调）；触线后高峰期的活等空闲时段交 DSH，或交用户决定。
- 并发 ≤2（作者 09-23 定，`CODEX_TASK_MAX_SESS`）；与 DSH 分开计数，内存闸门（available <8 GB 不起）共用。Unity 写操作仍走交接锁，同一时刻一方持有。

## 四、实测坑（09-23）

1. **workspace-write 沙箱把 `.git` 设成只读** ⇒ ws_git 提交报 `index.lock: Read-only file system`。脚本已固定加 `--add-dir <工作区>/.git`；手工调用 `codex exec` 时也要加。
2. **`-i` 是可变参数**，后面的位置参数会被当成图片路径吞掉，报 `No prompt provided via stdin`。脚本一律用 stdin 传任务书（末尾 `-`）。
3. `--json` 的 stdout 只有 thread_id 和消息；工具明细、实际模型、收尾、额度都在 `~/.codex/sessions/**/rollout-*<thread>.jsonl`。复盘读 rollout，不听自述。
4. 主理把派工的 stdout/stderr 重定向进 `--record` 目录，会被留痕核验当成「遗留未提交」判 FAIL（C01 实例）⇒ 重定向到 `_dsh_tmp_codex_logs/`。
5. 子进程若继承 `CLAUDECODE`，ws_git 会把 DSH/Codex 的提交署名成 Claude；脚本已剔除。
6. **出图**：`image_generation` 特性默认开，`codex exec` 里可直接生图；图先落 `~/.codex/generated_images/<thread>/`，任务书要写明「复制到 <目标目录>/<文件名>」。参考图用 `--images` 附上（外观真值只用主理验收过的定妆照）。生图耗订阅额度，派前看额度行。
7. Codex 读不到 CLAUDE.md 和 Claude 记忆；脚本自动在任务书前加「派工身份」段（主理是谁、SOP 入口、不可逆动作不做）。任务书仍要自包含。

## 五、验收

与 DSH 相同，见 [改工程派工与验收](改工程派工与验收.md)：看核验块（引擎/模型/收尾/留痕/快照）、`git show --stat`、回读值。施工记录标题后缀是 `（Codex）`。
