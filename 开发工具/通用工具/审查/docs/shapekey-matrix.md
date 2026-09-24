# T5 形态键依赖矩阵 t5_shapekey_matrix.py · 流水线与子命令 <!-- nav -->

> 旧称：T5（原 `审查/README_T5.md`） 页首 / §1–§4。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 下一页：[T5 形态键依赖矩阵 · analyze、分类与候选判据](shapekey-matrix-analyze.md) <!-- nav -->

# T5 · 形态键依赖矩阵 `t5_shapekey_matrix.py` —— 生成 T1 请求、合并轮盘区间、分析依赖关系

> 目标：把「哪个开关动了哪个形态键、谁该收谁没收、脚型键绑对了没有」从**肉眼比对**变成**数据**。
> 依附工具：T1 `AuditStateDriver`（跑状态、读可见渲染器与形态键）、T4 `AuditMenuDump`（导出 `params.json`）。
> 本工具是**纯 Python 3 标准库**脚本：不启动 Unity、不调 MCP、不碰工程；只读输入、只写 `--out`。
> 设计依据：`_长程任务_20260918/派工/` 任务 P；手工验证样本见
> `_长程任务_20260918/审查产出/工程A/t1_sweep_outfit_parts/`。

---

## 1. 交付物与典型流水线

| 文件 | 作用 |
|---|---|
| `开发工具/通用工具/审查/t5_shapekey_matrix.py` | 本工具（唯一代码文件） |
| `README_T5.md` | 本页 |

典型流水线（工程A 这类「多套服装 + 部位开关」的头像）：

```bash
T5=开发工具/通用工具/审查/t5_shapekey_matrix.py
# ① 轮盘细扫：每个 Float 轮盘 0..1 各取 65 个点，写 T1 请求
python3 $T5 slots --params <工程>/t4_menu/params.json --avatar "<头像根名>" \
        --out <run>/slots_scan --step 1/64
#    → 把 <run>/slots_scan/t1_request_slots.json 复制成
#      <工程>/Library/AvatarAudit/request.json，在 Play 里跑 T1
# ② 合并轮盘区间
python3 $T5 slots-reduce --t1 <run>/slots_scan --out <run>/slots.json
# ③ 生成开关 sweep 请求（整套 × 单关 × 全关 + 其余开关）
python3 $T5 sweep --params <工程>/t4_menu/params.json --slots <run>/slots.json \
        --avatar "<头像根名>" --out <run>/sweep
#    → 把 <run>/sweep/t1_request_sweep.json 复制成 request.json 再跑一次 T1
# ④ 分析
python3 $T5 analyze --t1 <run>/sweep --sweep <run>/sweep/t1_request_sweep.json \
        --out <run>/matrix
#    → <run>/matrix/matrix.json + <run>/matrix/matrix.md
```

> T1 部署/请求字段见 `README.md`；`params.json` 字段见 `README_T4.md`。
> 本工具不复制任何文件到工程；`request.json` 的搬运由调用方做（见两步之间的注释）。

四个子命令：

| 子命令 | 一句话 | 关键输入 | 关键输出 |
|---|---|---|---|
| `slots` | 每个 Float 轮盘 0→1 细扫 | `params.json` | `t1_request_slots.json`、`slots_plan.json` |
| `slots-reduce` | 按签名把细扫结果压成区间 | T1 输出目录（+ `slots_plan.json`） | `slots.json` |
| `sweep` | 整套 × 单关 × 全关 + 其余开关 | `params.json`、`slots.json`、可选 `groups.json` | `t1_request_sweep.json`、`groups_used.json` |
| `analyze` | T1 输出 → 依赖矩阵 | T1 输出目录、sweep 请求 | `matrix.json`、`matrix.md` |

---

## 2. `slots`：轮盘细扫

```
slots --params <t4 params.json> --avatar <名> --out <目录> [--step 1/64]
      [--only 正则] [--exclude 正则] [--settle-frames 30]
```

- 选参数：`value_type_name == "Float"` 且 `menu_value_kinds` 含 `radial`（「轮盘」）。T4 没导出类型的
  Float 参数不入选；用 `--only/--exclude`（对参数名正则）可进一步限制，例如面捕用
  `--exclude '^FT/'` 排除。
- 取值：从 **0 到 1** 均分，**含 0 和 1**。`--step 1/64` → 65 个点；也接受小数（如 `0.05`）。
- 每个取值一个状态，其余参数不写（T1 会把「用户可控参数」复位到启动默认值，见 README.md §3）。
- 请求里固定 `volatile_probe=false`：细扫要的是确定性，自动播放的面部键只会污染签名。

