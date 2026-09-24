// ══════════════════════════════════════════════════════════════════
// 【项目沉淀】通用工具 · 客户单审查 T2「贴合探针」
// 适用素体：任意 Humanoid 头像（VRChat 3.x / Unity 2022.3）
// 相关素材：无
// 工具链　：Unity 2022.3.22f1（Editor 程序集；只用 UnityEngine / Unity.Collections /
// 　　　　　Unity.Jobs，无第三方依赖，不依赖 VRChat / MA / UnityEditor 类型）
// 可复用性：★★★ 换单子直接复制到 <工程>/Assets/Editor/AvatarAudit/
// 用途　　：用几何数值判定「身体从衣物/鞋袜里穿出」与「脚与鞋不贴合」。
// 　　　　　用户的痛点是：曲线/组件数据上没错，但看上去不对 —— 所以这里不谈动画层，
// 　　　　　只对「烘焙后的当前姿势蒙皮网格」量几何：身体顶点沿法线打射线，看打不打得
// 　　　　　到衣物、打到的是正面还是背面，由此判 covered / pierced。
//
// ── 与 AuditIO.cs 的接口（本文件实现 IAuditTool，由 AuditIO 分派）────────────
// AuditIO.cs 里已有分派表，需要加的一行（工具 C 已确认接口存在）：
//     else if (toolId == "fit") tool = new AuditFitProbe();
// 本类实现：
//     public sealed class AuditFitProbe : IAuditTool
//     string ToolId              => "fit"
//     bool   RequiresPlayMode    => true      // T1 设好的状态只在 Play 模式里存在；
//                                             // 且只有 Play 模式才启用 RaycastCommand 批处理
//     int    DefaultTimeoutSeconds => 1800
//     void   Begin(AuditContext ctx)          // 同步跑完全部：解析请求→烘焙→射线→写 fit_<state_id>.json
//     bool   Tick()              => true      // Begin 已做完，下一帧即结束
//     void   Cleanup()                        // 幂等兜底：恢复临时改动、销毁临时物体
//   请求文件：<工程>/Library/AvatarAudit/request.json ，"tool":"fit"
//   输出：<ctx.OutDir>/fit_<state_id>.json ；进度写 <ctx.OutDir>/status.json（由 ctx.Status 负责）
// 说明：T2 不需要多帧，Begin 里同步完成即可；大工程会阻塞主线程数秒~十几秒，属预期。
//
// 设计取舍（为什么这么做）：
//   · 不说「哪根曲线接错」，只说「哪个部位、哪件衣物、穿出多少毫米」——这是能用眼睛复核的口径。
//   · 全部射线限制在一个空闲 layer（衣物默认 30、身体默认 29）的临时 MeshCollider 上，一次只启用一件
//     衣物，避免把场景里别的碰撞体（PhysBone Collider 等）算进来。
//   · 部位映射（v2）：不看骨骼名是否精确等于 HumanBodyBones，而是沿父链向上遇到的第一个人形骨骼；
//     Play 模式下 MA/AAO 会插入 Const bone、合并出 "Foot_L$Toe_L$85" 这类名字，精确匹配会整片落空。
//   · 被删除/不可见顶点（v2）：MA ShapeChanger 的 Delete 用 NaNimation 骨骼把顶点移走、或被形态键
//     拉到极远，这些顶点不参与统计，按原因计数进 excluded_vertices。
//   · 薄部位误报（v2）：给身体也建 MeshCollider，内向/外向射线若在衣物命中前先命中身体，说明打到的是
//     对侧表面，不算 covered/pierced；另用「衣物命中法线须与身体顶点法线同向」兜底。
//   · 判正面/背面：优先用 hit.normal 的符号（与任务书一致），但启动时先用一块自建四边形
//     标定一次 Unity 的实际约定（背面命中时 normal 会不会被翻、winding 方向），标定失败才退回
//     任务书默认。原因见 Calibrate() 注释：这个符号一旦反了，整个工具会「全 0」静默出错。
//   · 所有临时改动（形态键、renderer.enabled、Physics.queriesHitBackfaces、临时物体/网格）
//     都登记进 _restores / _trash，在 finally 里逆序恢复并 DestroyImmediate；
//     全程不 MarkSceneDirty、不 SaveScene（Play 模式下场景改动本来就不会保存）。
//
// v3（工程A 2026-09-18 实测两处修正）：
//   · 覆盖范围（coverage scope）：一个身体顶点只对「自身蒙皮覆盖该部位的衣物」计入 covered/pierced。
//     部位集合由该衣物自己的顶点主骨骼（按部位归并、顶点数占比 ≥ region_min_share）决定；
//     不在集合里的命中改记 out_of_scope，不再冒充穿出（sailor 上衣误报 RightHand/Thumb 的根因）。
//   · 脚部专项：从「每只脚挑一件覆盖最多的衣物」改为「每只脚 × 每件覆盖该脚的衣物」分别输出，
//     并把衣物分成 footwear（鞋）/ legwear（袜）/ other：分类依据优先级 请求显式 > 几何厚度 > 名称关键词。
//     footwear 才报「脚底到鞋内底有向距离/脚跟/脚尖」；legwear 不算鞋底指标，只报穿出与平均间隙。
// ══════════════════════════════════════════════════════════════════

using System;
using System.Collections.Generic;
using System.Text.RegularExpressions;
using Unity.Collections;
using Unity.Jobs;
using UnityEngine;
using UnityEngine.Rendering;
using Object = UnityEngine.Object;
using Stopwatch = System.Diagnostics.Stopwatch;

namespace AvatarAudit
{
    public sealed class AuditFitProbe : IAuditTool
    {
        /// <summary>衣物临时 MeshCollider 放在这个 layer。30/31 是用户层，任务书举例 30。
        /// 为什么不用 0~7：内置层可能被场景其它系统占用；30 通常空闲。
        /// 若头像自己也在 30 层有碰撞体，射线会打到它们，warning 会提示。</summary>
        public const int TempLayer = 30;

        /// <summary>身体临时 MeshCollider 放在这个 layer（v2 新增，任务书举例 29）。
        /// 为什么与衣物分两个 layer：射线要分别问「先打到身体还是先打到衣物」，
        /// 两次批量查询各用一个 mask，互不干扰，也避免在同一批结果里区分 collider 类型。</summary>
        public const int BodyLayer = 29;

        public string ToolId { get { return "fit"; } }

        /// <summary>T1 设好的状态只在 Play 模式里存在；也只有 Play 模式才用 RaycastCommand 批处理。</summary>
        public bool RequiresPlayMode { get { return true; } }

        public int DefaultTimeoutSeconds { get { return 1800; } }

        private Probe _probe;

        public void Begin(AuditContext ctx)
        {
            _probe = new Probe(ctx);
            _probe.Run();          // 同步跑完；失败直接抛，由 AuditIO 落 status.json=error
        }

        /// <summary>Begin 已把活干完；返回 true 让 AuditIO 的泵下一帧收尾。</summary>
        public bool Tick() { return true; }

        /// <summary>幂等兜底：正常路径下 Probe.Run 的 finally 已恢复/销毁，这里只处理异常中断的残留。</summary>
        public void Cleanup()
        {
            if (_probe != null)
            {
                try { _probe.Cleanup(); }
                catch (Exception e) { Debug.LogWarning("[AuditFitProbe] Cleanup 异常: " + e.Message); }
                _probe = null;
            }
        }

        // ─────────────────────────────────────────────────────────────
        // 执行体：一个请求一个实例，状态全在里面
        // ─────────────────────────────────────────────────────────────
        sealed class Probe
        {
            const float RayOffsetM = 0.0005f;   // 0.5 mm：射线起点离开身体表面，躲开共面精度问题
            const float DegenerateSqr = 1e-12f;
            const float FarFromHipsM = 3.0f;    // 顶点到 Hips 超过 3 m 视为被形态键拉远/已删除
            const int BoneWalkGuard = 512;      // 父链异常成环时的兜底步数

            readonly AuditContext _ctx;

            // 请求参数
            string _stateId = "default";
            string _bodySpec = "auto";
            string _hide;
            JsonObject _perturb;
            float _coverMm = 25f;
            float _pierceMm = 15f;
            float _minDepthMm = 1f;
            int _markersTop = 200;
            bool _footEnabled = true;
            float _footProbeMm = 40f;
            Regex _excludeRe;
            Regex _includeOnly;
            Regex _footKeyRe;

            // v3：覆盖范围（coverage scope）与脚部衣物分类
            float _regionMinShare = 0.02f;      // 衣物顶点里主骨骼归到某部位的占比达到它才算「覆盖该部位」
            float _soleMinMm = 4f;              // 脚底下方厚度 ≥ 它 → footwear
            const float LegwearMaxMm = 2f;      // 脚底下方厚度 < 它 → legwear；两者之间几何不表态
            const string ClassFootwear = "footwear";
            const string ClassLegwear = "legwear";
            const string ClassOther = "other";
            readonly HashSet<string> _footwearPaths = new HashSet<string>(StringComparer.Ordinal);
            readonly HashSet<string> _footwearLeaves = new HashSet<string>(StringComparer.Ordinal);
            readonly HashSet<string> _legwearPaths = new HashSet<string>(StringComparer.Ordinal);
            readonly HashSet<string> _legwearLeaves = new HashSet<string>(StringComparer.Ordinal);
            Regex _footwearNameRe;
            Regex _legwearNameRe;
            readonly RaycastHit[] _thickBuf = new RaycastHit[16];   // 脚底厚度：一条射线一次拿全部命中（非分配版）

            readonly Stopwatch _clock = new Stopwatch();
            readonly Dictionary<string, double> _timings = new Dictionary<string, double>();
            readonly List<Action> _restores = new List<Action>();
            readonly List<Object> _trash = new List<Object>();
            bool _cleaned;

            Transform _avatar;
            Animator _anim;
            readonly Dictionary<Transform, string> _boneNames = new Dictionary<Transform, string>();
            // v2 部位映射：全部人形骨骼 Transform 的集合；沿父链向上遇到的第一个即该部位。
            readonly HashSet<Transform> _humanoidSet = new HashSet<Transform>();
            readonly Dictionary<Transform, string> _regionCache = new Dictionary<Transform, string>();
            readonly Dictionary<Transform, bool> _naniCache = new Dictionary<Transform, bool>();
            // region -> 最多 3 个原始骨骼名（诊断用，验证映射没跑偏）
            readonly Dictionary<string, List<string>> _regionExamples = new Dictionary<string, List<string>>();

            SkinnedMeshRenderer _bodySmr;
            Mesh _bodyBaked;
            Vector3[] _bodyPos;
            Vector3[] _bodyNrm;
            string[] _bodyRegion;
            HashSet<string> _bodyRegionSet;   // v3：身体实际出现过的部位名（衣物覆盖集合的交叉校验）
            bool[] _bodyExcluded;
            int _bodyCount;
            int _bodyUsedCount;
            int _exNanimated, _exNonFinite, _exZeroWeight;
            string _bodyPath = "";
            string _weightsSource = "none";
            readonly List<BodyCandidate> _bodyCandidateInfo = new List<BodyCandidate>();

            // v2：身体临时 MeshCollider（layer BodyLayer）与一次算好的身体命中
            Mesh _bodyColliderMesh;
            GameObject _bodyColliderGo;
            MeshCollider _bodyCollider;
            Vector3[] _rayO, _rayD;
            float[] _rayDist;
            RaycastHit[] _bodyHits;

            List<int>[] _footVertIdx;
            List<int>[] _footSoleIdx;

            readonly List<Garment> _garments = new List<Garment>();
            readonly List<FootResult> _feet = new List<FootResult>();
            TopK _markers;
            int _done;

            RayShooter _rays;
            // T-10：可选内嵌 T-28a 静态穿出斑块（poke）块；请求 "poke": true 或对象时启用。
            bool _pokeEnabled;
            JsonObject _pokeJson;
            // 法线约定标定结果（见 Calibrate）
            bool _hitNormalUsable = true;
            int _windingSign = 1;
            string _calibDetail = "default(winding=+1, hit.normal 可用)";

            public Probe(AuditContext ctx) { _ctx = ctx; }

