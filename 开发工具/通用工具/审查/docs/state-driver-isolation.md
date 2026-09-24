# T1 · 回调隔离、头像解析、GestureManager 接管 <!-- nav -->

> 旧称：T1 `AuditStateDriver` / T3 `AuditTurntable` 等（原 `审查/README.md`） §3.0.2 /「头像解析规则」/「GestureManager 接管」/ §3.1。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[T1 · 每个状态做什么、健全性检查、易变形态键](state-driver-steps.md) · 下一页：[T1 · reset 模式与切换残留测试](state-driver-reset.md) <!-- nav -->

### 3.0.2 工程侧编辑器回调隔离（`isolated_callbacks.json`，任务 G，T1/T2/T3 通用）

请求开始处（`AuditRunner.Begin` 调 `AuditCallbackIsolation.Install`）用反射做三件事：

1. 读 `EditorApplication.update` 的调用列表；
2. 读 `EditorApplication.playModeStateChanged` 的调用列表（该事件真正的存储在静态字段
   `m_PlayModeStateChangedEvent` → `EventWithPerformanceTracker<T>` → `DelegateWithHandle<T>` → `Entry.Reference` 里；
   本工具只把它读出来，摘除走官方 `remove_playModeStateChanged` 访问器，不改内部结构）；
3. 对已知的 `AvatarGen.RuntimeProbe`：若存在静态字段 `_armed` 就置 `false`。

凡是方法所在程序集名以 **`Assembly-CSharp`** 开头、且声明类型不在 **`AvatarAudit`** 命名空间的回调，全部摘掉
（本工具自己的类型在 `AvatarAudit` 命名空间，双重排除；T-09 后它在 `AvatarAudit.Editor` 程序集，
程序集名本来也不以 `Assembly-CSharp` 开头），写进输出目录的
`isolated_callbacks.json`（`isolated_callbacks` 为 `类名.方法名` 列表）。

**时序（关键）**：摘除**不在 Play 模式的 Cleanup 时挂回**。因为这些回调里的老探针正是在 `ExitingPlayMode` /
`EnteredEditMode` 时写 `Assets/` 下的文件；Cleanup 通常还在 Play 里，挂回后退出 Play 照样触发。
所以：`Install` 时另外订阅一次 `playModeStateChanged` → 收到 **`EnteredEditMode`** 时把摘掉的回调按原顺序挂回、
写回 `isolated_callbacks.json` 的 `restored_at`、并退订自己；为避免在事件分发过程中改订阅表，实际挂回排在
`EditorApplication.delayCall`。例外：若请求本来就在编辑模式跑（T3 允许），Cleanup 时 `EditorApplication.isPlaying=false`，
不存在「下一次退出 Play」，`AuditRunner.Stop()` 会调 `AuditCallbackIsolation.Cleanup()` 立即恢复。

副作用：本轮 Play 期间这些老探针完全不跑（它们想写的文件不会产生）；退出 Play 回到编辑模式后恢复。
若编辑器在 Play 里被强杀，则不恢复（进程都没了，`ProjectSettings` 里的临时改动也可能留成脏值）。

**与域重载（Reload Domain，默认开）的关系**：退出 Play 会触发域重载，本类在 Play 里注册的静态订阅会随之丢失，
于是「收到 EnteredEditMode 再挂回」这条路在默认设置下可能来不及执行（`isolated_callbacks.json.restored_at`
可能停在 `null`）。这不影响本轮的正确性：**保证（本轮退出 Play 不写文件）来自 `ExitingPlayMode` 之前处理器已被摘掉**
——该事件在 Play 域内、域重载之前派发（否则在 Play 里注册的回调永远不会被调用）；重载之后，老探针自己的
`[InitializeOnLoad]` 静态构造会重新订阅（RuntimeProbe 的 `_armed`、EarPlayProbe 的 `_sb` 也随重载归零），
等价于恢复。若工程关掉了 Reload Domain，则没有重载，本类的 `OnPlayModeChanged` 会正常收到 `EnteredEditMode` 并显式挂回。

### 头像解析规则（判据）

面捕安装器会把头像克隆成第二个根，所以：

- 只认名字精确相等的**场景**对象（排除预制体资产、排除不在场景里的）；
- 候选先去重（某个候选是另一个候选的子孙就丢掉）；
- 只接受 `activeInHierarchy` 的候选；
- 恰好 1 个 → 用它；0 个 → 报错并列出全部同名对象路径；≥2 个都活跃 → **报错**并列出路径，
  让人自己去关掉一个，工具不猜。

