# 请求序列 sequence · 样例、验收与局限 <!-- nav -->

> 旧称：T1 `AuditStateDriver` / T3 `AuditTurntable` 等（原 `审查/README.md`） §13.3–13.5。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[请求序列 sequence](sequence.md) · 下一页：[单按钮对话框屏蔽 AuditDialogGuard](dialog-guard.md) <!-- nav -->

### 13.3 样例：13 套服装逐套「T1 全穿 → T3 躯干四面」

Milfy 的 `RJ_Outfit` 是 **13 档**轮盘（0 素体默认装 /1 兽爪比基尼 /2 傲娇女仆 /3 兔天使 /
4 兔子居家服 /5 垂耳兔 /6 雪花罗曼史 /7 雾感针织 /8 Petal Drape /9 LUNALICE /10 Rogue Noir /
11 NOEM 卫衣 /12 Peridot——不是 26 档，证据 `工程B/_审查准备_20260918.md:28`）。
轮盘按 `i/n` 取档（`n=13`），13 步样例取的就是各档中点 **`(i+0.5)/13`**（`i=0..12`，即
`1/26、3/26、…、25/26`）；**第 1 步是第 0 档「素体默认装」，不是外购套装**。
每套两步：T1 用 `reset:none` 只拨本套那一档（接着上一步的状态），T3 拍躯干（Chest）四方位、无透明检测。
`out` 全省略，自动落到汇总目录下的 `01_…`、`02_…`；`avatar` 由顶层继承。**数值/档位以该工程
`params.json` / `gear_slots` 的实际档位为准**。

```json
{
  "tool": "sequence",
  "out": "/abs/path/audit/milfy_outfits_13_run",
  "stop_on_error": true,
  "avatar": "Milfy",
  "steps": [
    { "id": "o01_t1", "tool": "state", "reset": "none", "states": [ { "id": "o01_on", "params": { "RJ_Outfit": 0.0384615385 } } ] },
    { "id": "o01_t3", "tool": "turntable", "size": 640, "bg": [0,1,0], "targets": [ { "bone": "Chest", "radius": 0.5 } ], "azimuths": 4, "elevations": [0], "fov": 30, "transparency_check": false },
    { "id": "o02_t1", "tool": "state", "reset": "none", "states": [ { "id": "o02_on", "params": { "RJ_Outfit": 0.1153846154 } } ] },
    { "id": "o02_t3", "tool": "turntable", "size": 640, "bg": [0,1,0], "targets": [ { "bone": "Chest", "radius": 0.5 } ], "azimuths": 4, "elevations": [0], "fov": 30, "transparency_check": false },
    { "id": "o03_t1", "tool": "state", "reset": "none", "states": [ { "id": "o03_on", "params": { "RJ_Outfit": 0.1923076923 } } ] },
    { "id": "o03_t3", "tool": "turntable", "size": 640, "bg": [0,1,0], "targets": [ { "bone": "Chest", "radius": 0.5 } ], "azimuths": 4, "elevations": [0], "fov": 30, "transparency_check": false },
    { "id": "o04_t1", "tool": "state", "reset": "none", "states": [ { "id": "o04_on", "params": { "RJ_Outfit": 0.2692307692 } } ] },
    { "id": "o04_t3", "tool": "turntable", "size": 640, "bg": [0,1,0], "targets": [ { "bone": "Chest", "radius": 0.5 } ], "azimuths": 4, "elevations": [0], "fov": 30, "transparency_check": false },
    { "id": "o05_t1", "tool": "state", "reset": "none", "states": [ { "id": "o05_on", "params": { "RJ_Outfit": 0.3461538462 } } ] },
    { "id": "o05_t3", "tool": "turntable", "size": 640, "bg": [0,1,0], "targets": [ { "bone": "Chest", "radius": 0.5 } ], "azimuths": 4, "elevations": [0], "fov": 30, "transparency_check": false },
    { "id": "o06_t1", "tool": "state", "reset": "none", "states": [ { "id": "o06_on", "params": { "RJ_Outfit": 0.4230769231 } } ] },
    { "id": "o06_t3", "tool": "turntable", "size": 640, "bg": [0,1,0], "targets": [ { "bone": "Chest", "radius": 0.5 } ], "azimuths": 4, "elevations": [0], "fov": 30, "transparency_check": false },
    { "id": "o07_t1", "tool": "state", "reset": "none", "states": [ { "id": "o07_on", "params": { "RJ_Outfit": 0.5 } } ] },
    { "id": "o07_t3", "tool": "turntable", "size": 640, "bg": [0,1,0], "targets": [ { "bone": "Chest", "radius": 0.5 } ], "azimuths": 4, "elevations": [0], "fov": 30, "transparency_check": false },
    { "id": "o08_t1", "tool": "state", "reset": "none", "states": [ { "id": "o08_on", "params": { "RJ_Outfit": 0.5769230769 } } ] },
    { "id": "o08_t3", "tool": "turntable", "size": 640, "bg": [0,1,0], "targets": [ { "bone": "Chest", "radius": 0.5 } ], "azimuths": 4, "elevations": [0], "fov": 30, "transparency_check": false },
    { "id": "o09_t1", "tool": "state", "reset": "none", "states": [ { "id": "o09_on", "params": { "RJ_Outfit": 0.6538461538 } } ] },
    { "id": "o09_t3", "tool": "turntable", "size": 640, "bg": [0,1,0], "targets": [ { "bone": "Chest", "radius": 0.5 } ], "azimuths": 4, "elevations": [0], "fov": 30, "transparency_check": false },
    { "id": "o10_t1", "tool": "state", "reset": "none", "states": [ { "id": "o10_on", "params": { "RJ_Outfit": 0.7307692308 } } ] },
    { "id": "o10_t3", "tool": "turntable", "size": 640, "bg": [0,1,0], "targets": [ { "bone": "Chest", "radius": 0.5 } ], "azimuths": 4, "elevations": [0], "fov": 30, "transparency_check": false },
    { "id": "o11_t1", "tool": "state", "reset": "none", "states": [ { "id": "o11_on", "params": { "RJ_Outfit": 0.8076923077 } } ] },
    { "id": "o11_t3", "tool": "turntable", "size": 640, "bg": [0,1,0], "targets": [ { "bone": "Chest", "radius": 0.5 } ], "azimuths": 4, "elevations": [0], "fov": 30, "transparency_check": false },
    { "id": "o12_t1", "tool": "state", "reset": "none", "states": [ { "id": "o12_on", "params": { "RJ_Outfit": 0.8846153846 } } ] },
    { "id": "o12_t3", "tool": "turntable", "size": 640, "bg": [0,1,0], "targets": [ { "bone": "Chest", "radius": 0.5 } ], "azimuths": 4, "elevations": [0], "fov": 30, "transparency_check": false },
    { "id": "o13_t1", "tool": "state", "reset": "none", "states": [ { "id": "o13_on", "params": { "RJ_Outfit": 0.9615384615 } } ] },
    { "id": "o13_t3", "tool": "turntable", "size": 640, "bg": [0,1,0], "targets": [ { "bone": "Chest", "radius": 0.5 } ], "azimuths": 4, "elevations": [0], "fov": 30, "transparency_check": false }
  ]
}
```

