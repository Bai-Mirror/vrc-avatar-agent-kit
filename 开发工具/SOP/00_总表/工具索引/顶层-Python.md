> ← [工具索引](../工具索引.md) <!-- tools_index.py 自动生成：整页覆盖，勿手改 -->

# 工具索引 · 顶层-Python（26 个文件）

由 `python3 开发工具/通用工具/tools_index.py --write` 从各脚本文件头的「用途 / 可复用性」生成，整页覆盖；要改内容请改脚本文件头。路径相对 `开发工具/`。

### 通用工具（顶层）

| 路径 | 用途 | 可复用性 |
|---|---|---|
| `通用工具/agy_panel.py` | 反向评审。两档用法 —— | ★★★ 换个单子直接能用 |
| `通用工具/bl_keydump.py` | dump 一个 .blend 的全部形态键真名表（键名 + 默认值 + 滑块范围 + 受影响顶点数），厂商不公开键名的素体开工前跑一遍。 | ★★★ 换个单子直接能用 |
| `通用工具/bl_keymeasure.py` | 打开 .blend 对指定形态键输出位移量级、平均方向与受影响区域质心。 | ★★★ 换个单子直接能用 |
| `通用工具/bl_keyprobe.py` | Blender headless 直接读形态键的顶点位移，判定每条键的真实作用方向，不渲图、不喂模型。 | ★★★ 换个单子直接能用 |
| `通用工具/bl_tilt.py` | 精确测「眼尾相对眼头是抬还是垂」：先按 x 分左右眼，再比每只眼最外 10% 与最内 10% 簇的 Δz。 | ★★ 眼周高度带阈值需按素体调 |
| `通用工具/check_links.py` | 核对一棵 markdown 目录（默认 开发工具/SOP）里所有相对 .md 链接的目标文件是否存在。 | ★★★ 换个单子直接能用 |
| `通用工具/cjk_font.py` | 标注图里写中文用的字体加载器，避开 ImageFont.load_default() 无 CJK 字形出方框。 | ★★★ 换个单子直接能用 |
| `通用工具/comfy_redraw.py` | 把定妆照送进本机 ComfyUI 做二次创作改绘（img2img + ControlNet lineart） | ★★★ 换个单子直接能用 |
| `通用工具/distill_collect.py` | 两层制的「收尾蒸馏」输入收集器：把某时间点之后的「待蒸馏」标签（各施工记录）、DSH 回复里的「应写进 SOP 的教训」段（流水账）、 | ★★★ 换个单子直接能用 |
| `通用工具/ds_vision.py` | DeepSeek 视觉模型客户端，给 agy_panel 当第四个评审模型用 | ★★★ 换个单子直接能用 |
| `通用工具/dsh_balance.py` | 只读查询 DSH 实际凭据的余额；不显示密钥、不消费模型额度。 | （未标） |
| `通用工具/dump_vrc_menu.py` | 不开 Unity，直接从 .asset YAML 还原 VRCExpressionsMenu 树 + VRCExpressionParameters | ★★★ 换个单子直接能用 |
| `通用工具/eye_composite.py` | 眼睛贴图离线合成：把眼色层 alpha-over 到素体底图上产出完整 _MainTex，异色瞳按 UV 岛切分。 | ★★ 换了素材包要改输入目录 |
| `通用工具/guid_uniqueness_audit.py` | 全工程 GUID 唯一性审计。**一个 GUID 只允许对应一个路径** —— | ★★★ 换个单子直接能用 |
| `通用工具/img_tools.py` | 图像小工具合集（子命令）：sheet 联系表 / sheet-by-tag 按标签挑图拼表 / diff-crop 差异热区裁图 / overlay 叠加层 alpha-over 合成 / autocrop 按像素裁紧 | ★★★ 换个单子直接能用 |
| `通用工具/lens_readability.py` | 度量「流星/眼球特效读不读得出来」：按视距出背景校正后的能量与 ΔE 诊断，给出可复现判据。 | ★★★ 换个单子直接能用 |
| `通用工具/log_step.py` | 给工程/长程任务追加一条施工记录（时间戳只从系统时钟取）、维护文件顶部的「状态头」、可选一步提交；写后回读，回读不一致就不提交。 | ★★★ 换个单子直接能用 |
| `通用工具/pack_usage.py` | 按 GUID 出素材应用表：素材包里每一项导进来没有、用上没有、完整性如何。 | ★★★ 换个单子直接能用 |
| `通用工具/project_fingerprint.py` | **不开 Unity、不装第三方包**，纯文件解析 Unity 工程（Assets + Packages 的 YAML 与 .meta）， | ★★★ 换个单子直接能用 |
| `通用工具/shapekey_audit.py` | 捏脸烘焙后的全量形态键影响检查：动画峰值加烘焙量 > 100 即判双重应用破形。 | ★★★ 换个单子直接能用 |
| `通用工具/tex_tier_apply.py` | 把 `tex_tier_plan.py` 出的分档方案**应用到 .meta**，并同时写一份可精确回滚的记录。 | ★★★ 换个单子直接能用 |
| `通用工具/tex_tier_plan.py` | **不开 Unity** 算出贴图分档方案 —— 场景 → 材质 → 贴图 → .meta 导入设置，全链路纯文本。 | ★★★ 换个单子直接能用 |
| `通用工具/tools_index.py` | 扫描 `开发工具/通用工具/` 下的脚本，把文件头五字段里的「用途 / 可复用性」抽成按目录分组的 markdown 表，分页写进 `开发工具/SOP/00_总表/工具索引/`、导航写进 `工具索引.md` 的自动段；`--check` 列出缺「用途」的文件。 | ★★★ 换个单子直接能用 |
| `通用工具/unpack_unitypackage.py` | 把素材包（zip → .unitypackage）解进 Unity 工程的 Assets/，不经 Unity、不改 GUID | ★★★ 换个单子直接能用 |
| `通用工具/vpm_baseline_check.py` | 比对「工程 locked 段的版本」与「VCC 缓存里可得的最新稳定版」， | ★★★ 换个单子直接能用 |
| `通用工具/ws_git.py` | 工作区 git 的唯一提交入口（强制准则 6：每步写施工记录并提交）。 | ★★★ 换个单子直接能用 |
