# 探针 shrink_cover · 判据改版记录（CU / CX / CT） <!-- nav -->

> 旧称：T1 `AuditStateDriver` / T3 `AuditTurntable` 等（原 `审查/README.md`） §3.2.8 中段。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[探针 shrink_cover（收缩键遮挡一致性）· 请求与参数](probe-shrink-cover.md) · 下一页：[探针 shrink_cover · 输出、诊断、自检与标定](probe-shrink-cover-output.md) <!-- nav -->

> **任务 CU 改判据（旧距离口径已证伪）**：`seq_t33_calib`（工程B 43%）用正负样本扫 `cover_dist_mm`
> 3/10/25/40 mm：3 mm 抓到正样本（关袜 + 强开 `Ankle`）但把负样本 `Shoulder` 误报，10/25/40 mm 又漏掉裸脚踝。
> 根因是距离回答「**附近**有没有布」而不是「我**外面**有没有布」——宽松外套离皮肤 1–3 cm，光脚踝**旁边**就是鞋帮。
> 现在默认 `cover_rule=outward_ray`：每影响顶点取身体外向伪法线 n（`PokeAngleWeightedPseudo` 角度加权、BakeMesh
> 法线翻正符号，与 poke 外壳共用同一份），从 `v + n*origin_mm` 沿 n 发 1 条 + ±`cone_deg` 的 4 条锥向射线，
> 长度 `cover_ray_mm`，打到任一可见服装三角形即算遮住，按 `ray_vote` 归票。旧距离读数保留成参考列
> `nearest_cover_dist_mm` / `covered_near_ratio`（后者=受影响顶点里最近距离 ≤ `cover_dist_mm` 的占比，不含壳内），
> **默认不参与 verdict**。

> **任务 CX / B-T33b 改 verdict 形状（「与」→「或」）**：`seq_t33_calib2` 的正样本（关袜子 + 强开 `Ankle`）
> 里，该键的影响顶点**大部分本来就在鞋腔里**（外向射线 30–80 mm 打到鞋面，属合法遮挡），真正裸露在鞋口以上的
> 只有 **21/221 = 9.5%**，过不了 `ratio_thr=0.60`；但它们的绝对面积是 **6.86 cm²**，远超面积门。于是三个
> `cover_ray_mm`（30/50/80）下正样本**全部漏掉**。根因：一个形态键的影响区天然**跨越遮挡区与裸露区**，比例会被
> 「合法被遮住的那部分」稀释，而人眼看见的是**绝对裸露面积**。故 `verdict_rule` 默认改成 `"or"`；`"and"` 一键取回旧行为。
> 每行另给 `verdict_by`（`ratio`/`area`/`both`/`none`）与 `ratio_ok`/`area_ok`，如实报告是哪一边达标。

> **任务 CX：`area_thr` 初值 1.0 cm²（⚠ 待 B-T33b 用正负样本标定，不是已验证值）**。推导：10 mm × 10 mm
> 连续裸露皮肤（约一个指甲盖）是 0.5–1 m 观察距离下不看标签也一眼能认出的最小斑块；低于 ~0.2 cm²（5 mm 圆斑）时
> 容易被单顶点 / 网格接缝 / 射线噪点混同，故取 ~5 倍余量 = **1.0 cm²**。取舍：比旧 2.0 松一半，正样本 6.86 cm²
> 有 6.8× 余量；代价是会把 1–2 cm² 的边界暴露也报出来（偏保守）。**用 `seq_t33_calib2` 的 N（全穿）档看：30 mm
> 档 `Chest_2=71 cm²`、`Spine_2=95.9 cm²`，`"or"+1.0` 会把它们也判 uncovered（该档 8 个键会全 uncovered →
> `self_check` suspicious → 全 `undecidable`）；50/80 mm 档负数明显收敛但仍非全 ok。** 所以 **B-T33b 必须把
> `cover_ray_mm` 与 `area_thr` 一起扫**（正样本 `Ankle` 要 uncovered、负样本全 ok、30–80 mm 不翻转），不能只调
> `area_thr`。**预测的失败模式**：若某个正样本的裸露面积也 <1 cm²，或负样本在短射线档仍有 >1 cm² 的假裸露，
> 则该档的 `verdict` 会给出错误结论——此时按 `verdict_by` 看得出是 `area` 触发的，再决定放宽 `cover_ray_mm`
> 还是抬高 `area_thr`。

> **任务 CT 修（第一次实跑 100% 误报的根因）**：CS 默认串 `(?i)(…|ear|head|…)` 拿**整条路径 + 子串**匹配，
> 命中 `_Outfit/LopEarMine/…` 的 `ear`、`Underwear` 的 `ear`，把整套在穿的 LopEar 外套/袜子/鞋排掉；
> 身体自己（`Body`）又留在集合里，被测键却长在 `Body_base` 上 → 四状态每键 `uncovered_ratio=1`、
> `Ankle.nearest_cover_dist_mm≈799mm`（最近的"衣服"只剩胸罩）。现在：
> **①** 排除只看叶子名、整词匹配（`Ear`/`Hair_Front`/`Jacket_Ear` 仍排除；`LopEarMine`/`Shoes` 不排除）；
> **②** 身体家族（`body` 自己 + 同素体其它片：`Body`、`Body_b*`，按 `ShrinkCoverRules.IsBodyLike` 的
> 归一词根/同父前缀判）一律不进集合；**③** 名单与判定一起写进产出（`garments_considered`/`used`/`excluded`、
> `body_leaf`/`body_family_root`/`body_family_rule`）；**④** 加 `self_check`（见下）。
> 代价：词匹配是「整个 token 相等」，复合名如 `NaturalNail`/`Hairpin`/`Kumachan_HeadAcc` 不拆 CamelCase，
> 不再被默认词表排除（宁可少排也不误伤整套衣服）；要排它们就把词表写成能命中的词或用自定义正则。