            public void Run()
            {
                bool savedBackfaces = Physics.queriesHitBackfaces;
                try
                {
                    ApplyRequest();
                    _markers = new TopK(_markersTop);
                    _rays = new RayShooter(_ctx);

                    Measure("calibrate", Calibrate);

                    _ctx.Status.Running("avatar", _ctx.S("avatar"));
                    Measure("resolve_avatar", ResolveAvatar);
                    Measure("find_body", FindBody);

                    _ctx.Status.Running("collect", "收集衣物");
                    Measure("collect_garments", CollectGarments);
                    Measure("apply_selfcheck", ApplyPerturbAndHide);

                    _ctx.Status.Running("bake_body", _bodyPath);
                    Measure("bake_body", BakeBody);
                    Measure("regions", ComputeRegions);
                    Measure("body_collider", BuildBodyCollider);
                    PrepareFootIndices();

                    _ctx.Status.Running("bake_garments", "0/" + _garments.Count);
                    Measure("bake_garments", BakeGarments);

                    // 全局打开背面命中；QueryParameters 里也逐条显式写 true，双保险。
                    // 为什么：不打开背面命中，就看不到「身体在衣物里面」时射线从内侧打到衣物背面。
                    Physics.queriesHitBackfaces = true;
                    _clock.Restart();
                    RunProbes();
                    _timings["raycast"] = _clock.Elapsed.TotalMilliseconds;

                    if (_footEnabled) Measure("feet", BuildFeet);
                    if (_pokeEnabled) Measure("poke", RunPokeBlock);

                    string fileName = "geo_" + AuditUtil.SafeFileName(_stateId) + ".json";
                    string outPath = _ctx.OutPath(fileName);
                    Measure("write", () => WriteOutput(outPath));
                    _ctx.Status.Log("T2/T-10 完成 -> " + outPath);
                }
                finally
                {
                    // 恢复顺序与登记顺序相反，保证嵌套改动按栈解开
                    Cleanup();
                    Physics.queriesHitBackfaces = savedBackfaces;
                }
            }

            void Measure(string key, Action a)
            {
                _clock.Restart();
                a();
                _timings[key] = _clock.Elapsed.TotalMilliseconds;
            }

            // ── 请求解析（走 AuditIO 的 AuditJson，请求原样保留在 ctx.Request 里）──
            void ApplyRequest()
            {
                if (string.IsNullOrEmpty(_ctx.S("avatar"))) throw new Exception("请求缺 avatar（头像根名）");
                _stateId = _ctx.S("state_id", "default");
                _bodySpec = _ctx.S("body", "auto");
                _hide = _ctx.S("hide");
                _perturb = _ctx.O("perturb");

                _coverMm = (float)_ctx.N("cover_mm", 25);
                _pierceMm = (float)_ctx.N("pierce_mm", 15);
                _minDepthMm = (float)_ctx.N("min_depth_mm", 1.0);
                _markersTop = _ctx.I("markers_top", 200);
                if (_coverMm <= 0f) _coverMm = 25f;
                if (_pierceMm <= 0f) _pierceMm = 15f;
                if (_minDepthMm <= 0f) _minDepthMm = 1f;
                if (_markersTop <= 0) _markersTop = 200;

                string exclude = _ctx.S("exclude_name_regex",
                    "(?i)(hair|face|eye|lash|tooth|tongue|head|halo|particle|nail|avatarhight|tail|ear)");
                if (string.IsNullOrEmpty(exclude))
                    exclude = "(?i)(hair|face|eye|lash|tooth|tongue|head|halo|particle|nail|avatarhight|tail|ear)";
                _excludeRe = new Regex(exclude, RegexOptions.CultureInvariant);

                // v2：include_only —— 只测匹配的衣物（正则）；缺省 null 表示不限制。
                string includeOnly = _ctx.S("include_only");
                _includeOnly = string.IsNullOrEmpty(includeOnly)
                    ? null
                    : new Regex(includeOnly, RegexOptions.CultureInvariant);

                _footKeyRe = new Regex("(?i)(foot|heel|toe|shoe|highheel|sock)", RegexOptions.CultureInvariant);

                // v3 覆盖范围阈值：允许写 0.02 或 2（都表示 2%）；非法值退回 0.02。
                _regionMinShare = (float)_ctx.N("region_min_share", 0.02);
                if (_regionMinShare > 1f) _regionMinShare *= 0.01f;
                if (_regionMinShare <= 0f || _regionMinShare > 1f) _regionMinShare = 0.02f;

                JsonObject foot = _ctx.O("foot");
                // 请求里没写 foot 键（ctx.O 返回 null）→ 默认开；写了就按 enabled 字段（缺省视为 true）
                _footEnabled = foot == null || AuditJson.Bool(foot, "enabled", true);
                _footProbeMm = foot != null ? (float)AuditJson.Num(foot, "probe_mm", 40) : 40f;
                if (_footProbeMm <= 0f) _footProbeMm = 40f;
                // sole_min_mm 优先取 foot 里的，退到顶层，默认 4 mm。
                _soleMinMm = (float)AuditJson.Num(foot, "sole_min_mm", _ctx.N("sole_min_mm", 4));
                if (_soleMinMm <= 0f) _soleMinMm = 4f;

                // v3 脚部衣物分类：名称兜底关键词 + 请求显式清单（foot.footwear / foot.legwear）。
                _footwearNameRe = new Regex("(?i)(shoe|boot|loafer|heel|sandal|sneaker|靴|鞋)", RegexOptions.CultureInvariant);
                _legwearNameRe = new Regex("(?i)(sock|stocking|tights|袜)", RegexOptions.CultureInvariant);
                _footwearPaths.Clear(); _footwearLeaves.Clear();
                _legwearPaths.Clear(); _legwearLeaves.Clear();
                ReadFootPaths(AuditJson.Arr(foot, "footwear"), _footwearPaths, _footwearLeaves);
                ReadFootPaths(AuditJson.Arr(foot, "legwear"), _legwearPaths, _legwearLeaves);

                // T-10：内嵌 poke 块。请求写 "poke": true 或 "poke": {…} 启用；参数见 审查/docs/probe-poke.md（原 README §3.2.5）。
                _pokeEnabled = _ctx.O("poke") != null || _ctx.B("poke", false);
            }

            /// <summary>T-10：在 fit 的同一帧上跑 T-28a 静态穿出斑块（复用 AuditProbes 的实现）。</summary>
            void RunPokeBlock()
            {
                _pokeJson = AuditProbes.RunPoke(_ctx, _avatar.gameObject, _anim);
            }

            /// <summary>把请求里的路径清单同时按「相对头像根的全路径」和「叶子名」两种口径收下，
            /// 因为调用方可能只写得出 `loafer` 也可能写得出 `kaguya_cloth/loafer`。</summary>
            static void ReadFootPaths(List<object> arr, HashSet<string> full, HashSet<string> leaves)
            {
                if (arr == null) return;
                for (int i = 0; i < arr.Count; i++)
                {
                    string s = arr[i] as string;
                    if (s == null) s = Convert.ToString(arr[i], System.Globalization.CultureInfo.InvariantCulture);
                    if (string.IsNullOrEmpty(s)) continue;
                    s = s.Trim();
                    if (s.Length == 0) continue;
                    full.Add(s);
                    int slash = s.LastIndexOf('/');
                    leaves.Add(slash >= 0 && slash + 1 < s.Length ? s.Substring(slash + 1) : s);
                }
            }

            // ── 法线约定标定 ────────────────────────────────────────
            // 为什么必须做：整套判据都靠 dot(射线方向, 命中面法线) 的符号区分正面/背面。
            // Unity 在 queriesHitBackfaces=true 时，hit.normal 是否会被翻成「朝向射线」，
            // 以及叉乘 winding 与「正面」的对应，都不是我们能凭空断言的（版本间有差异）。
            // 一旦符号反了，结果是「covered 全 0 / pierced 全 0」这种静默错误，很难发现。
            // 这里用一块自建四边形做一次可控实验：先关背面命中，看从哪一侧能打到（定正面在叉乘法线的哪一边）；
            // 再开背面命中，看 hit.normal 是否指向正面（定 hit.normal 能不能直接用）。
            void Calibrate()
            {
                _windingSign = 1;
                _hitNormalUsable = true;
                bool saved = Physics.queriesHitBackfaces;
                GameObject cgo = null;
                Mesh cm = null;
                try
                {
                    var verts = new Vector3[]
                    {
                        new Vector3(0f, 0f, 0f), new Vector3(1f, 0f, 0f),
                        new Vector3(0f, 0f, 1f), new Vector3(1f, 0f, 1f)
                    };
                    var tris = new int[] { 0, 1, 2, 2, 1, 3 };
                    Vector3 gn = Vector3.Cross(verts[1] - verts[0], verts[2] - verts[0]);
                    if (gn.sqrMagnitude < DegenerateSqr) { _ctx.Warn("标定：叉乘法线退化，沿用默认约定"); return; }
                    gn.Normalize();

                    cm = new Mesh();
                    cm.indexFormat = IndexFormat.UInt32;
                    cm.hideFlags = HideFlags.HideAndDontSave;
                    cm.vertices = verts;
                    cm.triangles = tris;
                    cm.RecalculateBounds();

                    cgo = new GameObject("__AuditFitProbe_calib__");
                    cgo.hideFlags = HideFlags.HideAndDontSave;
                    cgo.layer = TempLayer;
                    MeshCollider mc = cgo.AddComponent<MeshCollider>();
                    mc.sharedMesh = cm;
                    mc.convex = false;
                    Physics.SyncTransforms();

                    Vector3 center = new Vector3(0.5f, 0f, 0.5f);

                    // 1) 关背面命中：从 +gn 侧打得到 => +gn 是正面 => windingSign=+1
                    Physics.queriesHitBackfaces = false;
                    bool frontIsPlus = Physics.Raycast(center + gn * 2f, -gn, 10f, 1 << TempLayer, QueryTriggerInteraction.Ignore);
                    bool frontIsMinus = false;
                    if (!frontIsPlus)
                        frontIsMinus = Physics.Raycast(center - gn * 2f, gn, 10f, 1 << TempLayer, QueryTriggerInteraction.Ignore);
                    if (frontIsPlus) _windingSign = 1;
                    else if (frontIsMinus) _windingSign = -1;
                    else _ctx.Warn("标定：四边形两侧都打不到，沿用默认 winding=+1");

                    // 2) 开背面命中：从正面打，看 hit.normal 是否指向正面（即是否未被翻转）
                    Physics.queriesHitBackfaces = true;
                    Vector3 frontDir = gn * _windingSign;
                    if (Physics.Raycast(center + frontDir * 2f, -frontDir, out RaycastHit h, 10f, 1 << TempLayer, QueryTriggerInteraction.Ignore))
                        _hitNormalUsable = Vector3.Dot(h.normal, frontDir) > 0.5f;
                    else
                    {
                        _hitNormalUsable = true;
                        _ctx.Warn("标定：正面射线未命中，沿用 hit.normal 可用");
                    }

                    _calibDetail = "winding_sign=" + _windingSign + ", hit_normal_usable=" + _hitNormalUsable
                                 + ", front_is_plus=" + frontIsPlus + ", front_is_minus=" + frontIsMinus;
                }
                catch (Exception e)
                {
                    _ctx.Warn("标定异常，沿用默认法线约定: " + e.Message);
                }
                finally
                {
                    Physics.queriesHitBackfaces = saved;
                    if (cgo != null) Object.DestroyImmediate(cgo);
                    if (cm != null) Object.DestroyImmediate(cm);
                }
            }

            // ── 头像 / 骨骼（复用 AuditIO 的 AuditAvatar.Resolve：同名多根的口径与 T1/T3 一致）──
            void ResolveAvatar()
            {
                GameObject go = _ctx.Avatar != null ? _ctx.Avatar : AuditAvatar.Resolve(_ctx.S("avatar"));
                _ctx.Avatar = go;
                _avatar = go.transform;

                _anim = _ctx.Animator;
                if (_anim == null) _anim = go.GetComponent<Animator>();
                if (_anim == null) _anim = go.GetComponentInChildren<Animator>(true);
                _ctx.Animator = _anim;
                if (_anim == null) _ctx.Warn("头像上没有 Animator：body=auto 无法判定，部位名会退化为骨骼原名");
                BuildBoneNameMap();
                WarnIfTempLayerOccupied();
            }

            void BuildBoneNameMap()
            {
                _boneNames.Clear();
                _humanoidSet.Clear();
                _regionCache.Clear();
                _naniCache.Clear();
                if (_anim == null || !_anim.isHuman) return;
                Array values = Enum.GetValues(typeof(HumanBodyBones));
                foreach (HumanBodyBones b in values)
                {
                    if (b == HumanBodyBones.LastBone) continue;
                    Transform t = null;
                    try { t = _anim.GetBoneTransform(b); } catch { }
                    if (t != null && !_boneNames.ContainsKey(t))
                    {
                        _boneNames[t] = b.ToString();
                        _humanoidSet.Add(t);
                    }
                }
            }

