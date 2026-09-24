# DSH 能力面与改造方法

> 派工怎么写在 [DSH派工](DSH派工.md)；这一页讲 **DSH 有哪些机制、什么时候用哪个、怎么改它**。
> 版本 `0.1.2-rc.1`。DSH 是可随任务改造的 —— 改配置、加插件、加 MCP 都是常规操作，不是例外。
>
> ⚠ **本页的所有改造动作都是 Claude 侧的活，不能派给 DSH。**
> DSH 跑在 `workspace-write` 沙箱里，写不到 `~/.dsh`。
> （这条是 DSH 自己审这份文档时指出来的 —— 它照着做会卡住。）

## 一、默认组合里已经有什么

| 机制 | 状态 | 什么时候用 |
|---|---|---|
| `compaction-basic` | ✅ 已挂 | 上下文涨到阈值自动压缩旧历史，不用管 |
| `tool-subagent`（spawn） | ✅ 已挂 | 委派给**全新上下文**的子代理 —— 要独立视角时用 |
| `tool-subagent-fork` | ✅ 已挂 | 委派给**继承父代理已完成轮次**的子代理 —— 要接着干时用 |
| `tool-subagent-control` | ✅ 已挂 | `send_message` / `interrupt_agent` / `list_agents` |
| `tool-workflow` | ✅ 已挂 | 让模型自己写编排脚本扇出子代理 |
| goal 系列（`create_goal` 等） | ✅ 已挂 | 一个会话一个长期目标，跨轮次持有 |
| `plan-mode` | ✅ 已挂 | `/plan` 进出计划模式 |
| `web_search` / `web_fetch` | ✅ 已挂 | DeepSeek 自家搜索 |
| `ralph` | ❌ 未挂 | 固定目标 + 每轮全新子代理的循环，要用得先加 |
| spill / output-retention | ❌ 未挂 | 超大工具输出转存、只回预览，需要时加 |

## 二、⚠ 实测：headless 里 goal **不会**自动续轮

`goal-round-driver` 的续轮条件是「整机空闲 + 目标已武装 + 还有额度」，
但 **headless 跑完一轮就退出**。实测给它一个「一轮建一个文件、共三个」的目标：
建了 goal、写了 `r1.txt`，然后收尾 `aborted`，`r2/r3` 没有。

**所以无人值守的长任务不要指望 headless 里的 goal。** 三条可选路：

| 路子 | 适用 | 代价 |
|---|---|---|
| **Claude 侧循环派工**（当前默认） | 大多数情况 | 每轮起停有开销，但每轮上下文干净、可核验 |
| 加 `ralph` 工具 | 一个不变的目标要磨很多轮 | 前台阻塞直到跑完；每轮全新子代理，**工作目录是唯一记忆** |
| `web` / `sdk` profile | 需要真正的持久会话 | 要另接客户端；`sdk` 是 JSON-RPC over stdio |

> `ralph` 的设计与你的 SOP 习惯天然契合：轮间只传一份有界的结构化交接报告，
> **工作目录当长期记忆** —— 也就是每轮都往 `_工程状态.md` 落盘那套做法。

## 三、⚠ 配置优先级：settings 文档压过 composition

踩过一次，症状很隐蔽：`--dump-config` 显示模型是 A，实际跑的是 B。

```
composition（cordis.yml + profile patch + home patch + --patch 覆盖层）
        ↑ 被下面这层压过
settings 文档（~/.dsh/settings.yaml）—— 运行时读取，不需要重启
```

**后果**：任何写进 `settings.yaml` 的字段，都会让对应的 `--patch` 覆盖**静默失效**。
所以默认模型故意写在 `~/.dsh/cordis.patch.yml` 而不是 `settings.yaml`。

⚠ **web UI 里手动切模型会把 `agent-default-model` 写回 settings.yaml**，
之后 `dsh_task.js --model` 就被压住了。`dsh_task.js` 的事后核验会把这种情况判 FAIL 报出来 ——
看到「实际用的模型与要求不符」就去 `settings.yaml` 里把那段删掉。

