# T3 环绕渲图 · 请求与输出 <!-- nav -->

> 旧称：T1 `AuditStateDriver` / T3 `AuditTurntable` 等（原 `审查/README.md`） §5 / §6。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[T1 输出格式 · states.json 字段口径](state-driver-states-fields.md) · 下一页：[T3 · 透明排序判据](turntable-transparency.md) <!-- nav -->

## 5. T3 请求格式

```json
{
  "tool": "turntable",
  "avatar": "Kaguya-工程A-FaceTracking[HD(VIVE)+HD(VIVE)]",
  "out": "/abs/path",
  "size": 1024,
  "bg": [0, 1, 0],
  "targets": [ { "bone": "Head", "radius": 0.45 }, { "bone": "LeftFoot", "radius": 0.35 } ],
  "azimuths": 8,
  "elevations": [-20, 0, 35],
  "fov": 30,
  "transparency_check": true,
  "vanish_threshold": 0.05,
  "only_renderers": ["Body", "Glove"],
  "hide_renderers": ["Skirt"]
}
```

| 字段 | 默认 | 说明 |
|---|---|---|
| `size` | 1024 | 正方形边长，钳到 64..4096 |
| `bg` | `[0,1,0]` | 纯色背景（0–1 空间） |
| `targets` | Head 0.45 / Chest 0.8 / LeftFoot 0.4 / RightFoot 0.4 | 每项 `bone`（`HumanBodyBones` 名，找不到时退回按层级名字找）+ `radius`（相机到骨骼的世界距离，米） |
| `azimuths` | 8 | 方位角个数，从角色**正前方**（`avatar.transform.forward`）起算，均分 360° |
| `elevations` | `[-20,0,35]` | 仰角（度），钳到 ±89 |
| `fov` | 30 | 相机垂直 FOV |
| `transparency_check` | true | 是否做透明排序检测 |
| `vanish_threshold` | 0.05 | 消失率阈值，`flagged = vanish_ratio >= vanish_threshold` |
| `only_renderers` | 省略 | 可选，字符串数组（任务 U）；**只显示**匹配这些串的渲染器，其余渲染器的 `enabled` 在渲图期间置 false。元素也可以是 `{name}`/`{path}`/`{renderer}` 对象。匹配按 **GameObject 名 / 相对头像层级路径 / 场景完整路径的子串**（不区分大小写）。用途：手被裙子挡住时 `["Body","Glove"]` 只渲身体 + 手套。配不到的串记 warning |
| `hide_renderers` | 省略 | 可选，字符串数组（任务 U）；在 `only_renderers` 的基础上再隐藏匹配这些串的渲染器。和 `only_renderers` 都作用于**渲图前的可见集合**，所以被隐藏的渲染器不会进入透明检测候选（`transparency.json.candidates` 里也不会出现） |
| `transparent_queue_min` | 2501 | 只把 `renderQueue > 此值` 的材质槽当候选；Opaque 2000 / Cutout 2450 被排除，lilToon 透明·Refraction·Fur 通常 ≥ 2460。若某厂商把透明槽设在 2460 一档（工程A 的 `Tea_GoldenHour(Hair)` 就是 q2460），默认 2501 不会把它当候选——怀疑这类槽时把它降到 2400 再跑一次 |
| `t_min` | 0.15 | 只在掩码内且像素透光率 `t >= t_min` 的地方统计 behind / vanished（理由见 §6） |
| 其它 | | `color_epsilon`(0.03)、`min_mask_px`(200)、`min_behind_px`(100)、`save_flagged_limit`(60)、`culling_mask`(不填则用场景主相机的)、`timeout_seconds`(3600)；`mask_layer`(31) 仅为兼容旧请求保留，第二版改用 `renderer.enabled` 隔离，不再使用 |

`only_renderers` / `hide_renderers` 的完整示例（「手被裙子挡住时，只渲身体 + 手套」）：

```json
{
  "tool": "turntable",
  "avatar": "Kaguya-工程A-FaceTracking[HD(VIVE)+HD(VIVE)]",
  "out": "/abs/path",
  "targets": [ { "bone": "Head", "radius": 0.45 }, { "bone": "LeftHand", "radius": 0.25 },
               { "bone": "RightHand", "radius": 0.25 } ],
  "azimuths": 12,
  "elevations": [-20, 0, 35],
  "transparency_check": true,
  "only_renderers": ["Body", "Glove"],
  "hide_renderers": ["Skirt", "Dress"]
}
```

