> ← [04 · 施工记录与版本管理](../04_施工记录与版本管理.md)

# ProjectSettings 副作用（从 04 主页下沉，2026-09-23）

### 图形 API 与 lilToonSetting.json（触发：`git status` 冒出 `ProjectSettings/` 的改动时）

- **`ProjectSettings/lilToonSetting.json` 随图形 API 改写是设计行为，不是损坏。** 只要 `CurrentRP.txt` 记的 API 与当前不一致，lilToon 启动钩子就会重写 json 并按头像材质重编译 `.shader`；实测 OpenGL→Vulkan 那 30 个 `LIL_FEATURE_*` 由 false→true，全是「没有材质引用」的贴图功能开关，**不进上传包**（上传走 `IVRCSDKBuildRequestedCallback`，按实际材质重算）。依据 `派工/B_结论.md`。
  - **取舍**：这一条只用来解释 diff，不拿来当「配置错了」修。**代价不对称在 API 混用那一侧**：一次 API 切换 = 整套 lilToon shader 重导入（几十秒级）+ 审查口径不统一 —— 所以全程只用一个图形 API；以「与 VRChat 上线端更接近」为准选 Vulkan，纯看配色/静态效果 OpenGL 也行，但**不要两种混着比对**。
- **Play 会改工程设置，提交前先看 `git diff ProjectSettings/`**：AAO/SDK 进 Play 把 `legacyClampBlendShapeWeights` 置 1（Play 口径，与客户端一致），正常退出置回 0 —— 这些是副作用不是改动，会话结束后 `git checkout <基线提交> -- <工程>/ProjectSettings/ProjectSettings.asset` 还原（详见 [B850_Linux环境](../02_环境准备与人工介入/B850_Linux环境.md)）。
  - **推断，待证伪（E-未核-08）**：若编辑器在 Play 中被强杀（`EnteredEditMode` 没跑到），`legacyClamp` 可能把 `1` **留在盘上**。**没证实之前只当运行假设用**：下次进 Play 前先 `grep -n legacyClampBlendShapeWeights` 读一遍 `ProjectSettings.asset`，见到 1 就还原；不要据此断言「外推一定被钳」。
  - **触发时刻**：动 7z / 归档之前。**修完依赖要重打 7z** —— 09-01 修了 7 个工程的历史 `file:`/`git#master` 依赖，但服务器上的 `个人存档/*.7z` 一直没重打（G 指出，待办 E-存档-02）