## 四、patch 写法（写反了不报错）

```yaml
- id: 已有行的id        # 覆盖已有行
  config: { ... }

- insert:               # 新增行
    - id: 新行id
      name: '@deepseek-ai/dsh-xxx'
      config: { ... }

- id: 要停用的行id      # 停用
  disabled: true
```

把覆盖写进 `insert` 不会报错，会得到**两条同 id 的行** —— 我第一次就是这么错的。
改完用 `dsh-vrc --profile headless --dump-config | grep -c "^- id: 那个id"` 自检，应为 1。

层序：bundle 各层 → profile 的 `cordis.patch.yml` → home 的 `~/.dsh/cordis.patch.yml` → `--patch`。
**home 层对三个 profile 同时生效**，共享接线放这里。

## 五、加 MCP 服务器 = 给 DSH 加能力

一条配置就够，工具名变成 `mcp__<serverName>__<tool>`，与 Claude Code 同名同形。
**MCP 返回的图像在视觉模型下会作为图片进入对话** —— 所以 Unity/Blender 的截图能直接被看。

已挂三个：`UnityMCP`、`Blender`、`agy`。加新的照抄 `~/.dsh/cordis.patch.yml` 里的写法。

`failOnStartupError: false` 是有意的：Unity 没开时 DSH 仍要能起来干别的活。
代价是**连不上时工具会静默消失**，任务书里最好写「如果没有 X 工具就直接回报 NO-X-TOOLS」，
这样区分得开「工具没挂上」和「它偷懒没调」。

## 六、agy 接入：把第三方证伪摆成工具

`通用工具/agy_mcp_server.js` 把 agy 包成 MCP，DSH 与 Claude **两侧共用同一个服务器**。

| 工具 | 用途 |
|---|---|
| `mcp__agy__agy_review` | 多模型交叉证伪。`mode`: `fast` 单模型秒评 / `panel` 3 模型 / `wide` 5 模型 |
| `mcp__agy__agy_ask` | 单次强模型问答（解读/比较/权衡），可挂只读目录与上下文文件 |

**为什么要摆成工具**（作者 2026-09-08 定）：
上下文一长就忘了调 agy，**这不是记性问题，是「它不在工具列表里」的结构问题**。
摆成工具之后模型每一轮都看得见它。想更硬，就上 `dsh-hooks-claude-code`
在固定卡口用 hook 强制触发 —— 那是确定性动作，不依赖模型自觉。

⚠ 三条使用约束（都写进工具描述里了，模型看得到）：
- 带图会撞 agy 的 ~185s 内部超时 → 服务器**自动把长边 >1600px 的图等比缩小**
- agy 对「漏洞扫描/安全审计」措辞会拒答 → 一律写「质量审查」
- **评审模型会认错对象**（实测把耳饰认成光环残件）→ 它指的位置比它给的结论可信，逐条自己复核

实测：DSH 调 `agy_review` fast 档，72 秒返回 3 条 blocker，指认准确。

## 七、还没用上、但值得知道的

- **`fork` 型子代理**：继承父代理已完成的轮次。适合「换个模型接着看同一堆证据」。
- **`session-reference`**：跨会话快照引用，可以把另一次会话的结论当上下文喂进来。
- **`schedule`**：会话内的持久提醒（`schedule_create` / `list` / `delete`）。
- **`repeat-tool-reminder`**：检测到重复同样的工具调用会提醒它换个思路。
- **`spill`**：超大工具输出转存到存储，上下文里只留预览和取回定位符 —— 扫大工程时值得加。

## 环境事实

改动了环境就同步这一节。