这两个列表在每次渲图（含 A/B/C0/C1/M）前就设好、整个 T3 期间保持，`Cleanup` 里恢复进入前的 `enabled`；
实际匹配到哪些串、过滤后可见 / 隐藏多少，写进 `shots.json.view_filter`，并给 `status.json` 记一条日志。
**为什么用子串而不是精确名**：一个模型上常有多件 `Body_1/Body_2`、`Glove_L/Glove_R`，写 `Body` 能一次命中；
副作用是同名子串会连带命中（如 `Glove` 也会命中 `GloveBox` 之类的道具），要看 `view_filter.only_matched` 核对。

文件名：`<bone>_az<方位角>_el<仰角>.png`（同名骨骼会补 `_t<序号>`）。

---

## 6. T3 输出格式

### `shots.json`

`{tool, avatar, out, size, bg, fov, culling_mask, targets[{bone,radius,file_base,world}], shot_count, shots[...], view_filter?, warnings}`
每条 shot：`{bone, file, az, el, radius, fov, size, target_world, cam_position, cam_rotation_euler}`。
请求了 `only_renderers` / `hide_renderers` 时多一个 `view_filter`：
`{only_renderers[], hide_renderers[], only_matched[], hide_matched[], visible_after, hidden_after}`
（`*_matched` 是实际命中到渲染器的串，用来发现「写了但没匹配上」的 pattern）。

### `transparency.json`

```json
{
  "tool": "turntable.transparency", "avatar": "...",
  "model": "per-pixel dot: t=avg(C1-C0); E=C0+t*B; vanished = |A-(C0+t*bg)|<eps && |A-E|>eps",
  "vanish_threshold": 0.05, "color_epsilon": 0.03, "t_min": 0.15,
  "transparent_queue_min": 2501, "color_space": "Linear",
  "min_mask_px": 200, "min_behind_px": 100,
  "candidates": [
    { "path": "Hair/Acc", "submesh": 1, "material": "acc_q3050", "render_queue": 3050,
      "material_names": ["body", "acc_q3050"], "render_queues": [2000, 3050] }
  ],
  "candidate_count": 9, "record_count": 216, "flagged_count": 3,
  "records": [
    { "target": "Head", "az": 45, "el": 0, "shot_file": "Head_az45_el0.png",
      "renderer_path": "Hair/Acc", "submesh": 1, "material": "acc_q3050", "render_queue": 3050,
      "material_names": ["body", "acc_q3050"], "render_queues": [2000, 3050],
      "mask_px": 4210, "behind_px": 3100, "vanished_px": 900,
      "t_p50": 0.82, "model_error_p50": 0.011,
      "vanish_ratio": 0.29, "flagged": true, "skipped": false,
      "vanished_owners": [ { "renderer_path": "Hair/Hair_GoldenHour", "share": 0.91 } ] }
  ],
  "flagged_images": [ { "target": "Head", "az": 45, "el": 0, "renderer_path": "Hair/Acc", "submesh": 1,
                        "material": "acc_q3050", "vanish_ratio": 0.29,
                        "A": "tr_37_A.png", "B": "tr_37_B.png", "C0": "tr_37_C0.png",
                        "C1": "tr_37_C1.png", "M": "tr_37_M.png", "C": "tr_37_C0.png" } ],
  "warnings": []
}
```

- 候选单位是 `(renderer_path, submesh)`；`material` / `render_queue` 是该槽自己的，`material_names` / `render_queues`
  仍是整个渲染器的（兼容第一版读法）；
- `skipped: true` 表示第 k 槽的掩码像素 < `min_mask_px`（这个槽在这个视角太小 / 被挡住），不参与判定；
- `vanish_ratio: null` 表示 `behind_px < min_behind_px`（第 k 槽后面本来就没什么东西，比值没意义）；
- `t_p50` 是掩码像素透光率的中位数；`model_error_p50` 是「`t >= t_min` 且不 vanished」像素上 `|A−E|` 的中位数；
- `vanished_owners` 只在 flagged 时给，对除 R 外的可见渲染器做一次 ID 渲染统计出来（前 3 名，share 分母是能成功解码的 vanished 像素数）；
- 被标记的存 A/B/C0/C1/M 五张 PNG（`tr_<记录序号>_A|B|C0|C1|M.png`），超过 `save_flagged_limit` 只留数值并在
  `flagged_images[].note` 里写明。`C` 是 `C0` 的别名，供第一版读法使用。
