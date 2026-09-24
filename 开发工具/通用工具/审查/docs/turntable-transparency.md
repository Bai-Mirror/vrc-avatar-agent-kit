# T3 · 透明排序判据 <!-- nav -->

> 旧称：T1 `AuditStateDriver` / T3 `AuditTurntable` 等（原 `审查/README.md`） §6「透明排序判据」。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[T3 环绕渲图 · 请求与输出](turntable.md) · 下一页：[自检 1 · 反射用到的 GM / SDK 符号出处](selfcheck-symbols.md) <!-- nav -->

### 透明排序判据（为什么这么判）

候选 = 头像下 `activeInHierarchy && enabled` 的渲染器 R 的每个**材质槽 k**，满足
`sharedMaterials[k].renderQueue > transparent_queue_min`（默认 2501），且 k 落在会被渲染的槽范围内。
Unity 的材质→子网格映射：**子网格 i 使用 `mats[min(i, mats.Length-1)]`**，所以 `mats.Length > subMeshCount` 时
多出的材质槽根本不会被渲染（记 warning 并跳过），`mats.Length < subMeshCount` 时最后一个材质槽覆盖它之后的全部
子网格（掩码是它们的并集，候选里用 `slot_note` 注明）。
（任务书原文写「子网格数少于材质数时多出的材质画最后一个子网格」；对照 Unity 的实际映射，方向应是「材质数少于
子网格数时最后一个材质覆盖多出的子网格」，这里按实际规则实现并记录差异。）

**为什么从「整个渲染器」改成「(渲染器, 子网格)」**：第一版以渲染器为单位，掩码是整个渲染器的轮廓，其中大部分是
不透明子网格（头发本体）；不透明物体挡住后面的东西本来就该看不见，于是每条都被判成「消失」，消失率到 0.97，
全是误报（2026-09-18 工程A 实测）。改成逐槽后，不透明槽（queue ≤ `transparent_queue_min`）根本不进候选。

对每个候选 (R, k)、每个视角渲五张（A 就是环绕图那一张，复用）：

| 记号 | 怎么渲 | 含义 |
|---|---|---|
| **M** | 只让 R 可见（其他渲染器 `enabled=false`），R 的第 k 槽 = FlatColor 纯白、其余槽 = Invisible，背景纯黑 | 非黑像素 = 第 k 槽的屏幕掩码 |
| **C0** | 只让 R 可见，第 k 槽 = 原材质、其余槽 = Invisible，**背景纯黑** | 只含第 k 槽自身发光的画面 |
| **C1** | 同 C0，**背景纯白** | 用来解出每像素透光率 |
| **B** | 全场景正常，只有第 k 槽 = Invisible，背景 = 请求 `bg` | 没有第 k 槽的画面；`B ≠ bg` = 槽后面有东西 |
| **A** | 全场景正常，背景 = 请求 `bg` | 正常画面（同时就是环绕图） |

逐像素（只在掩码内、且 `t >= t_min` 的像素里统计）：

- 透光率 `t = clamp((C1 − C0) 的三通道平均, 0, 1)`。推导：alpha 混合下 `C0 = src·a`、`C1 = src·a + (1−a)`，
  所以 `C1 − C0 = 1 − a` = 透光率；`t≈0` 不透明、`t≈1` 全透。
- `behind`：`B` 与 `bg` 色差 > ε → 第 k 槽后面确实有东西；
- 期望颜色 `E = C0 + t·B`（线性混合模型）；
- `vanished`：`behind` 且 `|A − (C0 + t·bg)| < ε`（A 看起来就像后面是背景）且 `|A − E| > ε`（和正确混合明显不同）；
- `vanish_ratio = vanished / behind`；`behind < min_behind_px` 记 `null`；
- `model_error_p50 = median(|A − E|)`，在 `t >= t_min` 且不 vanished 的像素上取——用来看这个槽的着色器是否满足线性模型。

**为什么 t ≥ 0.15**：`t` 很小时着色器几乎不透明，`C0 + t·B` 与 `C0` 只差一点点，`|A − E|` 被量化噪声主导，
很容易在 ε=0.03 附近抖动；而且几乎不透明的槽本来就该挡住后面，「透过去看不见」没有讨论意义。
0.15 是「至少能透过去一成五」的经验下限，请求里可用 `t_min` 改。

**为什么用线性模型 E = C0 + t·B**：普通 alpha 混合（含 lilToon 透明模式）就是 `dst = src·rgb * a + dst·(1−a)`，
展开后正好是 `C0 + t·B`（`C0 = src·a`，`t = 1−a`），模型精确成立。会破坏这个式子的主要是
**Refraction / GrabPass 类**：第 k 槽要在着色时采样「屏幕后方」，而 C0/C1 两张图里它采样到的是黑/白背景、
和 A 里采样到的真实背景不同，于是 `E` 对不上 A，`model_error_p50` 明显升高（Screen/Multiply/自定义 Blend
一般也对不上）。纯加色（`Blend One One` 之类）解出来的 `t ≈ 1`，`E = C0 + B` 恰好等于 `A`，既不误报也不会
被判 vanished（它是「叠加上去」而不是「把后面顶掉」）。

**怎么看 model_error_p50**：
- 低（< ~0.02）且 `vanish_ratio` 高 → 线性模型成立，后面的东西确实没了，可信；
- 高（> ~0.05）→ 该槽的着色器不是普通 alpha 混合（Refraction/GrabPass/自定义 Blend），vanished 判定不可信，必须先看 A/B/C0/C1；
- `null` → 这个槽在所有视角都没达到 `t >= t_min` 或没有 `behind` 像素，等于没测到。

**vanished_owners 怎么来的、能信到什么程度**：对 flagged 的记录，把除 R 外的每个「当前 enabled 且在
`culling_mask` 内」的渲染器临时换成唯一颜色的 FlatColor，R 关掉，在 B 条件下渲一张 ID 图（独立
`RenderTextureReadWrite.Linear` + `Material.SetVector` 写色，绕开 Gamma/Linear 色彩空间转换），
再在 vanished 像素上解码统计，返回前 3 名。它回答「消失的是谁」（P3 里应是 `Hair_GoldenHour` 的合并网格）；
解码不出来（背景 / 被 R 自己别的槽挡住）的像素不计入分母。抗锯齿边缘混色的像素按最近邻归类，
占比是近似值，只用来找嫌疑人，不参与阈值判定。

**残余局限（第二版仍有，但不再是系统性误报）**：掩码 M 是「第 k 槽的几何轮廓」，不考虑 R 自己别的槽的自遮挡。
若第 k 槽是一块透明几何、而 R 的不透明槽在它前面盖住同一片像素，A 就等于前面那块不透明槽；在特定配色下
`|A − (C0 + t·bg)|` 仍可能 < ε 而误判。这与第一版「整个渲染器都被算成消失」的系统性误报不同（那种一整条到 0.97），
只会在同渲染器前后重叠槽的少数像素上出现；遇到时看 A/B/C0/C1 四张图和 `vanished_owners`（多半解码不出、
落在「不计入分母」里）即可分辨。

---