            // ── v2 部位映射：沿父链向上找到的第一个 HumanBodyBones 即部位 ──────
            // 为什么：Play 模式下 MA/AAO 会插入 Const bone、把多个骨骼合并成
            // "Foot_L$Toe_L$85" 这类名字，SMR.bones 里往往没有 GetBoneTransform 的原始
            // Transform；只做精确匹配会整片落到原名（脚部就会 covered=0）。沿父链上溯
            // 到最近的人形骨骼，才能把 Foot_L$... 归到 LeftFoot/LeftToes。
            string RegionOfBone(Transform t)
            {
                if (t == null) return "unknown";
                string cached;
                if (_regionCache.TryGetValue(t, out cached)) return cached;

                Transform cur = t;
                string region = null;
                int guard = 0;
                while (cur != null && guard++ < BoneWalkGuard)
                {
                    string name;
                    if (_boneNames.TryGetValue(cur, out name)) { region = name; break; }
                    if (cur == _avatar) break;          // 走到头像根还没遇到人形骨骼
                    cur = cur.parent;
                }
                // 没有人形 Animator（_humanoidSet 为空）时退化为骨骼原名，保持旧行为可用；
                // 有人形骨骼但这条父链接不上时按任务书记 Other。
                if (region == null)
                    region = _humanoidSet.Count == 0 ? t.name : "Other";

                _regionCache[t] = region;
                return region;
            }

            bool IsNanimatedBone(Transform t)
            {
                if (t == null) return false;
                bool cached;
                if (_naniCache.TryGetValue(t, out cached)) return cached;

                bool hit = false;
                Transform cur = t;
                int guard = 0;
                while (cur != null && guard++ < BoneWalkGuard)
                {
                    if (cur.name != null && cur.name.IndexOf("NaNimat", StringComparison.OrdinalIgnoreCase) >= 0)
                    {
                        hit = true;
                        break;
                    }
                    if (cur == _avatar) break;
                    cur = cur.parent;
                }
                _naniCache[t] = hit;
                return hit;
            }

            void RecordRegionExample(string region, string boneName)
            {
                if (string.IsNullOrEmpty(region) || string.IsNullOrEmpty(boneName)) return;
                List<string> list;
                if (!_regionExamples.TryGetValue(region, out list))
                {
                    list = new List<string>();
                    _regionExamples[region] = list;
                }
                if (list.Count >= 3) return;
                if (!list.Contains(boneName)) list.Add(boneName);
            }

            // 若头像自己已有碰撞体落在临时 layer 上，射线会误命中；给出警告而不是静默出错。
            void WarnIfTempLayerOccupied()
            {
                Collider[] cols = _avatar.GetComponentsInChildren<Collider>(true);
                bool warned30 = false, warned29 = false;
                for (int i = 0; i < cols.Length; i++)
                {
                    if (cols[i] == null) continue;
                    int layer = cols[i].gameObject.layer;
                    if (layer == TempLayer && !warned30)
                    {
                        warned30 = true;
                        _ctx.Warn("头像里已有层 " + TempLayer + " 的碰撞体（" + AuditUtil.RelPath(_avatar, cols[i].transform) +
                                  "），贴合射线可能误命中；建议换层或先禁用。");
                    }
                    else if (layer == BodyLayer && !warned29)
                    {
                        warned29 = true;
                        _ctx.Warn("头像里已有层 " + BodyLayer + " 的碰撞体（" + AuditUtil.RelPath(_avatar, cols[i].transform) +
                                  "），身体薄壁判定可能误命中；建议换层或先禁用。");
                    }
                    if (warned30 && warned29) break;
                }
            }

            // ── 定身体网格 ──────────────────────────────────────────
            void FindBody()
            {
                if (_bodySpec != "auto")
                {
                    Transform t = FindByPath(_bodySpec);
                    if (t == null) throw new Exception("找不到 body 路径: " + _bodySpec);
                    _bodySmr = t.GetComponent<SkinnedMeshRenderer>();
                    if (_bodySmr == null) throw new Exception("body 不是 SkinnedMeshRenderer: " + _bodySpec);
                    _bodyPath = AuditUtil.RelPath(_avatar, t);
                    return;
                }
                if (_anim == null || !_anim.isHuman)
                    throw new Exception("body=auto 需要头像根上有 Humanoid Animator（或改用 body 显式指定路径）");
                if (_humanoidSet.Count == 0)
                    throw new Exception("Humanoid Animator 取不到任何人形骨骼，body=auto 无法判定");

                // v2：不看 SMR.bones 是否精确等于 GetBoneTransform 的 Transform（Play 模式下
                // MA/AAO 会改写层级，这样永远匹配不到），而是把每个候选的骨骼按第 1 条映射成
                // 人形部位集合。v4（任务 AY）：选择改走共享判据 AuditBodyPick —— 名字候选
                // （Body_b/Body_base/Body）优先且要过「蒙皮权重同时覆盖脚与躯干」关，再退几何启发。
                // 这里仍逐候选登记 body_candidates 供排查；选择不在此处做。
                var vis = new List<SkinnedMeshRenderer>();
                SkinnedMeshRenderer[] smrs = _avatar.GetComponentsInChildren<SkinnedMeshRenderer>(true);
                for (int i = 0; i < smrs.Length; i++)
                {
                    SkinnedMeshRenderer smr = smrs[i];
                    if (smr == null || smr.sharedMesh == null) continue;
                    if (!smr.gameObject.activeInHierarchy || !smr.enabled) continue;
                    vis.Add(smr);
                    Transform[] bones = smr.bones;
                    if (bones == null || bones.Length == 0) continue;

                    HashSet<string> regions = new HashSet<string>();
                    for (int b = 0; b < bones.Length; b++)
                    {
                        string reg = RegionOfBone(bones[b]);
                        if (!string.IsNullOrEmpty(reg)) regions.Add(reg);
                    }
                    bool hasFoot = regions.Contains("LeftFoot") || regions.Contains("LeftLowerLeg");
                    bool hasTorso = regions.Contains("Chest") || regions.Contains("Spine");

                    List<string> sorted = new List<string>(regions);
                    sorted.Sort(StringComparer.Ordinal);
                    BodyCandidate bc = new BodyCandidate();
                    bc.path = AuditUtil.RelPath(_avatar, smr.transform);
                    bc.vertices = smr.sharedMesh.vertexCount;
                    bc.regions = sorted;
                    bc.hasFoot = hasFoot;
                    bc.hasTorso = hasTorso;
                    bc.selected = false;
                    _bodyCandidateInfo.Add(bc);
                }
                SkinnedMeshRenderer best = AuditBodyPick.FindBodySmr(vis, RegionOfBone);
                if (best == null)
                    throw new Exception("body=auto 没找到同时含（LeftFoot|LeftLowerLeg）与（Chest|Spine）人形部位、且蒙皮权重覆盖脚+躯干的可见 SkinnedMeshRenderer");
                _bodySmr = best;
                _bodyPath = AuditUtil.RelPath(_avatar, best.transform);
                for (int i = 0; i < _bodyCandidateInfo.Count; i++)
                    if (_bodyCandidateInfo[i].path == _bodyPath) _bodyCandidateInfo[i].selected = true;
            }

            // ── 衣物候选 ────────────────────────────────────────────
            void CollectGarments()
            {
                _garments.Clear();
                Renderer[] all = _avatar.GetComponentsInChildren<Renderer>(true);
                for (int i = 0; i < all.Length; i++)
                {
                    Renderer r = all[i];
                    if (r == null || r == _bodySmr) continue;
                    if (!(r is SkinnedMeshRenderer) && !(r is MeshRenderer)) continue;
                    GameObject go = r.gameObject;
                    // 只收可见的：隐着的衣物不参与判定（hide 自检也走这条，故先收集后隐藏）
                    if (!go.activeInHierarchy || !r.enabled) continue;
                    if (_excludeRe.IsMatch(go.name)) continue;
                    if (_includeOnly != null && !_includeOnly.IsMatch(go.name)) continue;   // v2：只测匹配的衣物
                    Mesh m = MeshOf(r);
                    if (m == null || m.vertexCount == 0) continue;
                    _garments.Add(new Garment
                    {
                        renderer = r,
                        path = AuditUtil.RelPath(_avatar, r.transform),
                        materials = MaterialNames(r),
                        vertexCount = m.vertexCount
                    });
                }
                // 排序保证同名工程两次运行结果顺序一致（确定性自检）
                _garments.Sort((a, b) => string.CompareOrdinal(a.path, b.path));
            }

            // ── 自检开关：perturb / hide ─────────────────────────────
            void ApplyPerturbAndHide()
            {
                if (!string.IsNullOrEmpty(_hide))
                {
                    Transform t = FindByPath(_hide);
                    if (t == null) throw new Exception("hide 找不到渲染器路径: " + _hide);
                    Renderer r = t.GetComponent<Renderer>();
                    if (r == null) throw new Exception("hide 目标不是 Renderer: " + _hide);
                    bool old = r.enabled;
                    r.enabled = false;
                    _restores.Add(() => r.enabled = old);
                }

                if (_perturb != null)
                {
                    string rp = AuditJson.Str(_perturb, "renderer");
                    string bs = AuditJson.Str(_perturb, "blendshape");
                    float w = (float)AuditJson.Num(_perturb, "weight", 100);
                    if (!string.IsNullOrEmpty(rp) && !string.IsNullOrEmpty(bs))
                    {
                        Transform t = FindByPath(rp);
                        if (t == null) throw new Exception("perturb 找不到渲染器路径: " + rp);
                        SkinnedMeshRenderer smr = t.GetComponent<SkinnedMeshRenderer>();
                        if (smr == null || smr.sharedMesh == null) throw new Exception("perturb 目标不是带网格的 SkinnedMeshRenderer");
                        int idx = smr.sharedMesh.GetBlendShapeIndex(bs);
                        if (idx < 0) throw new Exception("perturb 找不到形态键: " + bs);
                        float old = smr.GetBlendShapeWeight(idx);
                        smr.SetBlendShapeWeight(idx, w);
                        _restores.Add(() => smr.SetBlendShapeWeight(idx, old));
                    }
                }
            }

            // ── 烘焙身体 ────────────────────────────────────────────
            void BakeBody()
            {
                _bodyBaked = new Mesh();
                _bodyBaked.indexFormat = IndexFormat.UInt32;      // 身体常 >65535 顶点
                _bodyBaked.hideFlags = HideFlags.HideAndDontSave;
                _bodySmr.BakeMesh(_bodyBaked, true);
                Vector3[] localPos = _bodyBaked.vertices;
                Vector3[] localNrm = _bodyBaked.normals;
                _bodyCount = localPos != null ? localPos.Length : 0;
                if (_bodyCount == 0) throw new Exception("身体网格烘焙为空（BakeMesh 返回 0 顶点）");

                // 为什么用 localToWorldMatrix：BakeMesh 的顶点相对 SMR 变换，且 useScale=true 时
                // Unity 已把 SMR 的缩放补偿掉（烘焙网格=原始尺寸），所以再乘完整 localToWorldMatrix
                // 正好得到世界坐标，不会二次缩放。（Unity 2022.3/2023.2 文档：useScale 是
                // "compensate for the SkinnedMeshRenderer's Transform scale"；位置/旋转始终补偿到局部空间。）
                Matrix4x4 m = _bodySmr.transform.localToWorldMatrix;
                _bodyPos = new Vector3[_bodyCount];
                _bodyNrm = new Vector3[_bodyCount];
                for (int i = 0; i < _bodyCount; i++)
                {
                    _bodyPos[i] = m.MultiplyPoint3x4(localPos[i]);
                    Vector3 n = m.MultiplyVector(localNrm != null && localNrm.Length == _bodyCount ? localNrm[i] : Vector3.up);
                    _bodyNrm[i] = n.sqrMagnitude > DegenerateSqr ? n.normalized : Vector3.up;
                }
            }

