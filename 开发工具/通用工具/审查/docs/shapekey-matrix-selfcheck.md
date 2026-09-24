# T5 形态键依赖矩阵 · 自检、局限、编码 <!-- nav -->

> 旧称：T5（原 `审查/README_T5.md`） §8–§10。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[T5 形态键依赖矩阵 · analyze、分类与候选判据](shapekey-matrix-analyze.md) <!-- nav -->

## 8. 自检：工程A 现成 71 状态

把手写请求 `_长程任务_20260918/审查产出/requests_工程A/t1_sweep.json` 当 `--sweep`，
把 `…/工程A/t1_sweep_outfit_parts/` 当 `--t1`：

```bash
python3 开发工具/通用工具/审查/t5_shapekey_matrix.py analyze \
  --t1 _长程任务_20260918/审查产出/工程A/t1_sweep_outfit_parts \
  --sweep _长程任务_20260918/审查产出/requests_工程A/t1_sweep.json \
  --out _长程任务_20260918/派工/tmp/t5_selfcheck
```

输出（本轮实跑，`_长程任务_20260918/派工/tmp/t5_selfcheck/`）：

```
[T5 analyze] 基准态 11 个，读入状态 71 个。
  候选：residual 0 / mis_bound 2 / no_body_keys 5 / unexpected_change 0 / out_of_range 0
  K12 豁免表命中（已在 residual 里扣除）：0 条
  residual 停用词命中（已在 residual 里扣除）：0 条
```

**要求复现的事实，逐条核对：**

| 草稿里的事实 | 本工具输出 | 结论 |
|---|---|---|
| kaguya 外套关 → `outer_shrink`/`outer_shlink`/`Outer_on` 100→0 | 见下方摘录：三条都在 `[A2_Coat off] kaguya__Coat_off` 的键变化里 | ✅ |
| MMN 关袜 → `Foot_heel_OFF` 100→0 且关鞋不变，应被 b 标出 | `[A2_Sok off] MMN__Sok_off` 键变化 100→0；`[A2_Sho off]` 键变化（无）；候选 b 列出 2 条 | ✅ |
| RePoppin/Kitty 基准态被 c 标出 | 候选 c 列出 Kitty_a/b、RePoppin_a/b/c 共 5 条 | ✅ |

`matrix.md` 摘录（原文，只删空行）：

```
# 形态键依赖矩阵（T5 analyze）

- 读入状态 71 个，基准态 11 个；blendshape_epsilon=0.0001
- 判为 Bool 的参数：A2_Btm, A2_Coat, A2_Sho, A2_Sok, A2_Top, A2_Und

## 基准态 kaguya__all
参数：`{"A2_Btm": 1, "A2_Coat": 1, "A2_Outfit": 0, "A2_Sho": 1, "A2_Sok": 1, "A2_Top": 1, "A2_Und": 1}`
可见服装件（8）：Pants | kaguya_cloth/aburaage_open | kaguya_cloth/bag | kaguya_cloth/loafer |
kaguya_cloth/outer | kaguya_cloth/outer_breast_big_open | kaguya_cloth/sailor | kaguya_cloth/stocking
非零形态键（已过滤表情/面捕类，6）：
- Body_b · outer_shrink（原名 AAO_Merged_outer_shrink_2） = 100
- Body_b · sailor_shrink（原名 AAO_Merged_sailor_shrink_1） = 100
- Hair · Outer_on = 100
- Outfit_RePoppin/(A)Shirt · Parker_on = 100
- kaguya_cloth/outer · use_bag = 100
- kaguya_cloth/sailor · outer_shlink = 100
身体上的收缩/脚型键：Body_b.outer_shrink（原名 AAO_Merged_outer_shrink_2） | Body_b.sailor_shrink（原名 AAO_Merged_sailor_shrink_1）

#### [A2_Coat off] kaguya__Coat_off（A2_Coat: 1→0）
隐藏：kaguya_cloth/outer | kaguya_cloth/outer_breast_big_open
出现：（无）
键变化：
- Body_b · outer_shrink（原名 AAO_Merged_outer_shrink_2）: 100→0
- Hair · Outer_on: 100→0
- Outfit_RePoppin/(A)Shirt · Parker_on: 100→0
- kaguya_cloth/sailor · outer_shlink: 100→0

## 基准态 MMN__all
可见服装件（17）：Pants | Outfit_MMN_黑/Bag（原 _Outfit$Outfit_MMN_黑$164/Bag） | …（16 个 MMN 部件）
非零形态键（已过滤表情/面捕类，2）：
- Body_b · Foot_heel_OFF_____足_ヒールオフ（原名 AAO_Merged_Foot_heel_OFF_____足_ヒールオフ_3） = 100
- Outfit_RePoppin/(A)Shirt · Parker_on = 100
身体上的收缩/脚型键：Body_b.Foot_heel_OFF_____足_ヒールオフ（原名 AAO_Merged_Foot_heel_OFF_____足_ヒールオフ_3）

#### [A2_Sho off] MMN__Sho_off（A2_Sho: 1→0）
隐藏：Outfit_MMN_黑/Shoes（原 _Outfit$Outfit_MMN_黑$164/Shoes）
出现：（无）
键变化：
- （无）

#### [A2_Sok off] MMN__Sok_off（A2_Sok: 1→0）
隐藏：Outfit_MMN_黑/Socks（原 _Outfit$Outfit_MMN_黑$164/Socks）
出现：（无）
键变化：
- Body_b · Foot_heel_OFF_____足_ヒールオフ（原名 AAO_Merged_Foot_heel_OFF_____足_ヒールオフ_3）: 100→0

## 自动候选
### a. residual：渲染器被隐藏，但名字与它相关的键仍非零（0 条）
- （无）
### b. mis_bound：脚型/收缩类键跟着不相干的开关走（2 条）
- 基准 MMN__all；状态 MMN__Sok_off；开关 A2_Sok：脚型/鞋跟键 Foot_heel_OFF_____足_ヒールオフ 跟着非鞋开关 A2_Sok 变化；且关鞋时这些键不变。
- 基准 ANEMONE__all；状态 ANEMONE__Sok_off；开关 A2_Sok：脚型/鞋跟键 Foot_heel_OFF_____足_ヒールオフ 跟着非鞋开关 A2_Sok 变化；且关鞋时这些键不变。
### c. no_body_keys：可见服装件多于阈值但身体没有收缩/脚型键（5 条）
- 基准 Kitty_a__all：可见服装件 6 件（>3）但身体渲染器上没有任何收缩/脚型键。
- 基准 Kitty_b__all：可见服装件 6 件（>3）但身体渲染器上没有任何收缩/脚型键。
- 基准 RePoppin_a__all：可见服装件 9 件（>3）但身体渲染器上没有任何收缩/脚型键。
- 基准 RePoppin_b__all：可见服装件 9 件（>3）但身体渲染器上没有任何收缩/脚型键。
- 基准 RePoppin_c__all：可见服装件 9 件（>3）但身体渲染器上没有任何收缩/脚型键。
### d. unexpected_change：关一件衣服时无关可见件的键变化（0 条）
- （无）
### e. out_of_range：形态键值 <0 或 >100（0 条）
- （无）
```

