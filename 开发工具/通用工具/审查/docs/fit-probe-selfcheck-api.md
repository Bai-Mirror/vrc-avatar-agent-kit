# T2 贴合探针 · 自检 1：API 签名 <!-- nav -->

> 旧称：T2（原 `审查/README_T2.md`） §7。§ 编号沿用原文，跨页 § 引用按 [文档目录](../README.md#文档目录) 查。<!-- nav -->
> 上一页：[T2 贴合探针 · v3 覆盖范围、输出、性能](fit-probe-scope-output.md) · 下一页：[T2 贴合探针 · 自检 2/3：恢复对照、运行期自检 A/B](fit-probe-selfcheck.md) <!-- nav -->

## 7. 自检 1：用到的 Unity / AuditIO API 与其 Unity 2022.3 签名

> 带 ✅ 的签名已用官方 ScriptReference（2022.3 / 2023.2）核对过；其余按文档知识写，**Claude 编译时请一并核对**。

### 7.1 蒙皮 / 网格

| API | 2022.3 签名 | 备注 |
|---|---|---|
| `SkinnedMeshRenderer.BakeMesh` ✅ | `public void BakeMesh(Mesh mesh, bool useScale);`（另有 `BakeMesh(Mesh)`） | `useScale` 语义见第 4 节第 3 条 |
| `SkinnedMeshRenderer.bones` | `public Transform[] bones { get; set; }` | |
| `SkinnedMeshRenderer.sharedMesh` | `public Mesh sharedMesh { get; set; }` | |
| `SkinnedMeshRenderer.GetBlendShapeWeight` | `public float GetBlendShapeWeight(int index);` | |
| `SkinnedMeshRenderer.SetBlendShapeWeight` | `public void SetBlendShapeWeight(int index, float value);` | 允许 0–100 之外（外推） |
| `Mesh.vertices` / `normals` / `triangles` | `public Vector3[] vertices { get; set; }` / `Vector3[] normals` / `int[] triangles` | 非 Readable 网格会报错，已先查 `isReadable` |
| `Mesh.vertexCount` | `public int vertexCount { get; }` | |
| `Mesh.isReadable` | `public bool isReadable { get; }` | |
| `Mesh.indexFormat` | `public Rendering.IndexFormat indexFormat { get; set; }` | 大网格必须先设 `UInt32` 再写数据 |
| `Mesh.RecalculateBounds()` | `public void RecalculateBounds();` | |
| `Mesh.RecalculateNormals()` | `public void RecalculateNormals();` | 法线缺失时在副本上重算 |
| `Mesh.GetBonesPerVertex()` ✅ | `public Unity.Collections.NativeArray<byte> GetBonesPerVertex();` | 返回视图，不要 Dispose |
| `Mesh.GetAllBoneWeights()` ✅ | `public Unity.Collections.NativeArray<BoneWeight1> GetAllBoneWeights();` | 每顶点已按权重降序 |
| `Mesh.boneWeights` | `public BoneWeight[] boneWeights { get; set; }` | legacy 退路 |
| `Mesh.blendShapeCount` | `public int blendShapeCount { get; }` | |
| `Mesh.GetBlendShapeName` | `public string GetBlendShapeName(int shapeIndex);` | |
| `Mesh.GetBlendShapeIndex` | `public int GetBlendShapeIndex(string name);` | 找不到返回 -1 |
| `BoneWeight1.boneIndex` / `.weight` | `public int boneIndex; public float weight;` | |
| `BoneWeight.boneIndex0..3` / `weight0..3` | 公开字段 | legacy |
| `MeshFilter.sharedMesh` | `public Mesh sharedMesh { get; set; }` | |

### 7.2 物理 / 射线

| API | 2022.3 签名 | 备注 |
|---|---|---|
| `RaycastCommand` ctor ✅ | `public RaycastCommand(Vector3 from, Vector3 direction, QueryParameters queryParameters, float distance);` | 旧 `(from,dir,dist,layerMask,maxHits)` 在 2022.3 已标 Obsolete“no longer supported”，故用 QueryParameters 版 |
| `RaycastCommand.ScheduleBatch` ✅ | `public static JobHandle ScheduleBatch(NativeArray<RaycastCommand> commands, NativeArray<RaycastHit> results, int minCommandsPerJob, JobHandle dependsOn);` | 此重载 `maxHits` 默认 1，结果下标 = 命令下标 |
| `QueryParameters` ctor ✅ | `public QueryParameters(int layerMask, bool hitMultipleFaces, QueryTriggerInteraction hitTriggers, bool hitBackfaces);` | |
| `RaycastHit.collider` / `.normal` / `.distance` / `.triangleIndex` | 公开属性 | 未命中时 `collider == null` |
| `Physics.queriesHitBackfaces` ✅ | `public static bool queriesHitBackfaces { get; set; }` | 用完恢复原值 |
| `Physics.SyncTransforms()` | `public static void SyncTransforms();` | 临时碰撞体建/启后调用 |
| `Physics.Raycast` | `public static bool Raycast(Vector3 origin, Vector3 direction, out RaycastHit hitInfo, float maxDistance, int layerMask, QueryTriggerInteraction queryTriggerInteraction);`（另有不带 out 的重载） | 非 Play 退路 |
| `Physics.RaycastNonAlloc` | `public static int RaycastNonAlloc(Vector3 origin, Vector3 direction, RaycastHit[] results, float maxDistance, int layerMask, QueryTriggerInteraction queryTriggerInteraction);` | **v3** 脚底厚度：一次取回该射线全部命中（数组需预分配） |
| `MeshCollider.sharedMesh` / `.convex` / `.enabled` | `public Mesh sharedMesh { get; set; }` / `public bool convex` / `public bool enabled` | 非凸才能贴合凹形衣物 |
| `QueryTriggerInteraction.Ignore` | 枚举值 | |
| `NativeArray<T>` | `public NativeArray(int length, Allocator allocator);`，`.Length`、索引器、`.Dispose()` | `Unity.Collections` |
| `Allocator.TempJob` | 枚举值 | |
| `JobHandle` / `.Complete()` | `public void Complete();` | `Unity.Jobs` |

### 7.3 变换 / 对象 / 场景 / 编辑器

| API | 2022.3 签名 |
|---|---|
| `Transform.localToWorldMatrix` | `public Matrix4x4 localToWorldMatrix { get; }` |
| `Matrix4x4.MultiplyPoint3x4` / `.MultiplyVector` | `public Vector3 MultiplyPoint3x4(Vector3 point);` / `public Vector3 MultiplyVector(Vector3 vector);` |
| `Transform.Find` | `public Transform Find(string n);` |
| `Transform.position` / `.parent` / `.name` | 公开属性 |
| `GameObject(string)` | `public GameObject(string name);` |
| `GameObject.layer` / `.activeInHierarchy` / `.hideFlags` | 公开属性 |
| `GameObject.AddComponent<T>()` | `public T AddComponent<T>() where T : Component;` |
| `Component.GetComponent<T>()` / `GetComponentInChildren<T>(bool)` / `GetComponentsInChildren<T>(bool)` | 泛型重载 |
| `Renderer.enabled` / `.sharedMaterials` / `.gameObject` | 公开属性 |
| `Material.name` | `public string name { get; set; }` |
| `Animator.GetBoneTransform` | `public Transform GetBoneTransform(HumanBodyBones humanBoneId);` |
| `Animator.isHuman` | `public bool isHuman { get; }` |
| `Object.DestroyImmediate` | `public static void DestroyImmediate(Object obj);` |
| `HideFlags.HideAndDontSave` | 枚举值（临时物体不保存） |
| `UnityEngine.Rendering.IndexFormat.UInt32` | 枚举值 |
| `Application.isPlaying` | `public static bool isPlaying { get; }` |
| `Debug.Log/LogWarning/LogError` | `public static void Log(object message);` 等 |
| `Mathf.Max/Floor/Ceil/Lerp/CeilToInt` | `public static float Max(float,float);` / `Floor(float)` / `Ceil(float)` / `Lerp(float,float,float)` / `CeilToInt(float)` |
| `Vector3.Cross/Dot`、`.normalized`、`.sqrMagnitude`、`.down/.up/.zero/.one` | 公开静态/实例成员 |
| `Quaternion.identity` | `public static Quaternion identity { get; }` |

### 7.4 AuditIO 公共件（本文件调用；签名以 `AuditIO.cs` 现状为准）

| API | 签名 | 用途 |
|---|---|---|
| `IAuditTool` | `string ToolId; bool RequiresPlayMode; int DefaultTimeoutSeconds; void Begin(AuditContext); bool Tick(); void Cleanup();` | T2 实现它，被 AuditIO 分派 |
| `AuditContext` | 字段 `JsonObject Request; string OutDir; string Tool; AuditStatus Status; GameObject Avatar; Animator Animator; List<string> Warnings;`；方法 `S/N/I/B/O/A`、`Warn(string)`、`OutPath(string)` | 取请求、写状态、共享缓存 |
| `AuditStatus` | `void Running(string,string); void Done(string,string); void Error(string); void Log(string);` | status.json / audit.log |
| `AuditJson` | `object Parse(string); string Serialize(object, bool pretty=true); void WriteFile(string, object); string Str/…; double Num(JsonObject,string,double); int Int(...); bool Bool(...); JsonObject Obj(...);` | 解析请求 / 写结果 |
| `JsonObject` | `JsonObject Set(string,object); object Get(string); bool Has(string);` | 有序 JSON 对象 |
| `AuditUtil` | `string RelPath(Transform root, Transform t); string ScenePath(Transform); string SafeFileName(string);` | 路径与文件名 |
| `AuditAvatar` | `static GameObject Resolve(string name);` | 头像根解析（同名多根报错） |

---