            // ── 部位归类 + 被删除/不可见顶点排除 ─────────────────────
            void ComputeRegions()
            {
                int n = _bodyCount;
                _bodyRegion = new string[n];
                _bodyRegionSet = new HashSet<string>();
                _bodyExcluded = new bool[n];
                _exNanimated = _exNonFinite = _exZeroWeight = 0;
                Mesh mesh = _bodySmr.sharedMesh;
                int[] dom = null;
                string src = "none";
                float[] totalW = null;
                if (mesh != null) dom = DominantBones(mesh, n, out src, out totalW);
                bool fromWeights = dom != null;
                if (dom == null)
                {
                    dom = NearestBones(_bodySmr.bones, _bodyPos, n);
                    src = "nearest_bone";
                    _ctx.Warn("读不到蒙皮权重（网格可能未开 Read/Write），部位改用最近骨骼近似 —— 部位统计会变粗，仅作参考。");
                }
                _weightsSource = src;

                bool haveHips;
                Vector3 hips = HipsPosition(out haveHips);
                float farSqr = FarFromHipsM * FarFromHipsM;

                Transform[] bones = _bodySmr.bones;
                for (int i = 0; i < n; i++)
                {
                    int bi = dom[i];
                    Transform t = (bones != null && bi >= 0 && bi < bones.Length) ? bones[bi] : null;
                    string region = RegionOfBone(t);
                    _bodyRegion[i] = region;
                    _bodyRegionSet.Add(region);
                    RecordRegionExample(region, t != null ? t.name : "unknown");

                    // 排除判定，优先级：非有限坐标 > NaNimation 删除 > 权重为 0 / 离 Hips 过远。
                    // 为什么先判非有限：NaN 参与后面所有比较都没有意义，先剔除最省事。
                    Vector3 p = _bodyPos[i];
                    Vector3 nn = _bodyNrm[i];
                    if (!IsFinite(p) || !IsFinite(nn))
                    {
                        _bodyExcluded[i] = true;
                        _exNonFinite++;
                    }
                    else if (IsNanimatedBone(t))
                    {
                        // MA ShapeChanger 的 Delete 用 NaNimation 骨骼把「被删掉」的顶点移走；
                        // 主骨骼名或父链上带 NaNimat，运行时不显示，不能进统计。
                        _bodyExcluded[i] = true;
                        _exNanimated++;
                    }
                    else
                    {
                        // 「不可见」的两条来源：总权重为 0（没有骨骼驱动）；或被形态键/删除拉到极远处。
                        bool weightZero = fromWeights && totalW != null && totalW[i] <= 0f;
                        bool far = haveHips && (p - hips).sqrMagnitude > farSqr;
                        if (weightZero || far)
                        {
                            _bodyExcluded[i] = true;
                            _exZeroWeight++;
                        }
                    }
                }
                _bodyUsedCount = n - _exNanimated - _exNonFinite - _exZeroWeight;
            }

            Vector3 HipsPosition(out bool ok)
            {
                if (_anim != null)
                {
                    Transform hips = null;
                    try { hips = _anim.GetBoneTransform(HumanBodyBones.Hips); } catch { }
                    if (hips != null) { ok = true; return hips.position; }
                }
                if (_avatar != null) { ok = true; return _avatar.position; }
                ok = false;
                return Vector3.zero;
            }

            static bool IsFinite(Vector3 v)
            {
                return !float.IsNaN(v.x) && !float.IsInfinity(v.x)
                    && !float.IsNaN(v.y) && !float.IsInfinity(v.y)
                    && !float.IsNaN(v.z) && !float.IsInfinity(v.z);
            }

            // 优先用新 API（GetBonesPerVertex + GetAllBoneWeights，每个顶点内已按权重降序）；
            // 退回 legacy Mesh.boneWeights；都拿不到返回 null，由 NearestBones 兜底。
            // totalWeight 与 dom 同长：每个顶点的权重之和，用于识别「没有骨骼驱动」的不可见顶点。
            int[] DominantBones(Mesh mesh, int vertexCount, out string source, out float[] totalWeight)
            {
                source = "none";
                totalWeight = null;
                try
                {
                    NativeArray<byte> bpv = mesh.GetBonesPerVertex();
                    if (bpv.Length == vertexCount && vertexCount > 0)
                    {
                        NativeArray<BoneWeight1> bw = mesh.GetAllBoneWeights();
                        if (bw.Length > 0)
                        {
                            int[] res = new int[vertexCount];
                            float[] tot = new float[vertexCount];
                            int k = 0;
                            for (int i = 0; i < vertexCount; i++)
                            {
                                int c = bpv[i];
                                int bestBone = -1; float bestW = -1f; float sum = 0f;
                                for (int j = 0; j < c; j++)
                                {
                                    if (k >= bw.Length) break;
                                    BoneWeight1 w = bw[k++];
                                    sum += w.weight;
                                    if (w.weight > bestW) { bestW = w.weight; bestBone = w.boneIndex; }
                                }
                                res[i] = bestBone;
                                tot[i] = sum;
                            }
                            source = "bone_weights";
                            totalWeight = tot;
                            return res;
                        }
                    }
                }
                catch (Exception e) { _ctx.Warn("GetAllBoneWeights 不可用: " + e.Message); }

                try
                {
                    BoneWeight[] bw = mesh.boneWeights;
                    if (bw != null && bw.Length == vertexCount && vertexCount > 0)
                    {
                        int[] res = new int[vertexCount];
                        float[] tot = new float[vertexCount];
                        for (int i = 0; i < vertexCount; i++)
                        {
                            BoneWeight w = bw[i];
                            int b = w.boneIndex0; float m = w.weight0;
                            if (w.weight1 > m) { m = w.weight1; b = w.boneIndex1; }
                            if (w.weight2 > m) { m = w.weight2; b = w.boneIndex2; }
                            if (w.weight3 > m) { m = w.weight3; b = w.boneIndex3; }
                            res[i] = b;
                            tot[i] = w.weight0 + w.weight1 + w.weight2 + w.weight3;
                        }
                        source = "bone_weights_legacy";
                        totalWeight = tot;
                        return res;
                    }
                }
                catch (Exception e) { _ctx.Warn("Mesh.boneWeights 不可用: " + e.Message); }
                return null;
            }

            int[] NearestBones(Transform[] bones, Vector3[] pos, int n)
            {
                int[] res = new int[n];
                if (bones == null || bones.Length == 0) { for (int i = 0; i < n; i++) res[i] = -1; return res; }
                Vector3[] bp = new Vector3[bones.Length];
                bool[] ok = new bool[bones.Length];
                for (int b = 0; b < bones.Length; b++)
                {
                    ok[b] = bones[b] != null;
                    if (ok[b]) bp[b] = bones[b].position;
                }
                for (int i = 0; i < n; i++)
                {
                    int best = -1; float bd = float.MaxValue;
                    Vector3 p = pos[i];
                    for (int b = 0; b < bones.Length; b++)
                    {
                        if (!ok[b]) continue;
                        float d = (bp[b] - p).sqrMagnitude;
                        if (d < bd) { bd = d; best = b; }
                    }
                    res[i] = best;
                }
                return res;
            }

            void PrepareFootIndices()
            {
                _footVertIdx = new List<int>[] { new List<int>(), new List<int>() };
                _footSoleIdx = new List<int>[] { new List<int>(), new List<int>() };
                for (int i = 0; i < _bodyCount; i++)
                {
                    if (_bodyExcluded[i]) continue;   // 被删除/不可见的脚部顶点不进脚部专项
                    int side = RegionSide(_bodyRegion[i]);
                    if (side < 0) continue;
                    _footVertIdx[side].Add(i);
                    // 只有朝下的面（脚底）才谈得上「悬空 / 穿底」——法线朝上的脚背顶点量的是鞋面，不是鞋底。
                    if (_bodyNrm[i].y < -0.5f) _footSoleIdx[side].Add(i);
                }
            }

            // ── v2：身体临时 MeshCollider（薄部位误报的判据基础）──────
            // 为什么：内向射线打在 <pierce_mm 的薄身体部位（脚趾/手指/手腕）上，会穿出身体、
            // 打到对侧衣物的内表面；那个面法线朝身体内部、与射线方向相反，旧代码把它当成
            // 「衣物正面在顶点里面 = 已穿出」。有了身体碰撞体就能问「射线是不是先穿出了身体」。
            // 碰撞体用烘焙世界坐标；被排除顶点的三角面不参与（它们不在原位，且常伴随 NaN / 极远坐标）。
            void BuildBodyCollider()
            {
                int[] srcTris = null;
                try { srcTris = _bodyBaked != null ? _bodyBaked.triangles : null; }
                catch (Exception e) { _ctx.Warn("读身体烘焙三角面失败，薄壁判定跳过: " + e.Message); return; }
                if (srcTris == null || srcTris.Length < 3) { _ctx.Warn("身体烘焙网格没有三角面，薄壁判定跳过"); return; }

                List<int> tris = new List<int>(srcTris.Length);
                for (int k = 0; k + 2 < srcTris.Length; k += 3)
                {
                    int a = srcTris[k], b = srcTris[k + 1], c = srcTris[k + 2];
                    if (a < 0 || b < 0 || c < 0 || a >= _bodyCount || b >= _bodyCount || c >= _bodyCount) continue;
                    if (_bodyExcluded[a] || _bodyExcluded[b] || _bodyExcluded[c]) continue;
                    tris.Add(a); tris.Add(b); tris.Add(c);
                }
                if (tris.Count < 3) { _ctx.Warn("排除被删除顶点后身体没有可用三角面，薄壁判定跳过"); return; }

                // 顶点数组整体拷一份并清掉非有限值：三角面已不引用被排除顶点，
                // 但 MeshCollider 烘 bounds 时若读到 NaN 会失败/报错。
                Vector3[] vv = new Vector3[_bodyCount];
                Vector3[] vn = new Vector3[_bodyCount];
                for (int i = 0; i < _bodyCount; i++)
                {
                    vv[i] = (_bodyExcluded[i] || !IsFinite(_bodyPos[i])) ? Vector3.zero : _bodyPos[i];
                    vn[i] = (_bodyExcluded[i] || !IsFinite(_bodyNrm[i])) ? Vector3.up : _bodyNrm[i];
                }

                Mesh cm = new Mesh();
                cm.indexFormat = IndexFormat.UInt32;
                cm.hideFlags = HideFlags.HideAndDontSave;
                cm.vertices = vv;
                cm.normals = vn;
                cm.triangles = tris.ToArray();
                cm.RecalculateBounds();

                GameObject go = new GameObject("__AuditFitProbe_bodycol__");
                go.hideFlags = HideFlags.HideAndDontSave;
                go.layer = BodyLayer;
                go.transform.position = Vector3.zero;
                go.transform.rotation = Quaternion.identity;
                go.transform.localScale = Vector3.one;
                MeshCollider mc = go.AddComponent<MeshCollider>();
                mc.sharedMesh = cm;
                mc.convex = false;
                mc.enabled = true;
                Physics.SyncTransforms();

                _bodyColliderMesh = cm;
                _bodyColliderGo = go;
                _bodyCollider = mc;
            }

            // ── 烘焙衣物 + 建临时碰撞体 ──────────────────────────────
            void BakeGarments()
            {
                for (int gi = 0; gi < _garments.Count; gi++)
                {
                    Garment g = _garments[gi];
                    if (g.renderer == null || !g.renderer.enabled || !g.renderer.gameObject.activeInHierarchy)
                    {
                        g.skipped = true;
                        g.skipReason = "renderer 不可见（含 hide 自检）";
                        continue;
                    }
                    Vector3[] pos, nrm; int[] tris; string err;
                    if (!TryGetWorldMesh(g.renderer, out pos, out nrm, out tris, out err))
                    {
                        g.skipped = true;
                        g.skipReason = err;
                        continue;
                    }
                    g.pos = pos; g.tris = tris; g.vertexCount = pos.Length;

                    // v3：用这件衣物自己的蒙皮权重算「它覆盖哪些部位」，供覆盖范围过滤。
                    ComputeGarmentRegion(g);

                    // 碰撞体网格：顶点已是世界坐标，所以临时物体自身保持单位变换。
                    Mesh cm = new Mesh();
                    cm.indexFormat = IndexFormat.UInt32;
                    cm.hideFlags = HideFlags.HideAndDontSave;
                    cm.vertices = pos;
                    cm.normals = nrm;
                    cm.triangles = tris;
                    cm.RecalculateBounds();

                    string goName = "__AuditFitProbe_col_" + AuditUtil.SafeFileName(g.path);
                    if (goName.Length > 120) goName = goName.Substring(goName.Length - 120);   // 路径可能很深，避免超长名字
                    GameObject go = new GameObject(goName);
                    go.hideFlags = HideFlags.HideAndDontSave;   // 不进层级、不随场景保存
                    go.layer = TempLayer;
                    go.transform.position = Vector3.zero;
                    go.transform.rotation = Quaternion.identity;
                    go.transform.localScale = Vector3.one;
                    MeshCollider mc = go.AddComponent<MeshCollider>();
                    mc.sharedMesh = cm;
                    mc.convex = false;                          // 非凸才能贴合凹形衣物
                    mc.enabled = false;                         // 一次只启用一件

                    g.colliderMesh = cm;
                    g.colliderGo = go;
                    g.collider = mc;
                }
            }