T1 若还用探针/哨兵，把 `probes`/`sentinels`/`gear_slots` 等照常写在对应 `state` 步骤里；T3 若要只手/脚，
写该步自己的 `only_renderers`。步骤之间是同一轮 Play，T1 的 `reset:none` 让 13 档按真实操作顺序累积切换。

### 13.4 给 Claude 的 Unity 验收步骤

1. `sync_audit.py <工程>` 部署后，`Assets/AvatarAudit` 编译 0 error，`AuditSequence.cs` 也在其中。
2. 写一个 **2 步**小序列（1×T1 + 1×T3）到 `Library/AvatarAudit/request.json`，**先按 Play** 再
   `Tools/AvatarAudit/Run Request`：看 `<汇总>/sequence_status.json` 第 1 步 `state=done` 后才出现第 2 步
   `running`；T3 渲出来的图确实是 T1 设的那套（与单独跑 T1→T3 对比）。
3. 看 `<汇总>/status.json` 在跑时 `state=running`、`progress` 递增，跑完 `done`；
   每个子 `out/status.json` 与单独跑该请求一致。
4. 把第 2 步故意写个不存在的 `tool`：`stop_on_error=true` 时它前面一步仍 `done`、它 `error`、后面 `skipped`、
   汇总 `state=error` 且 `failure` 指到它；`stop_on_error=false` 时它后面的步继续跑，最终汇总仍 `error`。
5. 只放 T3 步骤的序列**不要求 Play**（编辑模式可直接跑）；含 T1 的序列在编辑模式应被挡并提示进 Play。
6. 中途点 `Abort Current Run`：当前步 `error`、后面 `skipped`，设备/场景能由各步 `Cleanup` 恢复
   （对照 §8 的「临时改动 → 恢复」表逐项看）。

### 13.5 已知局限

- 只做了离线编译 + 纯逻辑测试（`_长程任务_20260918/派工/tmp/bb/seqtest/`，33 项断言全过）；
  **没在 Unity 里跑过**——步与步之间的状态延续（尤其多个 T1 步骤 `reset:none`、以及
  「场景原本没有 GM、T1 每步临时建/销毁 `__AvatarAudit_GM`」）必须按 §13.4 实测。
- 不支持条件/并行/嵌套；只按数组顺序串行。
- 顶层 `status.json` 无法表达「跑到第几步」的细节，要精确定位看 `sequence_status.json` 的 `steps[]`。

---
