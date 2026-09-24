> 🌐 English translation · [中文原文](../../../../../开发工具/通用工具/审查/docs/fit-probe-selfcheck-api.md)

# T2 Fit Probe · Self-Check 1: API Signatures <!-- nav -->

> Formerly: T2 (originally `审查/README_T2.md`) §7. § numbers follow the original; for cross-page § references, look them up in the [document index](../README.md). <!-- nav -->
> Previous: [T2 Fit probe · v3 coverage scope, output, performance](fit-probe-scope-output.md) · Next: [T2 Fit probe · self-check 2/3: restore table, runtime self-checks A/B](fit-probe-selfcheck.md) <!-- nav -->

## 7. Self-check 1: Unity / AuditIO APIs used and their Unity 2022.3 signatures

> Signatures marked ✅ have been checked against the official ScriptReference (2022.3 / 2023.2); the rest are written from documentation knowledge, **please check them too when Claude compiles**.

### 7.1 Skinning / meshes

| API | 2022.3 signature | Notes |
|---|---|---|
| `SkinnedMeshRenderer.BakeMesh` ✅ | `public void BakeMesh(Mesh mesh, bool useScale);` (there's also `BakeMesh(Mesh)`) | `useScale` semantics in item 3 of section 4 |
| `SkinnedMeshRenderer.bones` | `public Transform[] bones { get; set; }` | |
| `SkinnedMeshRenderer.sharedMesh` | `public Mesh sharedMesh { get; set; }` | |
| `SkinnedMeshRenderer.GetBlendShapeWeight` | `public float GetBlendShapeWeight(int index);` | |
| `SkinnedMeshRenderer.SetBlendShapeWeight` | `public void SetBlendShapeWeight(int index, float value);` | Values outside 0–100 allowed (extrapolation) |
| `Mesh.vertices` / `normals` / `triangles` | `public Vector3[] vertices { get; set; }` / `Vector3[] normals` / `int[] triangles` | Non-Readable meshes error; `isReadable` is checked first |
| `Mesh.vertexCount` | `public int vertexCount { get; }` | |
| `Mesh.isReadable` | `public bool isReadable { get; }` | |
| `Mesh.indexFormat` | `public Rendering.IndexFormat indexFormat { get; set; }` | Large meshes must set `UInt32` before writing data |
| `Mesh.RecalculateBounds()` | `public void RecalculateBounds();` | |
| `Mesh.RecalculateNormals()` | `public void RecalculateNormals();` | Recalculated on a copy when normals are missing |
| `Mesh.GetBonesPerVertex()` ✅ | `public Unity.Collections.NativeArray<byte> GetBonesPerVertex();` | Returns a view; don't Dispose |
| `Mesh.GetAllBoneWeights()` ✅ | `public Unity.Collections.NativeArray<BoneWeight1> GetAllBoneWeights();` | Each vertex already sorted by weight descending |
| `Mesh.boneWeights` | `public BoneWeight[] boneWeights { get; set; }` | Legacy fallback |
| `Mesh.blendShapeCount` | `public int blendShapeCount { get; }` | |
| `Mesh.GetBlendShapeName` | `public string GetBlendShapeName(int shapeIndex);` | |
| `Mesh.GetBlendShapeIndex` | `public int GetBlendShapeIndex(string name);` | Returns -1 if not found |
| `BoneWeight1.boneIndex` / `.weight` | `public int boneIndex; public float weight;` | |
| `BoneWeight.boneIndex0..3` / `weight0..3` | Public fields | legacy |
| `MeshFilter.sharedMesh` | `public Mesh sharedMesh { get; set; }` | |

### 7.2 Physics / rays

| API | 2022.3 signature | Notes |
|---|---|---|
| `RaycastCommand` ctor ✅ | `public RaycastCommand(Vector3 from, Vector3 direction, QueryParameters queryParameters, float distance);` | The old `(from,dir,dist,layerMask,maxHits)` is marked Obsolete “no longer supported” in 2022.3, hence the QueryParameters version |
| `RaycastCommand.ScheduleBatch` ✅ | `public static JobHandle ScheduleBatch(NativeArray<RaycastCommand> commands, NativeArray<RaycastHit> results, int minCommandsPerJob, JobHandle dependsOn);` | This overload's `maxHits` defaults to 1; result index = command index |
| `QueryParameters` ctor ✅ | `public QueryParameters(int layerMask, bool hitMultipleFaces, QueryTriggerInteraction hitTriggers, bool hitBackfaces);` | |
| `RaycastHit.collider` / `.normal` / `.distance` / `.triangleIndex` | Public properties | `collider == null` when nothing is hit |
| `Physics.queriesHitBackfaces` ✅ | `public static bool queriesHitBackfaces { get; set; }` | Restore the original value after use |
| `Physics.SyncTransforms()` | `public static void SyncTransforms();` | Called after creating/enabling temporary colliders |
| `Physics.Raycast` | `public static bool Raycast(Vector3 origin, Vector3 direction, out RaycastHit hitInfo, float maxDistance, int layerMask, QueryTriggerInteraction queryTriggerInteraction);` (there are also overloads without out) | Non-Play fallback |
| `Physics.RaycastNonAlloc` | `public static int RaycastNonAlloc(Vector3 origin, Vector3 direction, RaycastHit[] results, float maxDistance, int layerMask, QueryTriggerInteraction queryTriggerInteraction);` | **v3** sole thickness: retrieves all hits of the ray at once (array must be preallocated) |
| `MeshCollider.sharedMesh` / `.convex` / `.enabled` | `public Mesh sharedMesh { get; set; }` / `public bool convex` / `public bool enabled` | Must be non-convex to fit concave clothing |
| `QueryTriggerInteraction.Ignore` | Enum value | |
| `NativeArray<T>` | `public NativeArray(int length, Allocator allocator);`, `.Length`, indexer, `.Dispose()` | `Unity.Collections` |
| `Allocator.TempJob` | Enum value | |
| `JobHandle` / `.Complete()` | `public void Complete();` | `Unity.Jobs` |

### 7.3 Transforms / objects / scenes / editor

| API | 2022.3 signature |
|---|---|
| `Transform.localToWorldMatrix` | `public Matrix4x4 localToWorldMatrix { get; }` |
| `Matrix4x4.MultiplyPoint3x4` / `.MultiplyVector` | `public Vector3 MultiplyPoint3x4(Vector3 point);` / `public Vector3 MultiplyVector(Vector3 vector);` |
| `Transform.Find` | `public Transform Find(string n);` |
| `Transform.position` / `.parent` / `.name` | Public properties |
| `GameObject(string)` | `public GameObject(string name);` |
| `GameObject.layer` / `.activeInHierarchy` / `.hideFlags` | Public properties |
| `GameObject.AddComponent<T>()` | `public T AddComponent<T>() where T : Component;` |
| `Component.GetComponent<T>()` / `GetComponentInChildren<T>(bool)` / `GetComponentsInChildren<T>(bool)` | Generic overloads |
| `Renderer.enabled` / `.sharedMaterials` / `.gameObject` | Public properties |
| `Material.name` | `public string name { get; set; }` |
| `Animator.GetBoneTransform` | `public Transform GetBoneTransform(HumanBodyBones humanBoneId);` |
| `Animator.isHuman` | `public bool isHuman { get; }` |
| `Object.DestroyImmediate` | `public static void DestroyImmediate(Object obj);` |
| `HideFlags.HideAndDontSave` | Enum value (temporary objects aren't saved) |
| `UnityEngine.Rendering.IndexFormat.UInt32` | Enum value |
| `Application.isPlaying` | `public static bool isPlaying { get; }` |
| `Debug.Log/LogWarning/LogError` | `public static void Log(object message);` etc. |
| `Mathf.Max/Floor/Ceil/Lerp/CeilToInt` | `public static float Max(float,float);` / `Floor(float)` / `Ceil(float)` / `Lerp(float,float,float)` / `CeilToInt(float)` |
| `Vector3.Cross/Dot`, `.normalized`, `.sqrMagnitude`, `.down/.up/.zero/.one` | Public static/instance members |
| `Quaternion.identity` | `public static Quaternion identity { get; }` |

### 7.4 AuditIO common components (called by this file; signatures per the current `AuditIO.cs`)

| API | Signature | Purpose |
|---|---|---|
| `IAuditTool` | `string ToolId; bool RequiresPlayMode; int DefaultTimeoutSeconds; void Begin(AuditContext); bool Tick(); void Cleanup();` | Implemented by T2, dispatched by AuditIO |
| `AuditContext` | Fields `JsonObject Request; string OutDir; string Tool; AuditStatus Status; GameObject Avatar; Animator Animator; List<string> Warnings;`; methods `S/N/I/B/O/A`, `Warn(string)`, `OutPath(string)` | Get the request, write status, shared cache |
| `AuditStatus` | `void Running(string,string); void Done(string,string); void Error(string); void Log(string);` | status.json / audit.log |
| `AuditJson` | `object Parse(string); string Serialize(object, bool pretty=true); void WriteFile(string, object); string Str/…; double Num(JsonObject,string,double); int Int(...); bool Bool(...); JsonObject Obj(...);` | Parse requests / write results |
| `JsonObject` | `JsonObject Set(string,object); object Get(string); bool Has(string);` | Ordered JSON object |
| `AuditUtil` | `string RelPath(Transform root, Transform t); string ScenePath(Transform); string SafeFileName(string);` | Paths and file names |
| `AuditAvatar` | `static GameObject Resolve(string name);` | Avatar root resolution (errors on same-name multiple roots) |

---
