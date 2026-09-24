# 缺陷回放库 `replay/`（开工清单 T-15；C-06 扩充）

把已修的真实缺陷按文件反向打回工作区，外加一条注入样本，供 **T-16 一次 Play
（E2/E3/E4/E12）**、**E11 盲起草**、**E6 几何正样本** 与 **工具改版回归（03 §4.4 ⑦）**
使用。判据与真值定义见 `_长程任务_20260918/感知机制研究/03_研究与方案.md` §4.5 / §4.6
与 04 的 T-15 一节；扩充条目见作业清单 C-06。

## 九条 case

第一批 4 条（工程A，修复提交 `ceb4070b`）：

| case | 类型 | dep_id | 缺陷一句话 | 关键指标（修前 → 修后） |
|---|---|---|---|---|
| `grab_headdress` | git 补丁 | `工程A.grab.headdress_color_chain`（U4） | 头饰换色动画引用厂商原件（队列 2450），抓取点回落 | 抓取点 2450 → 3050；抓屏链 hits 24 → 0 |
| `coat_double` | git 补丁 | `kaguya.outer_variant_by_bust`（D5/U2） | 备选外套 `outer_breast_big_open` 与 `outer` 同时激活 | 重合比例 70% → 0（构建产物里无 big_open） |
| `mmn_foot` | git 补丁 | `MMN.foot_flat`（D3/U1） | 鞋在袜关时无人写平脚键，脚趾穿出包趾鞋头 | 脚趾穿出 63/170 → 0；`Foot_heel_OFF` 0 → 100 |
| `inject_parker` | 注入脚本 | `RePoppin.shirt_under_parker`（D4a/U3） | 删 `PART_SHAPES` 的 RePoppin 行，`Parker_on` 无写者 | `Parker_on` 期望 100，注入后基线 0 |

第二批 5 条（本轮手工修掉的缺陷，errors.md E1/B1/B2+B3/R1/Z1–Z3）：

| case | 类型 | dep_id | 缺陷一句话 | 关键指标（修前 → 修后） |
|---|---|---|---|---|
| `e1_bust_sync` | git 补丁 | `RePoppin.bust_shape_sync`（D5） | 工程E Re-Poppin 五件胸型键无人同步，胸型拉满双乳穿出 | 件上键恒 0 → 与身体逐值相同；正面肤色像素 6,822 → 837 |
| `b1_rurune_flatfoot` | git 补丁 | `工程D.rurune_black_foot_flat`（D3） | 工程D Rurune-Black 厚底鞋没挂平脚键 | `Foot_heel_OFF` 缺席(=0) → 100（穿鞋）/0（脱鞋） |
| `b23_esmera_nipple` | git 补丁 | `工程D.esmera_nipple_bust_sync`（D5） | 工程D Esmera 乳贴缺 `Breast_small` / `Breast_big(limit)` 且无人同步 | 间隙 p50 5.74 / 14.95 mm → 1.28 / 1.66 mm |
| `r1_lopear_shrink` | git 补丁 | `工程B.lopear_shrink_owner`（D4a） | 工程B垂耳兔 11 个收缩键挂整套，脱件后身体缺失 | 11 键恒 100 → 跟随覆盖件显隐 |
| `z_outfit_menu` | git 补丁 | `工程F.outfit_menu_visibility`（菜单/显隐） | 工程F失效 Outfit 子菜单 + Shellmarin 三件同开关 + 眼镜语义反 | 9 开关零效果 → 子菜单删；三件独立；default 隐藏/0 显示/1 隐藏 |

每条 case 目录里有：`patch.diff`（git 补丁）或 `inject.py`（注入脚本）、`expect.json`
（dep_id / 状态集 / 责任写者 / 指标区间 / 正反对照 / 证据）、`README.md`（本 case 说明）。

`b23_esmera_nipple` 合并 errors.md 的 B2 与 B3（同一 asset 与场景，拆开会互相覆盖）；
`z_outfit_menu` 合并 Z1–Z3（同一次修复提交）。`e1_bust_sync` 与 工程A 无关，
是 工程E 工程的第一条回放用例。

## 用法

```bash
R=开发工具/通用工具/审查/replay
python3 $R/replay.py list                 # 列 9 条
python3 $R/replay.py status               # 9 条状态 + 清单核对（验收命令）
python3 $R/replay.py verify               # 干净树上验证补丁正/反向都能应用（临时改、结束还原）
python3 $R/replay.py apply  --all         # 打回全部（幂等）
python3 $R/replay.py revert --all         # git checkout HEAD -- <清单 19 文件>
python3 $R/replay.py apply  mmn_foot      # 单条
python3 $R/replay.py selftest             # 干净树 → apply --all → 核对/可复现（重定基条目走语义断言）→ revert
```