| 项 | 值 |
|---|---|
| 版本 | `@deepseek-ai/dsh@0.1.2-rc.1`，隔离装在 `~/.local/opt/dsh-0.1.2-rc.1`，命令 `dsh-vrc`。⚠ 全局 `dsh`（~/.npm-global）是 dsh.service 网页端用的另一版本，家目录 `~/harness/home`，别混用 |
| 配置根 | `~/.dsh`；凭据 `~/.dsh/.credentials.yaml`（**不进环境变量**） |
| **默认模型** | **`~/.dsh/cordis.patch.yml`** 的 `agent-default-model` 行 → `deepseek-flash`, effort `high`（带图派工由 dsh_task.js `--model vision` 覆盖）。⚠ **不是** settings.yaml，理由见第三节 |
| 共享接线 | `~/.dsh/cordis.patch.yml` —— MCP: `UnityMCP` / `Blender` / `agy`，对三个 profile 都生效 |
| profile | `headless`（派工主力）· `sdk`（JSON-RPC，备用） |
| web 服务 | 本机(Linux) 上是 systemd 用户服务 `dsh.service`（全局 dsh、`~/harness/home`），**不是改模用的这套**；改模派工只走 headless |
| 技能目录 | `~/.dsh/skills`。格式 `<名>/SKILL.md` 或 `<名>.md`，**必须有 name + description 的 YAML frontmatter**，缺了会被静默丢弃 |
| 沙箱 | `workspace-write`，`workspaceRoot` = 传入的 cwd；`DSH_PERMISSION_MODE` 可覆盖 |

⚠ **UnityMCP 别加 `--offline`**：uv 缓存缺 wheel 时它是「失败关闭」，
日志刷屏 `Failed to download`，工具静默消失。去掉后走网络自动补缓存。

---

相关：[DSH派工](DSH派工.md)、[子代理提示词](子代理提示词.md)、[05 多模型评审规程](../05_多模型评审规程.md)。

## DSH 里再派 DSH（嵌套派工）：沙箱里 `~/.dsh` 只读（09-22 H-03 收尾）

**触发**：任务书让 DSH 自己再跑 `dsh_task.js`（例如给每个部件开视觉子会话）。
**现象**：外层 DSH 的沙箱把 `~/.dsh` 挂成只读，内层 `dsh_task.js` 起不来（profile EROFS）。DSH 用 `HOME=<临时目录> DSH_BIN=<dsh 绝对路径>` 绕过能跑，但收尾核验去真实 `~/.dsh` 认领会话失败 ⇒ 判 FAIL（假 FAIL）。
**做法**：嵌套派工的任务书写明这条绕法，并要求它**手动读 `<临时>/.dsh/sessions/**.zstd` 复核模型与 `read_image`**，贴进报告；验收时看这份复核，别只看退出码。
**取舍**：嵌套派工省 Claude 用量（视觉会话由 DSH 自己开），代价是核验要人工补一步。
补（H-04 三路实测）：`dsh_task.js` 会清子进程的 `DSH_HOME`，所以除了 `HOME` 重定向还要显式 `DSH_BIN`（否则 `os.homedir()` 变了、指错二进制）；影子 HOME 里拷了凭据，**任务收尾必须删**。
补（09-22 22:40 修，H-05 复验）：假 FAIL 的根因是 `dsh_task.js` 按继承的 `DSH_HOME` 找会话、而子进程按影子 `HOME` 写会话；已改为按子进程 `$HOME/.dsh/sessions` 认领，H-05 嵌套 28/28 认领成功（[DSH执行要点](../50_服装发型装配/部件理解与菜单编排/DSH执行要点.md)）。上面的手动复核降为核验仍报退出码 2 时的兜底。

> → [沙箱限制](DSH能力与改造/沙箱限制.md) —— DSH 起的后台进程随会话被杀（长时批处理由 Claude 起）；沙箱里没有 GPU（渲图/GPU 活由 Claude 在沙箱外跑）；bash 里的 `/tmp` 每条命令一个新的空目录（中间产物放工作区）。