输出：

- `t1_request_slots.json`：标准 T1 请求（`tool=state`，`out` 指向同一目录）。
- `slots_plan.json`：`values`（全部取值）+ 每个轮盘的 `state_ids`（`slot__<参数>__<序号>`）、
  `labels`/`label_count`、`menu_paths`。`slots-reduce` 靠它把 state 文件对回取值。

> 状态数 = 轮盘数 × 取值数。工程A 有 20 个 Float 轮盘，`1/64` 就是 1300 个状态；超过 2000 会写
> warning。首跑建议 `--step 1/4` 试通流程，正式再细扫。

---

## 3. `slots-reduce`：把细扫压成区间

```
slots-reduce --t1 <T1 输出目录> --out slots.json [--params <params.json>] [--step 1/64]
```

- 签名 = **可见渲染器集合 + 非零形态键集合**（键用 `(渲染器路径, 形态键名)`）。
  `state_<id>.json` 里 `visible = activeInHierarchy && enabled`；非零键只收 `|值| > blendshape_epsilon`
  （取 `states.json.blendshape_epsilon`，缺省 1e-4）。
- **相邻**取值签名相同 → 合并成一个区间，输出 `[lo, hi]`、`recommended`（区间中点）、
  `value_count`、`visible_count`、`nonzero_key_count`、`appeared`/`disappeared`（相对上一区间）、
  以及区间内最后一次采样的完整签名。
- `narrow`：区间宽度 `hi-lo < 2×step` 时标出（单点区间、两点区间都算）——这种区间很可能是过渡帧或
  噪声，T1 复跑时应确认。
- `label_mismatch`：区间数与菜单 `radial_labels` 数量不一致时写出。T4 的 `radial_labels` 为空时
  该字段为 `null`（工程A 就是空，无从比较）。
- 缺少某个取值的 state 文件时，在该点**断开**不跨过合并，并写 warning。

`slots.json` 结构（节选）：

```json
{ "tool": "t5_shapekey_matrix.slots-reduce", "step": 0.25,
  "slots": { "A2_Hair": {
      "interval_count": 3, "label_count": null, "label_mismatch": null,
      "intervals": [
        { "lo": 0.0, "hi": 0.0, "recommended": 0.0, "narrow": true,
          "value_count": 1, "visible_count": 1, "nonzero_key_count": 1,
          "appeared": ["Hair"], "disappeared": [],
          "signature": { "visible": ["Hair"], "nonzero_keys": ["Body_b.hair_shrink"] } } ] } } }
```

---

## 4. `sweep`：整套 × 单关 × 全关

```
sweep --params <params.json> --slots <slots.json> --avatar <名> --out <目录> [--groups groups.json]
```

状态集的构成：

1. **整套/服装类轮盘**（如 `A2_Outfit`）的每个区间推荐取值：
   - `setN__all`：该轮盘 = 推荐值，**全部服装部位 Bool = 1**（全开）；
   - `setN__<Bool>_off`：全开基础上，把某一个服装部位 Bool 置 0（单关）；
   - `setN__naked`：全关（全部服装部位 Bool = 0）。
2. **其余 Bool 开关**：`bool__<名>__on|off`，默认态下单独翻转（`on`/`off` 以 `params.json` 的
   `default_value` 决定翻转方向）。
3. **其余轮盘**：`radial__<名>__<序号>`，默认态下取 `slots.json` 里每个区间的推荐值。
4. 另加一个空参数的 `default` 基准态。

分组（哪些参数算「整套轮盘 / 服装部位」）：

- 给了 `--groups groups.json` 就用文件，`source` 记为文件路径；
- 否则**按菜单路径关键词推断**（见 §6），并把推断结果连同**证据**写进 `groups_used.json`，供人工确认。
- 推断有两个已知盲点，程序会写 `notes` 提示：找不到「整套」轮盘、找不到「服装部位」Bool。

`groups.json` 格式（字段名允许中英别名）：

```json
{ "outfit_radials": ["A2_Outfit"],
  "clothing_bools": ["A2_Coat", "A2_Top", "A2_Btm", "A2_Und", "A2_Sok", "A2_Sho"],
  "defaults": {},
  "notes": ["人工指定"] }
```

别名：`outfit_sets` / `整套`、`clothing_parts` / `服装部位`、`default_params` / `defaults`。

`groups_used.json` 里除最终分组，还写 `all_radials` / `all_bools`（方便看漏了/多选了谁）、
每个参数的匹配证据、`state_count`、`state_ids` 与每个整套的 `recommended`。

---
