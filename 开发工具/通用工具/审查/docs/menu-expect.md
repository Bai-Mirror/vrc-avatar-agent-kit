# 编译态菜单断言 menu_expect_check.py · 模式、流水线、期望文件 <!-- nav -->

> 旧称：W5（原 `审查/README_menu_expect.md`） 页首 / §0–§2。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 下一页：[编译态菜单断言 · 取值转换、覆盖、匹配、退出码、报告](menu-expect-rules.md) <!-- nav -->

# W5 · 编译态菜单断言 `menu_expect_check.py` —— 期望格式、两种模式与覆盖口径

> 目标：把「交付说明里承诺的菜单行为」与「构建后（NDMF/VRCFury 之后）实测的状态扫描」**机械比对**，
> 输出逐条 PASS/FAIL。期望由**第二视角**（交付说明/菜单说明）写出，实测由构建后 T1 扫描给出，
> 比对由脚本做 —— 代替「在开发态工程里自验自己的假设」。
> 本工具是**纯 Python 3 标准库**脚本：不启动 Unity、不调 MCP、不碰工程；只读输入、只写 `--out`。
> 设计依据：派工 `W5_编译态菜单断言工具.md`、`P02_交付菜单验收.md`；样本见
> `_长程任务_20260918/派工/tmp/w5/`。
> 依赖工具：T4 `AuditMenuDump`（导出 `params.json`）、T1 `AuditStateDriver`（构建后状态扫描）。

---

## 0. 两种模式（先读这个）

| | 研究模式（默认） | 交付模式（`--delivery`） |
|---|---|---|
| 用途 | 局部抽查、排障、摸机制 | 交付前卡口，**不能误放行** |
| `--params` | 可选 | **必给**，否则 exit 2 |
| `source` 与每条 `note` 出处 | 不强制 | **强制**非空且非占位符，否则 exit 2 |
| `visible/hidden/shapes` 全空的 state | 拒绝（exit 2） | 拒绝（exit 2） |
| `Bool` 两态 / `Int` 各 `menu_values` | 只记录，不拦 | **强制**；缺一档即失败（exit 1） |
| 连续 `Float`/`radial`/轴 覆盖 | 允许按 `radial_labels`/边界**推测**并记录 | **必须**在顶层 `coverage` 显式声明 `gears`/`units`/`boundaries` 且写 `note`/`source` 出处；否则 exit 2 |
| `coverage` 声明解析错误 | **exit 2**（输入错误，不静默过滤/截断） | **exit 2** |
| `params.json` 参数重名 / 名单冲突 | **exit 2** | **exit 2** |
| schema 定不出档位且无声明 | 记录 | **exit 2（检查失败）** |
| 同一 `set` 命中多个 T1 状态 | 取参数最少者并记录歧义数 | **exit 2（无法唯一判定）** |
| 检查结果为空（无任何断言行） | 视为缺失 → exit 1 | **exit 2** |
| 退出码 0 的含义 | 本次写的状态全过（不代表完整） | 期望按显式约定覆盖的档/开关/边界全过（仍不代表全组合/游戏端） |

**共同底线**：`set` 只写参数名、不写任何行为断言的 state，在任何模式都被拒绝。
参数名覆盖 ≠ 行为覆盖：`Coat` 只测 `=1` 不能算覆盖了这个开关。
**连续轴不猜**：`radial_labels` 只是「引用该参数的 Radial 控件标签名」（T4 会把同一参数的多个
控件合并），不保证真实档数；交付模式必须人工写出档数/边界约定与来源，研究模式才允许推测并标注。

---

## 1. 交付物与流水线

| 文件 | 作用 |
|---|---|
| `开发工具/通用工具/审查/menu_expect_check.py` | 本工具（唯一代码文件） |
| `README_menu_expect.md` | 本页 |
| `menu_expect_check_selftest.py` | 离线独立自测（合成正反例 + 真实现有研究样例），不开 Unity |

