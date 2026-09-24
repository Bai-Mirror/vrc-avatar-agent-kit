# T1 · reset 模式与切换残留测试 <!-- nav -->

> 旧称：T1 `AuditStateDriver` / T3 `AuditTurntable` 等（原 `审查/README.md`） §3.0.3。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[T1 · 回调隔离、头像解析、GestureManager 接管](state-driver-isolation.md) · 下一页：[T1 纯数据探针总览 · grab_chain / coincident](probes.md) <!-- nav -->

### 3.0.3 `reset` 模式与切换残留测试（任务 Q）

| `reset` | 行为 | 典型用途 |
|---|---|---|
| `declared`（默认） | 每状态前把可复位参数设回 `VRCExpressionParameters.defaultValue`；读不到才退回启动实值并逐个 warning | 常规多状态对比（状态差异只归因于该状态自己的参数） |
| `startup` | 设回 T1 启动瞬间实值（值来源为旧行为；驱动器排除仍生效，见任务 AD） | 复现历史批次 / 与旧结论对齐 |
| `none` | 完全不复位，状态接着上一状态累积 | **切换残留测试**（故意让上一档的残留带进下一档） |

**做切换残留测试时**：必须用 `"reset": "none"`，并在请求里**显式列出序列**（每个状态只写这一档要拨的参数，
数组顺序就是实际拨动顺序）。否则观察到的「残留」是上一次运行留下来的、不是本次序列造成的，结论不可信。
这时 `state_*.json` 的 `reset_values_source` 会是 `none`、`reset_count=0`；`states.json.defaults_snapshot`
仍是声明默认（供对照，不参与复位）。示例：

```json
{ "tool": "state", "reset": "none", "avatar": "...", "out": "/abs/path",
  "states": [
    { "id": "s1_hood_on",   "params": { "A2_Outfit": 1.0 } },
    { "id": "s2_then_sok0", "params": { "A2_Sok": 0 } },
    { "id": "s3_only_hood","params": { "A2_Outfit": 0.214286 } }
  ] }
```

`s3_only_hood` 里 `A2_Sok` 保持在 `s2` 的 0——这正是「切换残留」要观察的现象。把它和同一序列用
`"reset": "declared"` 再跑一遍对比，就能把「档位没清干净」与「档位本身无效」分开。

**任务 AD：为什么默认还要跳过「参数驱动器维护的内部参数」**（与上面「默认值漂移」是两个不同的坑，别混）：

- **症状**：`reset: declared` 在每个状态前把「表达参数 − VRChat 内置」全部复位到声明默认值。其中有一类参数
  不是给用户点的，而是 `VRCAvatarParameterDriver` 维护的内部状态。工程B_Milfy 实测：厂商参数 `Slippers_OFF`
  由「鞋子」部位层 ON/OFF 状态与整套切换层的驱动器写入，声明默认值 `0` = 显示拖鞋；复位把它写回 `0`，而
  **同一套服装内切换时驱动器不会再触发** → 13 套里 12 套「只关袜子」都出现了小熊拖鞋（和该套自己的鞋叠穿）。
  同一批状态用 `reset: none` 按真实操作顺序切，拖鞋不出现 → **工具假象**，不是工程缺陷。
  证据：`_长程任务_20260918/审查产出/工程B/t1_sweep/`（假象）、`t1_slipper_seq/`（真实顺序）。
- **为什么**：复位集合的语义是「用户可控参数的起点」，但表达参数里混进了驱动器内部状态——它们由动画层
  在切换时写入，没有「用户起点」这回事。复位它们等于在驱动器不重新触发的情况下单方面改写状态。
- **与「默认值漂移」的区别**：漂移（任务 Q）是**复位值取错来源**（拿上次残留当默认），两次运行之间漂移；
  本坑是**复位集合混进了不该复位的参数**，同一次运行内、每个状态都会发生。两者都表现为「档位切换结果不
  可信」，但修法不同：前者改正默认值来源，后者从复位集合里剔除被驱动参数。
- **修法**：Play 模式下扫头像**构建后**各可播放层控制器（`descriptor.baseAnimationLayers` +
  `specialAnimationLayers` 的 `animatorController`；`isDefault` 层经 GM 的
  `ModuleVrc3Styles.Data.ControllerOf(type)` 取 GM 实际在用的内置控制器；再加 `Animator.runtimeAnimatorController`）
  全部状态与子状态机上的 `VRCAvatarParameterDriver`，收集其写入的参数名（`Set`/`Add`/`Random`/`Copy` 的
  `name`）。`reset:declared`（及 `startup`）的复位集合再减去「被写入且用户不能直接点」的参数；
  参数若同时直接出现在表达菜单控件里（用户也能点）则仍复位，但在 warnings 与
  `states.json.driver_targets_user_clickable` 里列出。`reset_driver_targets: true` 可关掉这个排除（旧行为）。
  扫描只读资产，不改场景；反射拿不到 GM 内置控制器时只记 warning，不影响自定义层控制器里的驱动器。
- **做整套/部位组合扫描时的建议**：**同一套服装内的状态按真实操作顺序排列，并用 `reset: none`**——这样
  驱动器会像 VRChat 里一样在切换时重新触发，观察到的就是真实穿脱结果；或者依赖本修正（`reset: declared`
  默认已会跳过被驱动参数）。两者取其一即可，但**别用「每个状态都从声明默认重置」的方式去扫同一套内的组合**
  ——那正是本坑的触发条件。