            bool TryGetWorldMesh(Renderer r, out Vector3[] pos, out Vector3[] nrm, out int[] tris, out string err)
            {
                pos = null; nrm = null; tris = null; err = null;
                Mesh src = null; bool temp = false;
                Matrix4x4 m = r.transform.localToWorldMatrix;
                SkinnedMeshRenderer smr = r as SkinnedMeshRenderer;
                if (smr != null)
                {
                    if (smr.sharedMesh == null) { err = "sharedMesh 为空"; return false; }
                    Mesh baked = new Mesh();
                    baked.indexFormat = IndexFormat.UInt32;
                    baked.hideFlags = HideFlags.HideAndDontSave;
                    try { smr.BakeMesh(baked, true); }
                    catch (Exception e) { Object.DestroyImmediate(baked); err = "BakeMesh 失败: " + e.Message; return false; }
                    src = baked; temp = true;
                }
                else
                {
                    MeshFilter mf = r.GetComponent<MeshFilter>();
                    if (mf == null || mf.sharedMesh == null) { err = "MeshFilter/sharedMesh 为空"; return false; }
                    if (!mf.sharedMesh.isReadable) { err = "mesh 未开 Read/Write，无法建碰撞体"; return false; }
                    src = mf.sharedMesh;
                }

                try
                {
                    Vector3[] v = src.vertices;
                    if (v == null || v.Length == 0) { err = "顶点为空"; return false; }
                    Vector3[] nn = src.normals;
                    if (nn == null || nn.Length != v.Length)
                    {
                        // 法线缺失：拷一份重算法线（不能污染原网格）
                        Mesh cp = new Mesh();
                        cp.indexFormat = IndexFormat.UInt32;
                        cp.hideFlags = HideFlags.HideAndDontSave;
                        cp.vertices = v;
                        cp.RecalculateNormals();
                        nn = cp.normals;
                        Object.DestroyImmediate(cp);
                    }
                    int[] tt = src.triangles;
                    if (tt == null || tt.Length < 3) { err = "三角面为空"; return false; }

                    int n = v.Length;
                    pos = new Vector3[n]; nrm = new Vector3[n];
                    for (int i = 0; i < n; i++)
                    {
                        pos[i] = m.MultiplyPoint3x4(v[i]);
                        Vector3 x = m.MultiplyVector(nn[i]);
                        nrm[i] = x.sqrMagnitude > DegenerateSqr ? x.normalized : Vector3.up;
                    }
                    tris = tt;
                    return true;
                }
                catch (Exception e)
                {
                    err = "读取网格失败: " + e.Message;
                    return false;
                }
                finally
                {
                    if (temp && src != null) Object.DestroyImmediate(src);
                }
            }

            // ── v3 覆盖范围：用衣物自身的蒙皮定「它覆盖哪些部位」────────────
            // 为什么用自己的蒙皮而不是公共包围盒：sailor 上衣的手部顶点占比为 0，但袖口几何
            // 会落在手的 25 mm 覆盖射程内，被误算成「手在衣服里」。衣物蒙皮的主骨骼集合才是
            // 「这件衣服设计上包住哪里」的直接证据。占比阈值 region_min_share 挡掉极少量杂散权重。
            //
            // regionSet == null 表示判定不了（MeshRenderer 无骨骼 / 网格未开 Read/Write），
            // 此时不限制范围（保持旧行为），输出 region_source 说明原因，便于核对。
            void ComputeGarmentRegion(Garment g)
            {
                g.regionSet = null;
                g.regionSource = "none";
                g.coverageRegions = null;

                Mesh mesh = MeshOf(g.renderer);
                if (mesh == null || mesh.vertexCount == 0) { g.regionSource = "no_mesh"; return; }
                Transform[] bones = null;
                SkinnedMeshRenderer smr = g.renderer as SkinnedMeshRenderer;
                if (smr != null) bones = smr.bones;
                if (bones == null || bones.Length == 0) { g.regionSource = "no_bones"; return; }

                string src; float[] tot;
                int[] dom = DominantBones(mesh, mesh.vertexCount, out src, out tot);
                if (dom == null) { g.regionSource = "unreadable_weights"; return; }

                Dictionary<string, int> counts = new Dictionary<string, int>();
                int total = 0;
                for (int i = 0; i < dom.Length; i++)
                {
                    int bi = dom[i];
                    Transform t = (bi >= 0 && bi < bones.Length) ? bones[bi] : null;
                    string reg = RegionOfBone(t);
                    if (string.IsNullOrEmpty(reg)) reg = "Other";
                    int c;
                    counts.TryGetValue(reg, out c);
                    counts[reg] = c + 1;
                    total++;
                }
                if (total == 0) { g.regionSource = "no_vertices"; return; }

                List<RegionShare> list = new List<RegionShare>();
                HashSet<string> set = new HashSet<string>();
                foreach (KeyValuePair<string, int> kv in counts)
                {
                    RegionShare rs = new RegionShare();
                    rs.region = kv.Key;
                    rs.count = kv.Value;
                    rs.share = (float)kv.Value / total;
                    list.Add(rs);
                    if (rs.share >= _regionMinShare) set.Add(kv.Key);
                }
                list.Sort((a, b) => string.CompareOrdinal(a.region, b.region));
                g.coverageRegions = list;
                if (set.Count == 0)
                {
                    // 部位太碎（每块都 < 阈值）时退回「所有出现过的部位」，避免整件衣物变成空范围。
                    for (int i = 0; i < list.Count; i++) set.Add(list[i].region);
                    _ctx.Warn("衣物 " + g.path + " 没有任何部位的主骨骼占比 ≥ region_min_share，已退回全部出现过的部位");
                }

                // 交叉校验：衣物部位与身体部位完全不相交，说明两者的父链映射对不上（例如衣物自带
                // 一套骨架），此时按范围过滤会把整件衣物清零。宁可退回不限制，并在 warnings 里点名。
                if (_bodyRegionSet != null && _bodyRegionSet.Count > 0)
                {
                    bool any = false;
                    foreach (string r in set) { if (_bodyRegionSet.Contains(r)) { any = true; break; } }
                    if (!any)
                    {
                        g.regionSet = null;
                        g.regionSource = "map_mismatch";
                        _ctx.Warn("衣物 " + g.path + " 的部位集合与身体部位无交集（父链映射可能对不上），已取消范围限制");
                        return;
                    }
                }
                g.regionSet = set;
                g.regionSource = src;
            }

            // ── 主探测：逐件衣物对身体顶点打射线 ────────────────────
            // 身体射线只建一次；身体命中也只算一次（整轮身体碰撞体几何不变）。
            void BuildBodyRaysAndHits()
            {
                int n = _bodyCount;
                int count = Mathf.Max(1, n * 2);
                _rayO = new Vector3[count];
                _rayD = new Vector3[count];
                _rayDist = new float[count];
                for (int i = 0; i < n; i++)
                {
                    if (_bodyExcluded[i])
                    {
                        // 被排除顶点的坐标可能是 NaN/极远值：不给射线批处理，距离 0 保证必然未命中。
                        _rayO[2 * i] = Vector3.zero; _rayD[2 * i] = Vector3.up; _rayDist[2 * i] = 0f;
                        _rayO[2 * i + 1] = Vector3.zero; _rayD[2 * i + 1] = Vector3.up; _rayDist[2 * i + 1] = 0f;
                        continue;
                    }
                    Vector3 v = _bodyPos[i];
                    Vector3 nn = _bodyNrm[i];
                    // 外向：从身体表面外 0.5mm 沿法线出去，打到衣物背面=身体在衣物里面
                    _rayO[2 * i] = v + nn * RayOffsetM;
                    _rayD[2 * i] = nn;
                    _rayDist[2 * i] = _coverMm * 0.001f;
                    // 内向：从身体表面里 0.5mm 沿反法线进去，打到衣物正面=衣物表面在顶点里面=顶点已穿出
                    _rayO[2 * i + 1] = v - nn * RayOffsetM;
                    _rayD[2 * i + 1] = -nn;
                    _rayDist[2 * i + 1] = _pierceMm * 0.001f;
                }
                _bodyHits = _rays.Shoot(_rayO, _rayD, _rayDist, count, 1 << BodyLayer, true);
            }

            /// <summary>衣物命中之前是否先命中了身体网格。&lt;=0.5mm 的算起点自命中，忽略。
            /// 这正是否掉「内向射线穿出薄部位、打到对侧衣物内表面」的关键。</summary>
            static bool BodyBlocks(RaycastHit hit, float garmentDistance)
            {
                if (hit.collider == null) return false;
                if (hit.distance <= RayOffsetM) return false;   // 自命中
                return hit.distance < garmentDistance;
            }

            // ── 主探测：逐件衣物对身体顶点打射线 ────────────────────
            void RunProbes()
            {
                int n = _bodyCount;
                BuildBodyRaysAndHits();

                for (int gi = 0; gi < _garments.Count; gi++)
                {
                    Garment g = _garments[gi];
                    if (g.collider == null)
                    {
                        _done = gi + 1;
                        _ctx.Status.Running((gi + 1) + "/" + _garments.Count, g.path + " [skip]");
                        continue;
                    }

                    g.collider.enabled = true;
                    Physics.SyncTransforms();

                    int count = n * 2;
                    RaycastHit[] hits = _rays.Shoot(_rayO, _rayD, _rayDist, count, 1 << TempLayer, true);

                    g.pierced = new bool[n];
                    g.depth = new float[n];
                    g.gap = new float[n];
                    for (int i = 0; i < n; i++) g.gap[i] = -1f;   // -1 = 该顶点没有被这件衣物包住（无间隙数据）
                    for (int i = 0; i < n; i++)
                    {
                        if (_bodyExcluded[i]) continue;

                        bool coveredInside = false;
                        bool pierced = false;
                        float depthMm = 0f;
                        bool rejectBody = false, rejectNormal = false;

                        RaycastHit ho = hits[2 * i];
                        if (ho.collider != null && IsBackface(_rayD[2 * i], ho, g.pos, g.tris))
                        {
                            // 打到衣物背面 => 该身体顶点被衣物包在里面；但若先穿出身体，就是对侧衣物，不算。
                            if (BodyBlocks(_bodyHits[2 * i], ho.distance)) rejectBody = true;
                            else coveredInside = true;
                        }

                        RaycastHit hi = hits[2 * i + 1];
                        if (hi.collider != null && !IsBackface(_rayD[2 * i + 1], hi, g.pos, g.tris))
                        {
                            // 打到衣物正面 => 衣物表面在身体顶点内侧 => 顶点穿出
                            if (BodyBlocks(_bodyHits[2 * i + 1], hi.distance)) rejectBody = true;
                            else if (Vector3.Dot(SurfaceNormal(hi, g.pos, g.tris), _bodyNrm[i]) <= 0f)
                                rejectNormal = true;   // 衣物法线与身体顶点法线反向 = 对侧内表面
                            else
                            {
                                float mm = (hi.distance + RayOffsetM) * 1000f;   // 从身体顶点量起，补回起点偏移
                                if (mm >= _minDepthMm) { pierced = true; depthMm = mm; }
                            }
                        }

                        string region = _bodyRegion[i];

                        // v3 覆盖范围：这件衣物的蒙皮覆盖不到该部位 → 命中不算 covered/pierced。
                        // 计数保留在 out_of_scope，便于核对「少掉的那些是不是本条挡的」。
                        if (g.regionSet != null && !g.regionSet.Contains(region))
                        {
                            if (coveredInside || pierced)
                            {
                                Stat ost = GetStat(g.regions, region);
                                ost.outOfScope++;
                                g.total.outOfScope++;
                            }
                            continue;
                        }

                        // 拒绝计数独立于覆盖区：它们解释的是「为什么这个顶点没被算成 covered/pierced」。
                        if (rejectBody || rejectNormal)
                        {
                            Stat rst = GetStat(g.regions, region);
                            if (rejectBody) { rst.rejectedThroughBody++; g.total.rejectedThroughBody++; }
                            if (rejectNormal) { rst.rejectedOppositeNormal++; g.total.rejectedOppositeNormal++; }
                        }

                        if (!coveredInside && !pierced) continue;   // 覆盖区之外不统计

                        g.pierced[i] = pierced;
                        g.depth[i] = depthMm;
                        if (coveredInside) g.gap[i] = (ho.distance + RayOffsetM) * 1000f;   // 身体表面到衣物内表面的间隙

                        Stat st = GetStat(g.regions, region);
                        st.coverage++;
                        if (coveredInside) st.covered++;
                        if (pierced) { st.pierced++; st.depths.Add(depthMm); }

                        g.total.coverage++;
                        if (coveredInside) g.total.covered++;
                        if (pierced) { g.total.pierced++; g.total.depths.Add(depthMm); }

                        int side = RegionSide(region);
                        if (side >= 0) g.footCoverage[side]++;

                        if (pierced)
                            _markers.Add(new Marker
                            {
                                pos = _bodyPos[i],
                                region = region,
                                garment = g.path,
                                depth = depthMm,
                                vertex = i
                            });
                    }

                    // 鞋底专项射线：只对脚底（法线朝下）顶点，向下找鞋内底正面、向上找鞋底背面。
                    // 这里对每件衣物都算一遍（脚底顶点只有几百个，代价可忽略），BuildFeet 里再按
                    // 「每只脚 × 每件覆盖该脚的衣物」取用；v3 另算脚底下方厚度用于分鞋/袜。
                    if (_footEnabled)
                    {
                        for (int side = 0; side < 2; side++)
                        {
                            ProbeFootRays(g, side);
                            ProbeFootThickness(g, side);
                        }
                    }

                    g.collider.enabled = false;
                    Physics.SyncTransforms();
                    _done = gi + 1;
                    _ctx.Status.Running((gi + 1) + "/" + _garments.Count, g.path);
                }
            }