```bash
T=开发工具/通用工具/审查/menu_expect_check.py

# ① 交付前：从交付说明写出期望.json（人工/Claude，每条带 note 出处行）
# ② 期望 → T1 请求（校验参数名与取值；slot:N 按显式约定求代表值，数值原样不改写）
python3 $T gen-request --delivery --expect 期望.json \
        --params <工程>/t4_menu/params.json --out t1_request.json
#    → 由 Claude 把 t1_request.json 复制成 <工程>/Library/AvatarAudit/request.json，
#      在 Play（构建后）触发 Tools/AvatarAudit/Run Request
# ③ 构建后实测 → 逐条比对（交付卡口）
python3 $T check --delivery --expect 期望.json --t1 <T1 输出目录> \
        --params <工程>/t4_menu/params.json --out 报告.md --json 报告.json

# 自测（纯离线，不开 Unity、不跑工程测试）
python3 开发工具/通用工具/审查/menu_expect_check_selftest.py
```

- `check` 读 T1 输出：目录（递归找 `state_*.json`）、单个 `state_*.json`、或 `states.json` 都行。
- T1/T4 的部署与请求字段见 `README.md`；`params.json` 字段见 `README_T4.md`。
- 本工具不往工程里复制任何文件；`request.json` 的搬运由调用方做。

---

## 2. 期望文件 `期望.json`

```json
{
  "avatar": "Kaguya-工程A-FaceTracking[HD(VIVE)+HD(VIVE)]",
  "source": "工程A/_交付/原根_A21实测报告.md:62-69",
  "coverage": {"A2_Outfit": {"gears": 7, "note": "档位表：原根_A21b补证.md:14"}},
  "states": [
    {
      "name": "MMN档 高跟鞋开",
      "set": {"A2_Outfit": "slot:1", "A2_HoleHeel": 1},
      "visible": ["HoleHeel.main", "HoleHeel.belt"],
      "hidden": ["*Outfit_MMN_黑*/Shoes", "kaguya_cloth/loafer"],
      "shapes": {"Body_b:Foot_Hiheel*": 100, "Body_b:Foot_heel_OFF*": 0},
      "note": "HoleHeel 开 → 显示高跟、隐藏整套鞋靴、Foot_Hiheel=100：菜单生成报告.md:94"
    }
  ]
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `avatar` | 是（或 `gen-request --avatar`） | 头像根名，写进 T1 请求的 `avatar`。 |
| `source` | 建议；交付模式必填 | 期望来源（交付说明/菜单说明路径与行号），写进报告头。 |
| `coverage` | 否 | 覆盖约定：`{参数名: 数组 \| {gears:N} \| {units:[...]} \| {boundaries:[...]}}`。连续 `Float`/`radial`/轴在**交付模式必须**显式声明（对象形式 + `note`/`source` 出处）；数组形式无出处，仅研究模式可用。声明只能把已知档位**加严**，**不能借它把 Bool 降成只测一态**。解析错误（未知字段/参数、小数 gears、NaN/Infinity、混入非法数值）一律 exit 2。 |
| `states[].name` | 是 | 期望状态名，报告里用它定位；**同文件内不可重复**。 |
| `states[].set` | 是 | `{参数名: 值}`；比对时按**子集**匹配 T1 状态的 `params_applied`。 |
| `states[].visible` | 否 | 应可见的渲染器；路径 / 唯一叶名 / 含 `*` 通配。 |
| `states[].hidden` | 否 | 应不可见的渲染器，写法同上。 |
| `states[].shapes` | 否 | `{"<网格>:<键名>": 期望值}`；网格与键名都可含 `*`。 |
| `states[].t1_state` | 否 | 可选，钉死匹配某个 T1 `id`（同 `set` 有多个候选时用）。 |
| `states[].note` | 建议；交付模式必填 | 出处行；`check` 在缺失/覆盖清单里原样列出。 |

> **硬规则**：每个 state 的 `visible`/`hidden`/`shapes` 至少要有一个非空，否则 exit 2。
> 只写 `set` 的状态证明不了任何行为。