> **任务 BR 起：`apply` 前会先跑 `git status --porcelain`，非空就拒绝**（打印前 50 条）。
> 动机：apply/revert 会改各工程工作区，本来就有一堆未提交改动（别的会话、Unity 未存盘）时，
> 打完补丁再 `revert` 会连同它们一起 checkout 掉 / 上下文对不上。确认这些改动与本库清单无关后，
> 可显式 `python3 $R/replay.py apply --allow-dirty mmn_foot` 跳过检查（工具会打 WARNING）。
> `selftest` 走内部 apply，不受这条全局检查影响（它本来就只要求清单内干净）。

`status` 退出码：清单内工作区与「已应用 case 的文件并集」一致时为 0，否则 1。
它同时打印锁文件状态与**清单外**的 tracked 改动（不判失败，只提示）。

> `selftest` 会改各工程工作区。想完全不碰真工程，可建一个稀疏 worktree 再指
> `--root`：`git worktree add --no-checkout --detach /tmp/wt HEAD` + sparse-checkout
> 出清单文件，然后 `replay.py --root /tmp/wt selftest`（本次 C-06 自测就是这么跑的）。

## 锁与安全约定

`apply` / `revert` 会**临时修改清单里各工程的工作区**（工程A、工程E、工程D、
工程B、工程F）。按派工约定：

1. `apply` 之前先建锁文件
   `_长程任务_20260918/派工/tmp/T15_REPLAY_ACTIVE`（写入时间）；
2. `revert --all` 后确认 `git diff -- <本库清单>` 为空，再删锁文件；
3. **任何情况下结束前都必须 revert 干净**。

replay.py 只**检测并打印**锁，不强制（锁的持有者可能是 Unity 会话或别的 DSH 任务，
工具无法判定）；缺锁时打 `WARNING`。

`revert` 只 `git checkout HEAD -- <本库清单文件>`，**绝不回退工具文件**
（`Assets/Editor/AvatarAudit/*`、`开发工具/通用工具/审查/*.cs` 等）或清单外改动。
注意：`b1_rurune_flatfoot` 的修复提交同时改了 `ProjectSettings.asset`（Play 副作用），
按 SOP 不进清单，revert 不会碰它。

共用文件的叠加：`coat_double` 与 `inject_parker` 共用 `MenuGenA2.cs`；
`b1_rurune_flatfoot` 与 `b23_esmera_nipple` 共用 `工程D.unity`。它们在不同区域，
可以叠加；但**单条 revert 会把共用文件的另一条一并还原**（都回到 HEAD），
`revert --all` 是推荐用法。

## 清单（19 个文件，相对仓库根）

```
工程A/Assets/Editor/AvatarGen/MenuGenA2.cs                 (coat_double, inject_parker)
工程A/Assets/_Work/工程A.unity                     (mmn_foot)
工程A/Assets/_Work/Gen/Clip/Dial_头饰色.anim                (grab_headdress)
工程A/Assets/_Work/Gen/Clip/Dial_整套.anim                  (coat_double)
工程A/Assets/_Work/Gen/Clip/On_部位_外套.anim               (coat_double)
工程A/Assets/_Work/GrabQueue/glass_virgo_q3050.mat         (grab_headdress，apply 时被删)
工程A/Assets/_Work/GrabQueue/glass_virgo_q3050.mat.meta    (grab_headdress，apply 时被删)
工程E/Assets/工程E.unity                                          (e1_bust_sync)
工程D/Assets/工程D.unity                                          (b1_rurune_flatfoot, b23_esmera_nipple)
工程D/Assets/_Work.meta                                          (b23，apply 时被删)
工程D/Assets/_Work/Esmera_BreastSmall.meta                       (b23，apply 时被删)
工程D/Assets/_Work/Esmera_BreastSmall/Breast_Bandage_BreastSmall.asset      (b23，apply 时被删)
工程D/Assets/_Work/Esmera_BreastSmall/Breast_Bandage_BreastSmall.asset.meta (b23，apply 时被删)
工程B/Assets/_Work/工程B_Milfy.unity                          (r1_lopear_shrink)
工程F/Assets/Kipfel.unity                                        (z_outfit_menu)
工程F/Assets/_Work.meta                                          (z，apply 时被删)
工程F/Assets/_Work/Menu.meta                                     (z，apply 时被删)
工程F/Assets/_Work/Menu/Kipfel_ExMenu_FT_noOutfit.asset          (z，apply 时被删)
工程F/Assets/_Work/Menu/Kipfel_ExMenu_FT_noOutfit.asset.meta     (z，apply 时被删)
```

## 补丁怎么来的（可复现）

