> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/menu-dump-output.md)

# T4 menu export · output fields <!-- nav -->

> Former name: T4 (originally `审查/README_T4.md`) §5. § numbers follow the original text; for cross-page § references see the [documentation index](../README.md). <!-- nav -->
> Previous page: [T4 Post-build menu tree and parameter export AuditMenuDump · deployment, requests, behavior](menu-dump.md) · Next page: [T4 menu export · self-check and known limitations](menu-dump-selfcheck.md) <!-- nav -->

## 5. Meaning of output fields

### 5.1 `menu_tree.json` (full tree)

```
{
  "tool": "menu",
  "avatar": "<头像根名>",
  "avatar_path": "<场景全路径>",
  "play_mode": true,
  "generated_at": "2026-09-18 12:34:56",
  "root_label": "顶层",
  "request": { ...request verbatim... },
  "descriptor": { "found": true, "type": "VRC.SDK3.Avatars.Components.VRCAvatarDescriptor" },
  "menu": {
    "found": true,                       // whether expressionsMenu was successfully read and traversed
    "type": "VRC.SDK3.Avatars.ScriptableObjects.VRCExpressionsMenu",
    "control_count": 37,
    "controls": [ <Control>, ... ]       // recursive
  },
  "expression_parameters": {             // same as expression_parameters in params.json
    "found": true, "type": "...VRCExpressionParameters", "count": 12,
    "parameters": [ {"name","valueType","valueType_name","defaultValue","saved","networkSynced"}, ... ]
  },
  "warnings": [ "...", ... ]
}
```

`<Control>`:

| Field | Meaning |
|---|---|
| `name` | Control name (written as `(未命名)` if empty). |
| `path` | `顶层/子菜单名/控件名`. A submenu control itself is `顶层/子菜单名`; its child controls add one more level. |
| `type` | The **integer value** of ControlType (obtained via SDK reflection; Button=101 / Toggle=102 / SubMenu=103 / TwoAxisPuppet=201 / FourAxisPuppet=202 / RadialPuppet=203). |
| `type_name` | Enum member name, e.g. `"Toggle"` (whatever SDK reflection returns; not hard-coded). |
| `parameter_name` | `control.parameter.name`; `null` when there is no parameter. |
| `value` | `control.value` (Button/Toggle set the parameter to this value). |
| `sub_parameters` | List of `subParameters[].name` (Radial = 1, TwoAxis = 2, FourAxis = 4). |
| `labels` | List of `labels[].name` (empty names are kept as empty strings). |
| `controls` | SubMenu only: the submenu's control array. |

### 5.2 `params.json` (parameter table + menu values + references)

```
{
  "tool": "menu", "avatar": "...", "avatar_path": "...", "play_mode": true,
  "generated_at": "...", "request": {...},
  "descriptor": {...},
  "menu_read": true, "params_read": true, "layers_read": true, "control_count": 37,

  "declared_param_names": ["HairOn", "Skirt", ...],     // names declared in expressionParameters (sorted)
  "menu_param_names":     ["HairOn", "Skirt", ...],     // names referenced in the menu (sorted)

  "parameters": [ <ParamAgg>, ... ],                    // declared ∪ menu-referenced, sorted by name
  "expression_parameters": {...},                       // parameter table (same as menu_tree.json)
  "menu_params_undeclared": ["Foo", ...],               // referenced by the menu, not declared in expressionParameters
  "params_not_in_menu": [                              // present in controllers, not in the menu
    {"name":"GestureLeft", "layers":["FX[4]"], "declared_in_expression":false, "likely_builtin":true},
    ...
  ],
  "controller_parameters": [ <Layer>, ... ],
  "warnings": [ ... ]
}
```

`<ParamAgg>`:

| Field | Meaning |
|---|---|
| `name` | Parameter name. |
| `declared_in_expression` | Whether it appears in `expressionParameters`. |
| `value_type` / `value_type_name` | ValueType integer value / name (`Int`=0, `Float`=1, `Bool`=2); `-1` / `null` when undeclared. |
| `default_value` / `saved` / `network_synced` | The three attributes of a declared parameter; `null` when undeclared. |
| `menu_values` | **Discrete values that actually appear in the menu** (deduplicated, ascending). Button/Toggle take `Control.value`; Bool parameters always record 1; Int parameters take the floor. Usually empty here for continuous Radial/axis parameters. |
| `menu_value_kinds` | Which control types reference the parameter: `button` / `toggle` / `radial` / `axis2` / `axis4`. |
| `suggested_values` | **Suggested values for T1 when picking combinations**, kept clearly separate from `menu_values`: Bool adds 0; Radial adds 0/0.25/0.5/0.75/1 and the steps derived from the number of labels; TwoAxis/FourAxis add -1/-0.5/0/0.5/1; Int/Float add 0. |
| `radial_labels` | Label names of the Radial controls that reference this parameter. |
| `radial_label_derived` | Steps derived from the label count: N labels → interval midpoints `(i+0.5)/N`; for N>1 also add endpoints `i/(N-1)`. |
| `referenced_by` | List of paths of the controls that reference this parameter. |

`<Layer>` (`controller_parameters`):

| Field | Meaning |
|---|---|
| `index` | Index into `baseAnimationLayers`. |
| `layer_type` / `layer_type_int` | `AnimLayerType` name / integer value (Base/Additive/Gesture/Action/FX…). |
| `is_default` | Whether the layer is an SDK default layer. |
| `controller` / `controller_type` | Controller asset name / CLR type name (`AnimatorController` or `AnimatorOverrideController`). |
| `parameters` | `[{name, type, type_name}]`, where `type` is `AnimatorControllerParameterType` (Float=1/Int=3/Bool=4/Trigger=9). |

> The comparison basis for `params_not_in_menu` is "controller parameter name ∉ menu-referenced parameter names", **not** a comparison against
> `expressionParameters`. VRChat/GM built-in parameters will show up here in large numbers; they are flagged with `likely_builtin` — don't treat them as defects.

### 5.3 `menu_tree.md` (human-readable)

- Section 1 "Indented tree": each line is `- <路径> · <类型>(<整数>) · <参数=值>`, with submenus indented;
  Radial shows `参数=radial(0..1)`, axes show `axis(-1..1)`, SubMenu shows `(子菜单)`.
- Section 2 "Parameter quick reference": a Markdown table with columns parameter / declared type / `menu_values` / `suggested_values` / number of referencing controls.
- Section 3 `params_not_in_menu`, section 4 `menu_params_undeclared` (with a one-line "not synced" note).

When Claude picks combinations, it uses `suggested_values` as candidates and `menu_values` as evidence that "the menu really has these steps";
when the two disagree (e.g. continuous Radial values), go with empty `menu_values` + `suggested_values`.

---