            void ProbeFootRays(Garment g, int side)
            {
                List<int> idx = _footSoleIdx[side];
                if (idx == null || idx.Count == 0) { g.footSigned[side] = new float[0]; return; }
                int c = idx.Count;
                g.footSigned[side] = new float[c];
                Vector3[] downO = new Vector3[c];
                Vector3[] downD = new Vector3[c];
                float[] downL = new float[c];
                Vector3[] upO = new Vector3[c];
                Vector3[] upD = new Vector3[c];
                float[] upL = new float[c];
                float probe = _footProbeMm * 0.001f;
                for (int k = 0; k < c; k++)
                {
                    Vector3 v = _bodyPos[idx[k]];
                    downO[k] = v; downD[k] = Vector3.down; downL[k] = probe;
                    upO[k] = v; upD[k] = Vector3.up; upL[k] = probe;
                }
                RaycastHit[] dh = _rays.Shoot(downO, downD, downL, c, 1 << TempLayer, true);
                RaycastHit[] uh = _rays.Shoot(upO, upD, upL, c, 1 << TempLayer, true);
                for (int k = 0; k < c; k++)
                {
                    float signed = float.NaN;
                    // 向下打到鞋内底（正面，法线朝上）=> 身体脚底在内底之上 => 悬空，记正
                    RaycastHit hd = dh[k];
                    if (hd.collider != null)
                    {
                        Vector3 fn = FaceNormal(g.pos, g.tris, hd);
                        if (fn.y > 0f && !IsBackface(Vector3.down, hd, g.pos, g.tris))
                            signed = (hd.distance + RayOffsetM) * 1000f;
                    }
                    // 向下没打到内底、向上却打到内底的背面 => 身体脚底在内底之下 => 穿底，记负
                    if (float.IsNaN(signed))
                    {
                        RaycastHit hu = uh[k];
                        if (hu.collider != null)
                        {
                            Vector3 fn = FaceNormal(g.pos, g.tris, hu);
                            if (fn.y > 0f && IsBackface(Vector3.up, hu, g.pos, g.tris))
                                signed = -(hu.distance + RayOffsetM) * 1000f;
                        }
                    }
                    g.footSigned[side][k] = signed;
                }
            }

            // ── v3 脚底下方厚度：区分鞋（厚）与袜（贴身）的几何依据 ─────────
            // 定义（与任务书一致）：沿 -up 从脚底顶点打到衣物，第一次与最后一次命中的距离。
            // 实现说明：`Physics.RaycastNonAlloc` 一次拿回该射线上的全部命中（用同一件衣物
            // 的 MeshCollider，逐件启用，故只会命中它），按最近/最远两点算厚度，等价于「第一次
            // 与最后一次」。个别引擎/网格只回一条命中时，补一条「从脚底下方 probe_mm 处向上」
            // 的射线取鞋外底高度，再减掉向下第一次命中的内底距离，得到同一厚度。
            // 这里用非分配重载；命中顺序不作假设，自己取 min/max。
            void ProbeFootThickness(Garment g, int side)
            {
                g.footThicknessCount[side] = 0;
                g.footThicknessP50[side] = float.NaN;
                List<int> idx = _footSoleIdx[side];
                if (idx == null || idx.Count == 0) return;

                float probe = _footProbeMm * 0.001f;
                int mask = 1 << TempLayer;
                List<float> vals = new List<float>(idx.Count);
                for (int k = 0; k < idx.Count; k++)
                {
                    Vector3 v = _bodyPos[idx[k]];
                    float dInner, dOuter;
                    int c = Physics.RaycastNonAlloc(v, Vector3.down, _thickBuf, probe, mask, QueryTriggerInteraction.Ignore);
                    if (c <= 0) continue;
                    dInner = float.MaxValue;
                    float dLast = float.MinValue;
                    for (int j = 0; j < c; j++)
                    {
                        float d = _thickBuf[j].distance;
                        if (d < dInner) dInner = d;
                        if (d > dLast) dLast = d;
                    }
                    float thickness;
                    if (c >= 2)
                    {
                        thickness = dLast - dInner;
                    }
                    else
                    {
                        // 只回一条：从脚底下方往正上方打，第一条命中即衣物外底。
                        Vector3 below = v + Vector3.down * probe;
                        int c2 = Physics.RaycastNonAlloc(below, Vector3.up, _thickBuf, probe, mask, QueryTriggerInteraction.Ignore);
                        if (c2 <= 0) continue;
                        float upMin = float.MaxValue;
                        for (int j = 0; j < c2; j++)
                            if (_thickBuf[j].distance < upMin) upMin = _thickBuf[j].distance;
                        dOuter = probe - upMin;          // 脚底往下到衣物外底的距离
                        if (dOuter <= 0f) continue;
                        thickness = dOuter - dInner;
                    }
                    float thMm = thickness * 1000f;
                    // < 0.05 mm 视为「内外两层被算成同一面」的退化结果，不进统计（否则会把鞋误判成贴身袜）。
                    if (thMm > 0.05f && !float.IsNaN(thMm) && !float.IsInfinity(thMm)) vals.Add(thMm);
                }
                g.footThicknessCount[side] = vals.Count;
                g.footThicknessP50[side] = vals.Count > 0 ? Pctl(vals, 50f) : float.NaN;
            }

            // 正面/背面判定。hit.normal 可用时用它的符号（与任务书一致）；
            // 标定发现 Unity 把背面法线翻向射线时，改用我们自己由三角形 winding 算的法线，
            // 并按 _windingSign 校正叉乘方向。这样无论版本约定如何，判据都不会反。
            bool IsBackface(Vector3 rayDir, RaycastHit h, Vector3[] verts, int[] tris)
            {
                return Vector3.Dot(rayDir, SurfaceNormal(h, verts, tris)) > 0f;
            }

            /// <summary>命中面的「外法线」（与正面同向）。_hitNormalUsable 时直接信 h.normal，
            /// 否则用 winding 法线乘标定出来的 _windingSign。</summary>
            Vector3 SurfaceNormal(RaycastHit h, Vector3[] verts, int[] tris)
            {
                if (_hitNormalUsable) return h.normal;
                return _windingSign * FaceNormal(verts, tris, h);
            }

            static Vector3 FaceNormal(Vector3[] verts, int[] tris, RaycastHit h)
            {
                int tri = h.triangleIndex;
                if (verts != null && tris != null && tri >= 0 && tri * 3 + 2 < tris.Length)
                {
                    Vector3 a = verts[tris[tri * 3]];
                    Vector3 b = verts[tris[tri * 3 + 1]];
                    Vector3 c = verts[tris[tri * 3 + 2]];
                    Vector3 n = Vector3.Cross(b - a, c - a);
                    if (n.sqrMagnitude > DegenerateSqr) return n.normalized;
                }
                return h.normal;
            }

            // ── 脚部汇总（v3：每只脚 × 每件覆盖该脚的衣物，先分类再选指标）──
            void BuildFeet()
            {
                Dictionary<string, float> shapeKeys = FootShapeKeys();
                for (int side = 0; side < 2; side++)
                {
                    string sideName = side == 0 ? "Left" : "Right";
                    int emitted = 0;
                    for (int gi = 0; gi < _garments.Count; gi++)
                    {
                        Garment g = _garments[gi];
                        if (g.collider == null) continue;
                        if (!GarmentCoversFoot(g, side)) continue;
                        emitted++;

                        FootResult fr = new FootResult();
                        fr.side = sideName;
                        fr.shapeKeys = shapeKeys;
                        fr.footVerts = _footVertIdx[side].Count;
                        fr.soleVerts = _footSoleIdx[side].Count;
                        fr.garmentPath = g.path;
                        fr.thicknessP50 = g.footThicknessP50[side];
                        fr.thicknessCount = g.footThicknessCount[side];
                        ClassifyFoot(g, side, fr);

                        if (fr.klass == ClassFootwear) FillFootwearMetrics(g, side, fr);
                        else FillLegwearMetrics(g, side, fr);

                        _feet.Add(fr);
                    }
                    if (emitted == 0)
                        _ctx.Warn("没有衣物覆盖 " + sideName + " 脚（该侧 foot 部位不在任何衣物的覆盖部位集合里），跳过鞋袜贴合判定");
                }
            }

            /// <summary>这件衣物的蒙皮是否覆盖该侧脚。regionSet==null（判不了）时退回旧的
            /// footCoverage 口径，保持可用。</summary>
            bool GarmentCoversFoot(Garment g, int side)
            {
                if (g.regionSet == null) return g.footCoverage[side] > 0;
                string a = side == 0 ? "LeftFoot" : "RightFoot";
                string b = side == 0 ? "LeftToes" : "RightToes";
                return g.regionSet.Contains(a) || g.regionSet.Contains(b);
            }

            /// <summary>分类优先级：请求显式（foot.footwear / foot.legwear）> 几何厚度 > 名称关键词。
            /// 几何厚度在 [2mm, sole_min_mm) 之间时几何不表态，落到名称兜底。</summary>
            void ClassifyFoot(Garment g, int side, FootResult fr)
            {
                string leaf = LeafName(g.path);
                if (_footwearPaths.Contains(g.path) || _footwearLeaves.Contains(leaf))
                {
                    fr.klass = ClassFootwear; fr.classSource = "request";
                    fr.classDetail = "foot.footwear 显式列出";
                    return;
                }
                if (_legwearPaths.Contains(g.path) || _legwearLeaves.Contains(leaf))
                {
                    fr.klass = ClassLegwear; fr.classSource = "request";
                    fr.classDetail = "foot.legwear 显式列出";
                    return;
                }

                float th = g.footThicknessP50[side];
                if (!float.IsNaN(th))
                {
                    if (th >= _soleMinMm)
                    {
                        fr.klass = ClassFootwear; fr.classSource = "geometry";
                        fr.classDetail = "脚底下方厚度 p50 >= sole_min_mm";
                        return;
                    }
                    if (th < LegwearMaxMm)
                    {
                        fr.klass = ClassLegwear; fr.classSource = "geometry";
                        fr.classDetail = "脚底下方厚度 p50 < 2mm（贴身）";
                        return;
                    }
                }

                if (_footwearNameRe.IsMatch(g.path))
                {
                    fr.klass = ClassFootwear; fr.classSource = "name";
                    fr.classDetail = "路径含鞋类关键词";
                    return;
                }
                if (_legwearNameRe.IsMatch(g.path))
                {
                    fr.klass = ClassLegwear; fr.classSource = "name";
                    fr.classDetail = "路径含袜类关键词";
                    return;
                }
                fr.klass = ClassOther; fr.classSource = "default";
                fr.classDetail = float.IsNaN(th) ? "几何无数据且名称无关键词" : "厚度落在 2mm 与 sole_min_mm 之间，几何不表态且名称无关键词";
            }

