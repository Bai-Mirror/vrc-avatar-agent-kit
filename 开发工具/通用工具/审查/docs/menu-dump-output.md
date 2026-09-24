# T4 菜单导出 · 输出字段 <!-- nav -->

> 旧称：T4（原 `审查/README_T4.md`） §5。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[T4 构建后菜单树与参数导出 AuditMenuDump · 部署、请求、行为](menu-dump.md) · 下一页：[T4 菜单导出 · 自检与已知局限](menu-dump-selfcheck.md) <!-- nav -->

## 5. 输出字段含义

### 5.1 `menu_tree.json`（完整树）

```
{
  "tool": "menu",
  "avatar": "<头像根名>",
  "avatar_path": "<场景全路径>",
  "play_mode": true,
  "generated_at": "2026-09-18 12:34:56",
  "root_label": "顶层",
  "request": { ...请求原样... },
  "descriptor": { "found": true, "type": "VRC.SDK3.Avatars.Components.VRCAvatarDescriptor" },
  "menu": {
    "found": true,                       // 是否成功读到并遍历了 expressionsMenu
    "type": "VRC.SDK3.Avatars.ScriptableObjects.VRCExpressionsMenu",
    "control_count": 37,
    "controls": [ <Control>, ... ]       // 递归
  },
  "expression_parameters": {             // 同 params.json 的 expression_parameters
    "found": true, "type": "...VRCExpressionParameters", "count": 12,
    "parameters": [ {"name","valueType","valueType_name","defaultValue","saved","networkSynced"}, ... ]
  },
  "warnings": [ "...", ... ]
}
```

`<Control>`：

| 字段 | 含义 |
|---|---|
| `name` | 控件名（空则写 `(未命名)`）。 |
| `path` | `顶层/子菜单名/控件名`。子菜单控件本身是 `顶层/子菜单名`，其子控件再接一层。 |
| `type` | ControlType 的**整数值**（SDK 反射所得；Button=101 / Toggle=102 / SubMenu=103 / TwoAxisPuppet=201 / FourAxisPuppet=202 / RadialPuppet=203）。 |
| `type_name` | 枚举成员名，如 `"Toggle"`（以 SDK 反射到的为准，不硬编码）。 |
| `parameter_name` | `control.parameter.name`；无参数时为 `null`。 |
| `value` | `control.value`（Button/Toggle 会把该参数设成这个值）。 |
| `sub_parameters` | `subParameters[].name` 列表（Radial=1 个，TwoAxis=2 个，FourAxis=4 个）。 |
| `labels` | `labels[].name` 列表（空名字段保留为空串）。 |
| `controls` | 仅 SubMenu 有：子菜单的控件数组。 |

### 5.2 `params.json`（参数表 + 菜单取值 + 引用）

```
{
  "tool": "menu", "avatar": "...", "avatar_path": "...", "play_mode": true,
  "generated_at": "...", "request": {...},
  "descriptor": {...},
  "menu_read": true, "params_read": true, "layers_read": true, "control_count": 37,

  "declared_param_names": ["HairOn", "Skirt", ...],     // expressionParameters 里声明的名字（排序）
  "menu_param_names":     ["HairOn", "Skirt", ...],     // 菜单里引用到的名字（排序）

  "parameters": [ <ParamAgg>, ... ],                    // 声明的 ∪ 菜单引用的，按名字排序
  "expression_parameters": {...},                       // 参数表（同 menu_tree.json）
  "menu_params_undeclared": ["Foo", ...],               // 菜单引用、expressionParameters 未声明
  "params_not_in_menu": [                              // 控制器里有、菜单里没有
    {"name":"GestureLeft", "layers":["FX[4]"], "declared_in_expression":false, "likely_builtin":true},
    ...
  ],
  "controller_parameters": [ <Layer>, ... ],
  "warnings": [ ... ]
}
```

`<ParamAgg>`：

| 字段 | 含义 |
|---|---|
| `name` | 参数名。 |
| `declared_in_expression` | 是否出现在 `expressionParameters`。 |
| `value_type` / `value_type_name` | ValueType 整数值 / 名字（`Int`=0、`Float`=1、`Bool`=2）；未声明为 `-1` / `null`。 |
| `default_value` / `saved` / `network_synced` | 声明参数的三项属性；未声明为 `null`。 |
| `menu_values` | **菜单里真实出现过的离散值**（去重升序）。Button/Toggle 取 `Control.value`；Bool 参数恒记 1；Int 参数取 floor。Radial/轴的连续参数这里通常为空。 |
| `menu_value_kinds` | 该参数被哪些控件类型引用：`button` / `toggle` / `radial` / `axis2` / `axis4`。 |
| `suggested_values` | **给 T1 选组合的建议值**，与 `menu_values` 明确分开：Bool 补 0；Radial 补 0/0.25/0.5/0.75/1 与按 labels 数量推算的档位；TwoAxis/FourAxis 补 -1/-0.5/0/0.5/1；Int/Float 补 0。 |
| `radial_labels` | 引用该参数的 Radial 控件的 labels 名。 |
| `radial_label_derived` | 由 labels 数量推算的档位：N 个标签 → 区间中点 `(i+0.5)/N`，N>1 另加端点 `i/(N-1)`。 |
| `referenced_by` | 引用该参数的控件路径列表。 |

`<Layer>`（`controller_parameters`）：

| 字段 | 含义 |
|---|---|
| `index` | `baseAnimationLayers` 下标。 |
| `layer_type` / `layer_type_int` | `AnimLayerType` 名 / 整数值（Base/Additive/Gesture/Action/FX…）。 |
| `is_default` | 该层是否是 SDK 默认层。 |
| `controller` / `controller_type` | 控制器资产名 / CLR 类型名（`AnimatorController` 或 `AnimatorOverrideController`）。 |
| `parameters` | `[{name, type, type_name}]`，`type` 是 `AnimatorControllerParameterType`（Float=1/Int=3/Bool=4/Trigger=9）。 |

> `params_not_in_menu` 的比较口径是「控制器参数名 ∉ 菜单引用参数名」，**不是**与
> `expressionParameters` 比。VRChat/GM 内置参数会大量出现在这里，用 `likely_builtin` 标出来，别当成缺陷。

### 5.3 `menu_tree.md`（人读）

- 第一节「缩进树」：每行 `- <路径> · <类型>(<整数>) · <参数=值>`，子菜单缩进；
  Radial 显示 `参数=radial(0..1)`、轴显示 `axis(-1..1)`、SubMenu 显示 `(子菜单)`。
- 第二节「参数速查」：Markdown 表格，列为 参数 / 声明类型 / `menu_values` / `suggested_values` / 引用控件数。
- 第三节 `params_not_in_menu`、第四节 `menu_params_undeclared`（带一句「不同步」提示）。

Claude 选组合时以 `suggested_values` 为候选、以 `menu_values` 为「菜单真实有这些档」的证据；
两者不一致时（例如 Radial 的连续取值）以 `menu_values` 为空 + `suggested_values` 为准。

---