补充说明：除草稿列出的 8 个套装基准态（kaguya / MMN / ANEMONE / Kitty_a / Kitty_b /
RePoppin_a / RePoppin_b / RePoppin_c）外，工具还把 `kaguya__hair0/1/2_coat1` 识别为基准态
（各自有一条 `A2_Coat` 单关态），这正对应草稿的「发型 × 外套」一节；`default` 与各 `__naked`
没有单关态，不作为基准。

---

## 9. 本轮做了 / 没做 / 已知局限

**做了（可复现，全部在 `_长程任务_20260918/派工/tmp/` 下留了输出）**：

1. `analyze` 复现了 §8 表里的全部事实（residual/d/unexpected/out_of_range 在真实数据上为 0）。
2. `slots`：`--step 1/64 --only '^A2_Outfit$'` → 65 个取值，首尾恰为 0.0/1.0；
   `--step 1/4 --only 'A2_Outfit|A2_Hair'` → 10 个状态的请求。
3. `slots-reduce`：用合成的 T1 输出，`A2_Hair` 被正确压成 3 个区间（单点区间标 `narrow`）、
   `A2_Outfit` 恒定签名压成 1 个区间；缺 `slots_plan.json` 时用 `--params` 重建计划也通过。
4. `sweep`：真实 `params.json` 推断出整套轮盘 `A2_Outfit`、服装部位 6 个 Bool，生成
   `setN__all / setN__<Bool>_off / setN__naked`；`--groups` 覆盖同样通过。
5. 另用一份合成数据把 (a) residual、(b) foot/shrink、(d) unexpected_change、(e) out_of_range
   五条候选都触发了一遍，确认判定路径可跑、不抛异常。

**没做 / 需要真实 T1 才能验证**：

1. 本轮没开 Unity、没跑 T1，`slots`/`sweep` 生成的请求**没有在真实 Play 构建上执行过**；
   状态签名是否稳定（尤其 `volatile_probe=false` 下是否仍有抖动）要等实跑。
2. `slots-reduce` 只在合成数据上验证；真实轮盘（如 `A2_Outfit` 的 7 套）区间数是否等于
   实际套数、`narrow` 阈值是否合适，要拿真扫结果校准。
3. `groups` 推断依赖菜单路径命名；换一套命名习惯的头像可能全推不出来，届时用 `groups.json`。

**已知局限**：

1. 基准/单关识别只认**一个 Bool 从 1→0**。多参数联动的开关（一键脱多件）不会进单关列表；
   请让同事把这种开关拆成单参数状态，或人工看 `matrix.json` 的 `naked`/全量 diff。
2. 「相关」全靠名字 token，跨语言命名（参数叫 Coat、物体叫 outer）时，靠**被隐藏物体**搭桥；
   若商家命名完全无关联，候选 (b2)(d) 会误报或漏报。
3. 表情过滤是键名关键词，不是「这个键是不是面捕」。自定义命名（如日文表情键）需要
   用 `--filter-file` 补词。
4. `matrix.md` 的可见服装件清单是启发式，可能把配饰当服装或反之；以 `matrix.json` 里的
   原始 `path` 为准。
5. 工具不判断「收缩值该是 0 还是 100」「鞋跟键该跟鞋走还是跟袜走」这类**设计意图**——它只把
   「实际实现的连接关系」摆出来，对错由人（或 SOP/客户要求）判。

---

## 10. 文件编码

工具与输出均为 **UTF-8 无 BOM、LF**。`t5_shapekey_matrix.py` 只依赖 Python 3 标准库。