            // footwear：保留原有的「脚底到鞋内底有向距离 + 脚跟 + 脚尖」。
            void FillFootwearMetrics(Garment g, int side, FootResult fr)
            {
                float[] arr = g.footSigned[side];
                List<float> vals = new List<float>();
                if (arr != null) for (int k = 0; k < arr.Length; k++) if (!float.IsNaN(arr[k])) vals.Add(arr[k]);
                fr.signedCount = vals.Count;
                float[] sorted = vals.ToArray();
                Array.Sort(sorted);
                fr.p05 = PctlSorted(sorted, 5f);
                fr.p50 = PctlSorted(sorted, 50f);
                fr.p95 = PctlSorted(sorted, 95f);
                for (int k = 0; k < sorted.Length; k++)
                {
                    if (sorted[k] < 0f) fr.belowSole++;
                    if (sorted[k] > 5f) fr.floating++;
                }

                // 脚跟 / 脚尖需要 Foot->Toes 连线定「前后」
                string sideName = side == 0 ? "Left" : "Right";
                Transform footT = _anim != null ? _anim.GetBoneTransform(side == 0 ? HumanBodyBones.LeftFoot : HumanBodyBones.RightFoot) : null;
                Transform toesT = _anim != null ? _anim.GetBoneTransform(side == 0 ? HumanBodyBones.LeftToes : HumanBodyBones.RightToes) : null;
                if (footT == null || toesT == null)
                {
                    _ctx.Warn("缺 " + sideName + " Foot/Toes 骨骼，跳过后跟/脚尖判定");
                    return;
                }
                Vector3 dir = toesT.position - footT.position;
                if (dir.sqrMagnitude <= 1e-8f)
                {
                    _ctx.Warn(sideName + " 脚 Foot 与 Toes 重合，脚方向退化，跳过后跟/脚尖判定");
                    return;
                }
                dir.Normalize();
                Vector3 org = footT.position;

                // 脚跟：沿脚方向投影最靠后的 10% 脚底顶点，取其有向距离 p50
                List<int> soleIdx = _footSoleIdx[side];
                var soleByProj = new List<KeyValuePair<float, int>>(soleIdx.Count);
                var soleSlot = new Dictionary<int, int>(soleIdx.Count);
                for (int k = 0; k < soleIdx.Count; k++)
                {
                    int i = soleIdx[k];
                    soleSlot[i] = k;
                    soleByProj.Add(new KeyValuePair<float, int>(Vector3.Dot(_bodyPos[i] - org, dir), i));
                }
                soleByProj.Sort((a, b) => a.Key.CompareTo(b.Key));
                int heelCount = Mathf.Max(1, Mathf.CeilToInt(0.10f * soleByProj.Count));
                if (heelCount > soleByProj.Count) heelCount = soleByProj.Count;
                List<float> heelVals = new List<float>();
                for (int k = 0; k < heelCount; k++)
                {
                    int i = soleByProj[k].Value;
                    int slot = soleSlot[i];
                    if (arr != null && slot < arr.Length && !float.IsNaN(arr[slot])) heelVals.Add(arr[slot]);
                }
                fr.heelCount = heelVals.Count;
                fr.heelP50 = Pctl(heelVals, 50f);

                // 脚尖：沿脚方向最靠前的 10% 脚部顶点，看它们是否被该鞋穿出（主探测的内向射线结果）
                List<int> fIdx = _footVertIdx[side];
                var footByProj = new List<KeyValuePair<float, int>>(fIdx.Count);
                for (int k = 0; k < fIdx.Count; k++)
                {
                    int i = fIdx[k];
                    footByProj.Add(new KeyValuePair<float, int>(Vector3.Dot(_bodyPos[i] - org, dir), i));
                }
                footByProj.Sort((a, b) => b.Key.CompareTo(a.Key));   // 降序，最前在前
                int toeCount = Mathf.Max(1, Mathf.CeilToInt(0.10f * footByProj.Count));
                if (toeCount > footByProj.Count) toeCount = footByProj.Count;
                fr.toeChecked = toeCount;
                for (int k = 0; k < toeCount; k++)
                {
                    int i = footByProj[k].Value;
                    if (g.pierced != null && i < g.pierced.Length && g.pierced[i]) fr.toePierced++;
                }
            }

            // legwear / other：不算鞋底有向距离（对贴身袜子无意义），只报穿出与平均间隙。
            // 平均间隙 = 该脚被这件衣物包住的顶点上，身体表面到衣物内表面的外向命中距离均值。
            void FillLegwearMetrics(Garment g, int side, FootResult fr)
            {
                List<int> fIdx = _footVertIdx[side];
                double gapSum = 0.0;
                for (int k = 0; k < fIdx.Count; k++)
                {
                    int i = fIdx[k];
                    bool pie = g.pierced != null && i < g.pierced.Length && g.pierced[i];
                    bool cov = g.gap != null && i < g.gap.Length && g.gap[i] >= 0f;
                    if (pie) fr.pierced++;
                    if (cov) { gapSum += g.gap[i]; fr.gapCount++; }
                    if (pie || cov) fr.coverage++;
                }
                fr.covered = fr.gapCount;
                fr.pierceRatio = fr.coverage > 0 ? (float)fr.pierced / fr.coverage : 0f;
                fr.gapAvg = fr.gapCount > 0 ? (float)(gapSum / fr.gapCount) : 0f;
            }

            static string LeafName(string path)
            {
                if (string.IsNullOrEmpty(path)) return "";
                int slash = path.LastIndexOf('/');
                return slash >= 0 && slash + 1 < path.Length ? path.Substring(slash + 1) : path;
            }

            Dictionary<string, float> FootShapeKeys()
            {
                Dictionary<string, float> d = new Dictionary<string, float>();
                Mesh m = _bodySmr != null ? _bodySmr.sharedMesh : null;
                if (m == null || _bodySmr == null) return d;
                int c = m.blendShapeCount;
                for (int i = 0; i < c; i++)
                {
                    string name = m.GetBlendShapeName(i);
                    if (!string.IsNullOrEmpty(name) && _footKeyRe.IsMatch(name))
                        d[name] = _bodySmr.GetBlendShapeWeight(i);
                }
                return d;
            }

            // ── 输出（复用 AuditIO 的 JsonObject，字段序 = 插入序，两次运行逐字节一致）──
            void WriteOutput(string path)
            {
                JsonObject root = new JsonObject();
                root.Set("avatar", _ctx.S("avatar"));
                root.Set("avatar_path", AuditUtil.ScenePath(_avatar));
                root.Set("state_id", _stateId);
                root.Set("body_path", _bodyPath);
                root.Set("body_vertex_count", _bodyCount);
                root.Set("body_vertex_used", _bodyUsedCount);
                root.Set("weights_source", _weightsSource);
                root.Set("mode", Application.isPlaying ? "play" : "edit");
                root.Set("ray_backend", _rays != null ? _rays.BackendUsed : "none");

                // v2：被删除/不可见顶点按原因计数（三桶相加 = body_vertex_count - body_vertex_used）
                JsonObject ex = new JsonObject();
                ex.Set("nanimated", _exNanimated);
                ex.Set("non_finite", _exNonFinite);
                ex.Set("zero_weight", _exZeroWeight);
                root.Set("excluded_vertices", ex);

                // v2：每个部位举最多 3 个原始骨骼名，用来核对父链映射没跑偏
                JsonObject examples = new JsonObject();
                List<string> exKeys = new List<string>(_regionExamples.Keys);
                exKeys.Sort(StringComparer.Ordinal);
                for (int i = 0; i < exKeys.Count; i++)
                    examples.Set(exKeys[i], new List<object>(_regionExamples[exKeys[i]].ToArray()));
                root.Set("region_bone_examples", examples);

                JsonObject calib = new JsonObject();
                calib.Set("hit_normal_usable", _hitNormalUsable);
                calib.Set("winding_sign", _windingSign);
                calib.Set("detail", _calibDetail);
                root.Set("calibration", calib);

                // params：请求原样（ctx.Request 就是解析后的请求对象，直接嵌进去）
                root.Set("params", _ctx.Request);

                // T-10：可选的 T-28a 穿出斑块块（请求 "poke" 时才有）。字段见 审查/docs/probe-poke.md（原 README §3.2.5）。
                if (_pokeJson != null) root.Set("poke", _pokeJson);

                var garments = new List<object>();
                for (int gi = 0; gi < _garments.Count; gi++)
                {
                    Garment g = _garments[gi];
                    JsonObject go = new JsonObject();
                    go.Set("path", g.path);
                    go.Set("material_names", new List<object>(g.materials));
                    go.Set("vertex_count", g.vertexCount);
                    go.Set("skipped", g.skipped);
                    go.Set("skip_reason", g.skipReason);
                    // v3：这件衣物的覆盖部位集合（由它自己的蒙皮权重得出），以及被排除的命中数
                    go.Set("region_source", g.regionSource);
                    go.Set("region_share_min", _regionMinShare);
                    go.Set("coverage_regions", RegionShareObjects(g.coverageRegions));
                    go.Set("total", StatObject(g.total));

                    List<string> keys = new List<string>(g.regions.Keys);
                    // 先按名字定序，再按 pierced 降序（List.Sort 稳定排序不保证，但同输入同结果）
                    keys.Sort(StringComparer.Ordinal);
                    keys.Sort((a, b) => g.regions[b].pierced.CompareTo(g.regions[a].pierced));
                    var regions = new List<object>();
                    for (int k = 0; k < keys.Count; k++)
                    {
                        Stat st = g.regions[keys[k]];
                        JsonObject ro = new JsonObject();
                        ro.Set("region", keys[k]);
                        ro.Set("covered", st.covered);
                        ro.Set("pierced", st.pierced);
                        ro.Set("coverage", st.coverage);
                        ro.Set("pierce_ratio", st.Ratio());
                        ro.Set("max_depth_mm", st.MaxDepth());
                        ro.Set("p95_depth_mm", st.P95());
                        ro.Set("depth_saturated", st.P95() >= _pierceMm * 0.9f);
                        ro.Set("rejected_through_body", st.rejectedThroughBody);
                        ro.Set("rejected_opposite_normal", st.rejectedOppositeNormal);
                        ro.Set("out_of_scope", st.outOfScope);
                        regions.Add(ro);
                    }
                    go.Set("regions", regions);
                    garments.Add(go);
                }
                root.Set("garments", garments);

                var feet = new List<object>();
                for (int i = 0; i < _feet.Count; i++)
                {
                    FootResult f = _feet[i];
                    JsonObject fo = new JsonObject();
                    fo.Set("side", f.side);
                    fo.Set("garment_path", f.garmentPath);
                    fo.Set("class", f.klass);
                    fo.Set("class_source", f.classSource);
                    fo.Set("class_detail", f.classDetail);
                    fo.Set("thickness_p50_mm", float.IsNaN(f.thicknessP50) ? (object)null : (object)f.thicknessP50);
                    fo.Set("thickness_count", f.thicknessCount);
                    fo.Set("foot_verts", f.footVerts);
                    fo.Set("sole_verts", f.soleVerts);
                    if (f.klass == ClassFootwear)
                    {
                        // 只有鞋才量「脚底到鞋内底」；袜/其它不算这套指标（对贴身衣物无意义）
                        JsonObject signed = new JsonObject();
                        signed.Set("p05", f.p05);
                        signed.Set("p50", f.p50);
                        signed.Set("p95", f.p95);
                        fo.Set("signed_mm", signed);
                        fo.Set("signed_count", f.signedCount);
                        fo.Set("below_sole", f.belowSole);
                        fo.Set("floating_gt5mm", f.floating);
                        fo.Set("heel_p50_mm", f.heelP50);
                        fo.Set("heel_count", f.heelCount);
                        fo.Set("toe_pierced", f.toePierced);
                        fo.Set("toe_checked", f.toeChecked);
                    }
                    else
                    {
                        // legwear / other：只报穿出与平均间隙
                        fo.Set("covered", f.covered);
                        fo.Set("pierced", f.pierced);
                        fo.Set("coverage", f.coverage);
                        fo.Set("pierce_ratio", f.pierceRatio);
                        fo.Set("gap_avg_mm", f.gapAvg);
                        fo.Set("gap_count", f.gapCount);
                    }
                    fo.Set("shape_keys", ShapeKeyObject(f.shapeKeys));
                    feet.Add(fo);
                }
                root.Set("feet", feet);

                var markers = new List<object>();
                List<Marker> ms = _markers != null ? _markers.Sorted() : new List<Marker>();
                for (int i = 0; i < ms.Count; i++)
                {
                    Marker mk = ms[i];
                    JsonObject mo = new JsonObject();
                    mo.Set("pos", new List<object> { mk.pos.x, mk.pos.y, mk.pos.z });
                    mo.Set("region", mk.region);
                    mo.Set("garment", mk.garment);
                    mo.Set("depth_mm", mk.depth);
                    mo.Set("vertex", mk.vertex);
                    markers.Add(mo);
                }
                root.Set("markers", markers);

                root.Set("body_candidates", BodyCandidateObjects());
                root.Set("warnings", new List<object>(_ctx.Warnings));

                JsonObject timings = new JsonObject();
                List<string> tkeys = new List<string>(_timings.Keys);
                tkeys.Sort(StringComparer.Ordinal);   // 排序保证两次运行输出逐字节一致
                for (int i = 0; i < tkeys.Count; i++) timings.Set(tkeys[i], _timings[tkeys[i]]);
                root.Set("timings_ms", timings);

                AuditJson.WriteFile(path, root);
            }

            JsonObject StatObject(Stat st)
            {
                JsonObject o = new JsonObject();
                o.Set("covered", st.covered);
                o.Set("pierced", st.pierced);
                o.Set("coverage", st.coverage);
                o.Set("pierce_ratio", st.Ratio());
                o.Set("max_depth_mm", st.MaxDepth());
                o.Set("p95_depth_mm", st.P95());
                o.Set("depth_saturated", st.P95() >= _pierceMm * 0.9f);
                o.Set("rejected_through_body", st.rejectedThroughBody);
                o.Set("rejected_opposite_normal", st.rejectedOppositeNormal);
                o.Set("out_of_scope", st.outOfScope);
                return o;
            }

