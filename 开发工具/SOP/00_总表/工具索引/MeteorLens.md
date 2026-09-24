> ← [工具索引](../工具索引.md) <!-- tools_index.py 自动生成：整页覆盖，勿手改 -->

# 工具索引 · MeteorLens（6 个文件）

由 `python3 开发工具/通用工具/tools_index.py --write` 从各脚本文件头的「用途 / 可复用性」生成，整页覆盖；要改内容请改脚本文件头。路径相对 `开发工具/`。

### 通用工具/MeteorLens/Editor

| 路径 | 用途 | 可复用性 |
|---|---|---|
| `通用工具/MeteorLens/Editor/MeteorLensErrors.cs` | NDMF 校验报错（中文标题 + 详情 + 怎么修），生成阶段失败一律走这里，不静默跳过。 | ★★ 改包名与菜单即可用 |
| `通用工具/MeteorLens/Editor/MeteorLensGenerator.cs` | 「眼内流星」壳网格生成算法（纯内存，不写 Assets/、不动场景）── 找眼盘岛、复制壳、投影 UV、写顶点色。 | ★★ 改包名与菜单即可用 |
| `通用工具/MeteorLens/Editor/MeteorLensPlugin.cs` | NDMF 插件：Transforming 阶段在 Modular Avatar 之后把镜片壳生成到构建克隆里，非破坏式。 | ★★ 改包名与菜单即可用 |
| `通用工具/MeteorLens/Editor/MeteorLensPreview.cs` | 编辑器菜单：在选中头像上跑一遍生成算法，把壳作为「不保存」的临时物体显示出来供人眼看位置/大小。 | ★★ 改包名与菜单即可用 |

### 通用工具/MeteorLens/Runtime

| 路径 | 用途 | 可复用性 |
|---|---|---|
| `通用工具/MeteorLens/Runtime/MeteorLensInstaller.cs` | 「眼内流星」挂载组件：放在头像根，NDMF 构建期读取它生成镜片后删掉自己（IEditorOnly）。 | ★★ 改包名与菜单即可用 |
| `通用工具/MeteorLens/Runtime/MeteorLensRigidSync.cs` | Rigid 模式运行时形态键同步：LateUpdate 逐帧把 Body 同名形态键权重拷到独立镜片 SkinnedMeshRenderer。 | ★★ 改包名与菜单即可用 |