### GestureManager 接管

- 优先复用 `GestureManager.ControlledAvatars` 里已有的模块；
- 没有就反射调 `ModuleHelper.GetModuleFor(VRC_AvatarDescriptor)` + `GestureManager.SetModule(module)`
  —— 这正是 GM 自己「在 Play 模式下打开 GestureManager Inspector」时走的内部路径
  （`Scripts/Editor/GestureManagerEditor.cs:81 TryInitialize` → `:97 Manager.SetModule(module)`），
  自动化下没人开 Inspector，所以我们替它走一遍。
- 接管成功 → 输出 `gm_controlled: true` / `driver: "gesture_manager"`；
  失败 → `driver: "animator"`，并在 `warnings` 里写明「ParameterDriver / LayerControl 不会被模拟，结论必须降级」。
- 顺手把 GM 的 `ModuleSettings.simulateCulling` 临时关掉（默认 prefab 里是 0，即关；一旦为开，
  GM 会按编辑器相机到头像的距离把全部 `renderer.enabled` 置 false，快照会全变成「不可见」），结束恢复。

### 3.1 场景里没有 GestureManager 时临时建一个（任务 F，`gm_created_by_audit`）

实测多数客户场景里根本没有 GestureManager 组件（如
`工程A/Assets/_Work/工程A.unity` 组件数 = 0），这时 T1 会退回
`driver=animator`，ParameterDriver / LayerControl 不被模拟。为此 T1 在 **Play 模式**下会自动补一个临时 GM：

- **触发**：`ensure_gm=true`（默认）+ 场景里 `FindManager()` 找不到组件 + `Application.isPlaying`。
  **编辑模式不建**，保持原来的退路（编辑模式本来也跑不了 T1）。
- **建法照 GM 自己的兜底路径**：`new GameObject("GestureManager").AddComponent<GestureManager>()`
  （出处 `Scripts/Editor/GestureManagerEditor.cs:63-68 CreateAndPing`）。GM 菜单项
  `Tools/Gesture Manager Emulator`（`:43-49 AddNewEmulator`）平时走的是
  `PrefabUtility.InstantiatePrefab(GestureManager.prefab)`（`:51-55`）；该 prefab 只含一个名为
  `GestureManager` 的 GameObject + GestureManager 组件（脚本 GUID `2398979b1d0d84349abc5ee9f0571350`，
  即 `Scripts/Runtime/GestureManager.cs.meta`），组件上把 `settings` 各字段序列化好
  （prefab 内 `cullingDistance: 5`、`initialPose: 0`、`simulateCulling: 0` 等），没有别的组件/字段。
  本工具照兜底路径建，但改名 `__AvatarAudit_GM`、`hideFlags = HideFlags.DontSave`，不污染场景/存档。
- **为什么挂上就能 `SetModule`（不需要等 Awake/OnEnable/Start/协程）**：
  `Scripts/Runtime/GestureManager.cs` 全文没有 `Awake`/`OnEnable`/`Start`，唯一生命周期钩子是
  `OnDisable`（`:23`）；`AddComponent` 返回时组件已 enabled、物体已 active。真正的初始化发生在
  `SetModule`（`:67`）→ `ModuleBase.Connect`（`Scripts/Runtime/Data/ModuleBase.cs:148-154`，把模块登记进
  `ControlledAvatars` 并调 `InitForAvatar`）→ `ModuleVrc3.InitForAvatar`
  （`Scripts/Editor/Modules/Vrc3/ModuleVrc3.cs:181-311`），全部同步完成（末尾 `_playableGraph.Play()` /
  `Evaluate(0f)`），不依赖帧。`settings` 是 prefab 序列化字段，运行时 new 出来是 null，
  由 `AuditIO.EnsureSettings` 补一个默认 `ModuleSettings` 实例兜底。
- **输出**：`states.json` 多一个布尔字段 `gm_created_by_audit`；`gm_note` 同时以
  `gm_created_by_audit=true；` 开头。字段为 `false` 表示用的是场景里原有的 GM（或没接管成功）。
- **清理**：T1 `Cleanup()` 调 `GmgBridge.DestroyAuditManager()`，**仅当 `_auditCreatedGo` 是我们建的**
  （幂等）；场景里原有的 GM 组件不碰。副作用：临时 GM 不会留给同一 Play 会话里后跑的 T3 复用——
  这是任务 F 的明确要求；T3 在没有 GM 的场景本来也无 GM 可用（它只 `GetControlledModule`，不主动建）。
