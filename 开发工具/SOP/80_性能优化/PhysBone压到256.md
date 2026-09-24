> ← [80 · 性能优化](../80_性能优化.md) · [00 · 总表](../00_总表.md)

# 把 PhysBone 压进 VRChat 的 256 硬上限（2026-09-21 工程B实战）

> 触发：SDK 面板报 `Phys Bone Components: N - Avatar exceeds the maximum limit (256)`。
> 这条**不是评级差**，是 `AvatarValidation.cs:127 MAX_AVD_PHYSBONES_PER_AVATAR = 256`，
> 构建期会对**处理后**的头像再校验一次并 `throw ValidationException`，上传拿不到 bundle。
> 同处还有：碰撞体 256（`:128`）、Contact 256（`:131`）、Constraint 2000（`:132`）、Raycast 80（`:126`）。

## 1 · 空的 AAO MergePhysBone 不是「白挂」，是「挂了就构建不过」

`MergePhysBoneProcessor.cs:52-53` 里 `componentsSet` 为空直接 `return`，但 **AAO 的 Validation 阶段会为它报
`MergePhysBone:error:noSources`**，NDMF 预处理返回 false，整条链断掉。

实测：某工具批量挂了 10 个 MergePhysBone 却没填 `componentsSet`，表现是
`VRCBuildPipelineCallbacks.OnPreprocessAvatar` 返回 false、**日志里没有任何异常文本**，查了很久。

- **可查问句**：预处理莫名返回 false 时，先数一遍 `componentsSet.mainSet.arraySize == 0` 的 MergePhysBone。
- **取舍**：要么填上源列表，要么删掉。别留空的。

## 2 · AAO MergePhysBone 减不了**面板**上的数

面板统计跑在**构建前**的场景对象上（实测面板显示 520，构建后是 497）。AAO 是构建期合并，
面板数字不会变。要让面板那条 Error 消失，只能在**场景里**真删/真合。

## 3 · 场景内合并的正确姿势（照抄 AAO 的语义，但不动层级）

合并语义（`MergePhysBoneProcessor.cs:143-176`）：留下的组件挂在**父物体**上，
`rootTransform = 父`、`multiChildType = Ignore`、`ignoreTransforms` 与 `colliders` 取并集。

### ⚠ 最容易漏、漏了就毁头像的一步

`rootTransform=父 + multiChildType=Ignore` 会把父物体下**所有**子链变成物理链，**包括原本没有 PhysBone 的**。
2026-09-21 实测漏了这步的后果：`Armature/Hips` 上的组件覆盖了 `Spine` 和 `Upper_leg.L/R`、
`Head` 上的覆盖了 `LeftEye`、`Chest` 上的覆盖了 `Neck`/`Shoulder` —— 整副骨架变软。

AAO 的做法是把源链**重新挂到一个新建空物体**下来隔离（`:56-100`；只有「父物体的子物体恰好全是源链」
且父物体没被动画写时才直接复用父物体）。

**更省事也更安全的等价做法**：把父物体下**不属于本组源链**的子物体全部加进 `ignoreTransforms`。
效果一样，而且**不动层级、不打断按路径引用骨骼的动画**。

### 硬自检（不用人看）

合完立刻算：这个组件实际覆盖的一级子链数（父物体的 childCount 减去落在 `ignoreTransforms` 里的），
**必须等于源链数**。对不上就抛异常中止，别往下做。

再补一条整机判据：遍历所有 PhysBone，检查
`Spine / Neck / Shoulder.L,R / Upper_leg.L,R / Hips / Chest / Head / LeftEye / RightEye / Hand.L,R`
这些骨头有没有出现在任何组件的「覆盖子链」里，**必须是 0**。

## 4 · 哪些组不能合

| 情况 | 为什么 |
|---|---|
| 组里任一成员被动画写（`m_Enabled` / `VRCPhysBone` 类型的曲线） | 合完那条曲线就指不到东西了 |
| 组内有 ≥2 个不同的非空 `parameter` | 合并只能留一个，另一个的 grab/stretch 参数会失效 |
| `allowGrabbing` / `allowPosing` 不一致 | 合了会让本来不能抓的变成能抓（或反之）。要合就明确对齐到组内多数派，并写进记录 |

## 5 · 白捡的那几个：纯空转的 PhysBone

「`rootTransform`（为空时取组件自身）名下没有任何子 transform，且 `endpointPosition` 是 0」的组件
**什么都不模拟**，删掉零损失。工程B两个根各有 5 个（厂商件里的 `TwistCancel/*Sode_*`、`DrawersFrillRoot1`）。
> 注意区分：根下没有子骨但**设了** `endpointPosition` 的，会有一个虚拟端点，**别当空转删**（工程B各有 15 个）。

## 6 · 实战数字（工程B，两个根完全一致）

| 步骤 | 组件数 |
|---|---:|
| 起点 | 520 |
| 删纯空转 5 个 | 515 |
| 一轮：同父合并 69 组（设置对齐到多数派） | 257 |
| 二轮：只动 `_Hair`，每个发型的各部分合成一条（4 组） | **236** |

**光靠「同父合并」到不了 256**：纯数学上限是 259（同父全合、设置强行对齐），还超 3。
必须叠加「删纯空转」或「跨一层再合」。做测算时先把这三档算出来再谈方案：
① 同父 + 设置完全相同才合（零手感变化）② 同父就合、设置强行对齐 ③ 再往上一层合。

## 7 · 副作用：cyclic dependency Warning

合并后可能新出现
`This avatar contains VRCPhysBone or VRCPhysBoneCollider components which have cyclic dependencies`。
SDK 原文说后果是「某个碰撞体晚一帧运行」，且「如果是有意的可以忽略」，**是 Warning 不是 Error，不拦上传**。
先按「碰撞体长在自己链上」剔自环；剔不掉说明是两个组件互相引用形成的环，记成已知项即可。

## 8 · 怎么不靠人看面板就知道还剩几条 Error

反射拿到开着的 `VRCSdkControlPanel` 实例 → `ResetIssues()` → 调 `VRCSdkControlPanelAvatarBuilder.OnGUIAvatarCheck(descriptor)`
→ 读 `GUIErrors` / `GUIWarnings` 两个字段（`Issue.issueText`）。
逐根跑，比让用户滚动截图靠谱得多，也能在改完之后立刻复验。