每条 `git_patch` case 的 `expect.json` 记 `fix_commit` / `pre_fix_rev`，补丁是**反向**
diff（把修好的树打回修前），用 `git diff <fix_commit> <pre_fix_rev> -- <case 的文件...>`
生成；`replay.py selftest` 会按这两个 commit 重算并与盘上补丁逐字比对：

```bash
git diff <fix_commit> <fix_commit>^ -- <case 的文件...>
```

* 第一批：`fix_commit = ceb4070b`。
  * `grab_headdress` / `coat_double`：整文件反向 diff，逐字保存。
  * `mmn_foot`：整文件反向 diff 后**只保留含 `232539723` 的两条 hunk**
    （新建组件 `&232539723` 与它在 PrefabInstance `m_AddedComponents` 里的登记），
    剔除 `RenderSettings.m_IndirectSpecularColor` 与 PhysBone `cachedExecutionGroupIndex`
    两条光照/序列化噪声 hunk。两条 hunk 都引用同一 fileID，缺一不可。
    case 里用 `patch_filter: "mmn_fileid"` 标出这条过滤。
  * `inject_parker`：无 commit，`inject.py` 删 `MenuGenA2.PART_SHAPES` 的
    `("A2_Coat", "in:Outfit_RePoppin/(A)Shirt", "Parker_on", 100f, 0f),` 一行（幂等）。
  * `git diff ceb4070b HEAD -- <第一批 7 文件>` 为空，所以反向补丁能干净应用、
    `revert` 用 `git checkout HEAD --` 即回到修后状态。
* 第二批：`fix_commit` 分别为 `2acdb32a`(e1) / `6d5eb1e7`(b1) / `da79abfc`(b23) /
  `67233c44`(r1) / `862686ad`(z)，整文件反向 diff（含新建文件/目录 `.meta` 的删除 hunk）。
  * `b23` 的 pre 侧取 `b34a6010^`（B2 与 B3 两次提交合并成一个用例）。
  * `b1`、`r1` 的文件在修复提交之后又被别的提交改过（b1 被 b23 的两次提交改、
    r1 被 `97ceccae` 改），补丁按修复提交生成，但在当前 HEAD 上
    `git apply --check` 通过（改动在不同区域），apply 只打回该缺陷的 hunk。
  * 新增文件（`glass_virgo_q3050.*`、`Breast_Bandage_BreastSmall.*`、
    `Kipfel_ExMenu_FT_noOutfit.*` 及目录 `.meta`）的反向 hunk 是**删除**；
    apply 会把它们删掉，revert 从 HEAD 取回。

### 对 HEAD 重定基（任务 CF，2026-09-19）

修复提交之后，`mmn_foot`、`b1_rurune_flatfoot`、`b23_esmera_nipple`、`z_outfit_menu`
四个场景文件又被生成器/后续修复改过（组件 fileID 重排、`m_AddedComponents` 里多了
别的条目、资源增删），逐字 `git diff <fix> <pre>` 的上下文对不上 HEAD，
`replay.py verify` 报「打补丁失败 …:<行号>」。

这四条 `expect.json` 现在带 `"regen": "head_rebase"`：

* `rebase` 记重定基的**原因 / 做法 / 生成时的 worktree HEAD**；`pre_fix_rev` 仍保留
  缺陷出处（修复提交的前一 rev），但**不再用于逐字重算补丁**。
* `patch.diff` 是在 HEAD 稀疏 worktree 上按**缺陷语义**重建缺陷态后 `git diff HEAD`
  得到的：删除该缺陷引入的组件/登记/新建资源，顺带剔除了光照、PhysBone、float
  精度这类序列化噪声 hunk（不影响缺陷语义）。
* `defect_assert` 列出「打完补丁后必须缺/含的标记」（例如 mmn_foot 打完必须没有
  `Foot_heel_OFF`、b23 打完必须没有 `Esmera_BreastSmall` 资源）；`verify` 与
  `selftest` 用它替代「逐字可复现」检查，保证补丁确实回到缺陷态。
* 需要重建时：`git worktree add --no-checkout --detach <wt> HEAD` + sparse-checkout
  出本库清单，按 `rebase.how` 改文件，`git diff HEAD` 覆盖 `patch.diff`。
  失败 hunk 可用 `git apply --reject <旧补丁>` 落在 HEAD 上，再手工补 `.rej`。


## 回归用法（03 §4.4 ⑦）

工具（几何 / 抓屏 / 校验器 / 生成器）改版后：

```bash
python3 $R/replay.py verify                       # 补丁本身没坏
python3 $R/replay.py apply --all                  # 打回缺陷
#   → 重跑生成器 + 一次 Play 采集（T-16 步骤①–③）
python3 $R/replay.py revert --all                 # 还原
#   → 修后同批再采一次（T-16 步骤⑤）
```

任一 case 在新工具下不再报违例 = 工具回归，记入施工记录。