            static List<object> RegionShareObjects(List<RegionShare> list)
            {
                List<object> outList = new List<object>();
                if (list == null) return outList;
                for (int i = 0; i < list.Count; i++)
                {
                    JsonObject o = new JsonObject();
                    o.Set("region", list[i].region);
                    o.Set("vertices", list[i].count);
                    o.Set("share", list[i].share);
                    outList.Add(o);
                }
                return outList;
            }

            List<object> BodyCandidateObjects()
            {
                List<object> list = new List<object>();
                for (int i = 0; i < _bodyCandidateInfo.Count; i++)
                {
                    BodyCandidate c = _bodyCandidateInfo[i];
                    JsonObject o = new JsonObject();
                    o.Set("path", c.path);
                    o.Set("vertex_count", c.vertices);
                    o.Set("has_foot", c.hasFoot);
                    o.Set("has_torso", c.hasTorso);
                    o.Set("selected", c.selected);
                    o.Set("regions", new List<object>(c.regions.ToArray()));
                    list.Add(o);
                }
                return list;
            }

            static JsonObject ShapeKeyObject(Dictionary<string, float> d)
            {
                JsonObject o = new JsonObject();
                if (d != null && d.Count > 0)
                {
                    List<string> keys = new List<string>(d.Keys);
                    keys.Sort(StringComparer.Ordinal);
                    for (int i = 0; i < keys.Count; i++) o.Set(keys[i], d[keys[i]]);
                }
                return o;
            }

            // ── 清理 / 恢复（幂等：Run 的 finally 与 AuditIO 的 Cleanup 都可能调）──
            public void Cleanup()
            {
                if (_cleaned) return;
                _cleaned = true;
                for (int i = _restores.Count - 1; i >= 0; i--)
                {
                    try { _restores[i](); } catch (Exception e) { Debug.LogWarning("[AuditFitProbe] 恢复失败: " + e.Message); }
                }
                _restores.Clear();
                DestroyTrash();
            }

            void DestroyTrash()
            {
                try
                {
                    for (int i = 0; i < _garments.Count; i++)
                    {
                        Garment g = _garments[i];
                        if (g.colliderGo != null) { _trash.Add(g.colliderGo); g.colliderGo = null; }
                        if (g.colliderMesh != null) { _trash.Add(g.colliderMesh); g.colliderMesh = null; }
                        g.collider = null;
                    }
                    if (_bodyBaked != null) { _trash.Add(_bodyBaked); _bodyBaked = null; }
                    if (_bodyColliderGo != null) { _trash.Add(_bodyColliderGo); _bodyColliderGo = null; }
                    if (_bodyColliderMesh != null) { _trash.Add(_bodyColliderMesh); _bodyColliderMesh = null; }
                    _bodyCollider = null;
                    for (int i = 0; i < _trash.Count; i++)
                        if (_trash[i] != null) Object.DestroyImmediate(_trash[i]);
                }
                catch (Exception e) { Debug.LogWarning("[AuditFitProbe] 清理异常: " + e.Message); }
                finally { _trash.Clear(); }
            }

            // ── 小工具 ──────────────────────────────────────────────
            static Stat GetStat(Dictionary<string, Stat> map, string region)
            {
                Stat st;
                if (!map.TryGetValue(region, out st)) { st = new Stat(); map[region] = st; }
                return st;
            }

            static int RegionSide(string region)
            {
                if (region == "LeftFoot" || region == "LeftToes") return 0;
                if (region == "RightFoot" || region == "RightToes") return 1;
                return -1;
            }

            static Mesh MeshOf(Renderer r)
            {
                SkinnedMeshRenderer smr = r as SkinnedMeshRenderer;
                if (smr != null) return smr.sharedMesh;
                MeshFilter mf = r.GetComponent<MeshFilter>();
                return mf != null ? mf.sharedMesh : null;
            }

            static string[] MaterialNames(Renderer r)
            {
                Material[] mats = r.sharedMaterials;
                if (mats == null) return new string[0];
                List<string> names = new List<string>(mats.Length);
                for (int i = 0; i < mats.Length; i++)
                    names.Add(mats[i] != null ? mats[i].name : "(null)");
                return names.ToArray();
            }

            Transform FindByPath(string path)
            {
                if (string.IsNullOrEmpty(path)) return null;
                if (path == ".") return _avatar;                    // AuditUtil.RelPath 里根节点记作 "."
                Transform direct = _avatar.Find(path);              // 相对头像根
                if (direct != null) return direct;
                Transform[] all = _avatar.GetComponentsInChildren<Transform>(true);
                for (int i = 0; i < all.Length; i++)
                {
                    Transform t = all[i];
                    if (AuditUtil.RelPath(_avatar, t) == path) return t;
                    if (AuditUtil.ScenePath(t) == path) return t;   // 也接受场景全路径
                }
                return null;
            }

            static float Pctl(List<float> vals, float p)
            {
                if (vals == null || vals.Count == 0) return 0f;
                float[] a = vals.ToArray();
                Array.Sort(a);
                return PctlSorted(a, p);
            }

            static float PctlSorted(float[] sorted, float p)
            {
                int n = sorted.Length;
                if (n == 0) return 0f;
                if (n == 1) return sorted[0];
                float idx = p / 100f * (n - 1);
                int lo = (int)Mathf.Floor(idx);
                int hi = (int)Mathf.Ceil(idx);
                if (lo < 0) lo = 0;
                if (hi >= n) hi = n - 1;
                return Mathf.Lerp(sorted[lo], sorted[hi], idx - lo);
            }

            // ── 数据结构 ────────────────────────────────────────────
            sealed class Garment
            {
                public Renderer renderer;
                public string path = "";
                public string[] materials = new string[0];
                public int vertexCount;
                public bool skipped;
                public string skipReason;
                public Mesh colliderMesh;
                public GameObject colliderGo;
                public MeshCollider collider;
                public Vector3[] pos;
                public int[] tris;
                public readonly Stat total = new Stat();
                public readonly Dictionary<string, Stat> regions = new Dictionary<string, Stat>();
                public bool[] pierced;
                public float[] depth;
                public float[] gap;                                   // v3：covered 顶点的身体→衣物内表面间隙（mm），-1=无
                public HashSet<string> regionSet;                     // v3：该衣物覆盖的部位；null=判不了（不限制）
                public string regionSource = "none";                  // v3：regionSet 的来源（bone_weights 等）
                public List<RegionShare> coverageRegions;             // v3：输出用，含占比
                public readonly int[] footCoverage = new int[2];
                public readonly float[][] footSigned = new float[2][];
                public readonly float[] footThicknessP50 = new float[2];   // v3：脚底下方厚度 p50（mm）
                public readonly int[] footThicknessCount = new int[2];     // v3：参与厚度统计的脚底顶点数
            }

            sealed class Stat
            {
                public int covered, pierced, coverage;
                // v2：被两条几何判据否掉的顶点数（不计入 coverage）
                public int rejectedThroughBody, rejectedOppositeNormal;
                // v3：命中但不在该衣物覆盖部位集合里、被排除出 covered/pierced 的顶点数
                public int outOfScope;
                public readonly List<float> depths = new List<float>();
                public float Ratio() { return coverage > 0 ? (float)pierced / coverage : 0f; }
                public float MaxDepth()
                {
                    float m = 0f;
                    for (int i = 0; i < depths.Count; i++) if (depths[i] > m) m = depths[i];
                    return m;
                }
                public float P95() { return Pctl(depths, 95f); }
            }

            sealed class BodyCandidate
            {
                public string path = "";
                public int vertices;
                public List<string> regions = new List<string>();
                public bool hasFoot;
                public bool hasTorso;
                public bool selected;
            }

            sealed class FootResult
            {
                public string side = "";
                public string garmentPath;
                // v3：footwear / legwear / other + 分类依据（request / geometry / name / default）
                public string klass = ClassOther;
                public string classSource = "default";
                public string classDetail = "";
                public float thicknessP50;
                public int thicknessCount;
                // footwear 指标
                public float p05, p50, p95;
                public int signedCount, belowSole, floating;
                public float heelP50;
                public int heelCount;
                public int toePierced, toeChecked;
                // legwear / other 指标
                public int covered, pierced, coverage;
                public float pierceRatio, gapAvg;
                public int gapCount;
                // 公共
                public int footVerts, soleVerts;
                public Dictionary<string, float> shapeKeys = new Dictionary<string, float>();
            }

            /// <summary>某部位在该衣物顶点里占的比例（用于输出核对；≥ region_min_share 的进 regionSet）。</summary>
            sealed class RegionShare
            {
                public string region = "";
                public int count;
                public float share;
            }

            struct Marker
            {
                public Vector3 pos;
                public string region;
                public string garment;
                public float depth;
                public int vertex;
            }

            /// <summary>按穿出深度保留前 N 个（用于 T3 打点）；深度小的淘汰，避免全量排序。</summary>
            sealed class TopK
            {
                readonly int _cap;
                readonly List<Marker> _list = new List<Marker>();
                public TopK(int cap) { _cap = Mathf.Max(1, cap); }
                public void Add(Marker m)
                {
                    if (_list.Count < _cap) { InsertSorted(m); return; }
                    if (m.depth <= _list[_list.Count - 1].depth) return;   // 列表降序，末尾最小
                    _list.RemoveAt(_list.Count - 1);
                    InsertSorted(m);
                }
                void InsertSorted(Marker m)
                {
                    int lo = 0, hi = _list.Count;
                    while (lo < hi)
                    {
                        int mid = (lo + hi) / 2;
                        if (_list[mid].depth >= m.depth) lo = mid + 1; else hi = mid;
                    }
                    _list.Insert(lo, m);
                }
                public List<Marker> Sorted() { return _list; }   // 已按 depth 降序
            }
        }

        // ─────────────────────────────────────────────────────────────
        // 射线批处理：优先 RaycastCommand.ScheduleBatch（Play 模式，2N 条一次提交），
        // 失败或非 Play 模式退回逐条 Physics.Raycast。返回的数组是本次调用的副本，
        // 调用方可以同时持有两份结果（脚底向上/向下各一份）。
        // ─────────────────────────────────────────────────────────────
        sealed class RayShooter
        {
            readonly AuditContext _ctx;
            bool _batchBroken;
            public string BackendUsed = "none";

            public RayShooter(AuditContext ctx) { _ctx = ctx; }

            public RaycastHit[] Shoot(Vector3[] origins, Vector3[] dirs, float[] dists, int count, int layerMask, bool hitBackfaces)
            {
                RaycastHit[] hits = new RaycastHit[count];
                if (count == 0) return hits;

                if (Application.isPlaying && !_batchBroken)
                {
                    NativeArray<RaycastCommand> commands = new NativeArray<RaycastCommand>(count, Allocator.TempJob);
                    NativeArray<RaycastHit> results = new NativeArray<RaycastHit>(count, Allocator.TempJob);
                    try
                    {
                        QueryParameters qp = new QueryParameters(layerMask, false, QueryTriggerInteraction.Ignore, hitBackfaces);
                        for (int i = 0; i < count; i++)
                            commands[i] = new RaycastCommand(origins[i], dirs[i], qp, dists[i]);
                        // minCommandsPerJob=32：每条命令很轻，太小会让调度开销占比过高
                        RaycastCommand.ScheduleBatch(commands, results, 32, default(JobHandle)).Complete();
                        for (int i = 0; i < count; i++) hits[i] = results[i];
                        BackendUsed = "raycast_command";
                        return hits;
                    }
                    catch (Exception e)
                    {
                        _batchBroken = true;
                        if (_ctx != null) _ctx.Warn("RaycastCommand 批处理不可用，退回 Physics.Raycast（会慢）: " + e.Message);
                    }
                    finally { commands.Dispose(); results.Dispose(); }
                }

                // 退回逐条：Physics.Raycast 读全局 queriesHitBackfaces，这里临时对齐再恢复
                bool saved = Physics.queriesHitBackfaces;
                Physics.queriesHitBackfaces = hitBackfaces;
                try
                {
                    for (int i = 0; i < count; i++)
                    {
                        RaycastHit h;
                        if (Physics.Raycast(origins[i], dirs[i], out h, dists[i], layerMask, QueryTriggerInteraction.Ignore))
                            hits[i] = h;
                        else
                            hits[i] = default(RaycastHit);
                    }
                }
                finally { Physics.queriesHitBackfaces = saved; }
                BackendUsed = "physics_raycast";
                return hits;
            }
        }
    }
}
