// ══════════════════════════════════════════════════════════════════
// 【通用工具】部件图鉴 · 逐部件拍照 + 部件清单
// 适用：任意 VRChat 人形头像工程（换单只改 `_交付/部件图鉴_配置.json`）
// 工具链：Unity 2022.3.22f1 / VRChat SDK 3.10.4 / Modular Avatar 1.17.1
// 可复用性：★★★ 配置驱动，不写死素体名与商品名（素体身体节点名走 bodyRoots，一套配置可跨多个头像根）
// 用途：
//   对配置里每套服装根下**每个 Renderer**（SkinnedMeshRenderer / MeshRenderer，含默认停用变体件）
//     ① 在身上单独看：只开这个部件＋素体身体；**场景里克隆之外的一切 Renderer/ParticleSystem 一律关**
//        （否则侧视正交相机会把克隆正后方那台原头像、乃至另一台在编辑的头像的玩偶/头发拍进来），
//        正/侧/背三视图 768²
//     ② 仅部件：身体也关，只留这个部件，正面 768²
//     ③ 整套有/无对比（都有/无同机位），两套取景各出一份：
//        · `整套-有/无-*`：按**部件包围盒取景**（扩到 ≥2.5 倍并并进相邻身体部位；再保证部件投影外接框 ≥5% 画幅）
//        · `整套全身-有/无-*`：保留原来的全身取景（H-02b 起从 `整套-*` 改名而来）
//        （部件重心在身体背面时补背面一套）
//   每张图左上角用 PIL 叠字：<商品名> / <Renderer 路径末两级> / <视图> / tris=<三角数> / mats=<材质名>
//   每套一份 `部件清单.json`：路径/网格/三角/材质+主贴图/默认 activeSelf+enabled/主导骨前5+身体部位/
//     世界包围盒/形态键/厂商开关引用/颜色变体材质差异；套装级：厂商展示图目录、厂商菜单树原文
//
// 出自 `_长程任务_20260918/作业清单_全部未完成.md` H-02。
// 本工具**不做任何「这是什么部件」的判断**——出图与出数据是它的全部职责。
//
// ── 硬规矩的实现方式 ──────────────────────────────────────────────
// · 全部拍摄在 `EditorApplication.delayCall` 里跑（单次远超 20 s），菜单只在主线程挂一次回调。
// · 单飞锁 `_dsh_tmp_mergeqa/lock`：存在即拒绝执行；跑完（含异常）必删。
// · 拍照用**临时克隆**（整体挪到 x=+10），开关只改克隆，拍完 `DestroyImmediate`；场景不存盘、原对象不变。
// · 取景不信 `Renderer.bounds`（蒙皮网格在编辑期实测虚报成 2×2×2），自己按
//   `Σ w_i · (bone_i.localToWorld · bindpose_i) · v` 算蒙皮世界坐标。
// · front 方向读 Head 骨 forward（水平投影），并把「Head forward 与『部件→相机』方向夹角」写进清单
//   （0° = 正脸朝镜头）。
// ══════════════════════════════════════════════════════════════════
using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using UnityEditor;
using UnityEditor.Animations;
using UnityEngine;
using UnityEngine.Rendering;

namespace AvatarGen
{
    [Serializable]
    public class PacConfig
    {
        public string avatarRoot;
        public string outputRoot;
        public string[] commonClipDirs;
        public string[] bodyRoots;           // 素体身体网格所在节点名（缺省 ["Body","Body_b"]）；Milfy 用 ["Body","Body_base"]
        public int maxRenderersPerOutfit;    // 调试用小样：>0 时每套只拍前 N 个部件；正式跑留 0
        public float partFrameExpand;        // 「整套」按部件取景：部件包围盒扩展倍数；<=0 用默认 2.5
        public float partFrameMinRatio;      // 「整套」按部件取景：部件投影外接框占画幅下限；<=0 用默认 0.05
        public string[] onlyParts;           // 只拍 gameObject.name 命中这些名字的 Renderer（空=全拍）；序号仍按完整列表算（H-03 上游修正后局部重拍）
        public bool cloneBlendshapeSync;     // 克隆上按 ModularAvatarBlendshapeSync 把 LocalBlendshape 跟到参照网格当前值（构建期语义）
        public bool mergeExistingManifest;   // 只拍子集时：把命中条目的新读数并回已存在清单，保留同套其余条目与套级字段
        public PacOutfit[] outfits;
    }

    [Serializable]
    public class PacOutfit
    {
        public string root;              // 克隆里服装根名；含 '/' 时按相对头像根的路径解析（如 "_Outfit/1"）
        public string avatarRoot;        // 可选：本套所属头像根（缺省用 cfg.avatarRoot）；一套配置里可跨多个头像根
        public string product;
        public string vendorImageDir;
        public string vendorPrefab;      // 可选：厂商服装预制件资产路径（不填则从场景节点反查）
    }

    public static class PartAtlasCapture
    {
        const int RES = 768;
        const float CLONE_DX = 10f;
        const float PART_FRAME_EXPAND_DEF = 2.5f;      // 整套对比：部件包围盒至少扩到 2.5 倍
        const float PART_FRAME_MIN_RATIO_DEF = 0.05f;  // 整套对比：部件投影外接框至少占画幅 5%
        const string CONFIG_REL = "_交付/部件图鉴_配置.json";
        const string REPORT_REL = "_交付/部件图鉴_拍摄报告.md";
        const string OVERLAY_PY_REL = "开发工具/通用工具/部件图鉴/part_atlas_overlay.py";
        const string SKIN_TEX = "主贴图按 _MainTex/_BaseMap/_BaseColorMap 优先，否则 shader 第一个非空 TexEnv";
        static readonly string[] BODY_ROOTS_DEF = { "Body", "Body_b" };

        static string PROJ { get { return Directory.GetParent(Application.dataPath).FullName; } }
        static string WORKSPACE { get { return Directory.GetParent(PROJ).FullName; } }
        // 单飞锁：放在工作区（工程的上一级）的 _dsh_tmp_mergeqa/ 下，与同工作区其它 QA 工具共用一把；不写死本机路径。
        static string LOCK_PATH { get { return Path.Combine(WORKSPACE, "_dsh_tmp_mergeqa", "lock"); } }
        static string OVERLAY_JSON { get { return Path.Combine(Path.GetTempPath(), "part_atlas_overlay.json"); } }

        static readonly string[] REGIONS =
            { "头", "颈", "胸", "腰", "臀", "上臂", "前臂", "手", "大腿", "小腿", "脚" };

        // 每次跑都要清空的静态缓存
        static Dictionary<Renderer, Vector3[]> _skinCache = new Dictionary<Renderer, Vector3[]>();
        static Dictionary<AnimationClip, List<string>> _clipParamCache;
        static VendorData _curVendor;
        static string _manifestStart = "", _manifestMd5Start = "", _sceneMd5Start = "";
        static float _partFrameExpand = PART_FRAME_EXPAND_DEF;
        static float _partFrameMinRatio = PART_FRAME_MIN_RATIO_DEF;
        static string[] _bodyRoots = BODY_ROOTS_DEF;   // 本次跑的素体身体节点名（配置可覆盖）
        static float _minPartRatio = 1f;     // 本次跑「整套」新图里部件投影占画幅（面积）的最小值
        static float _minPartLong = 1f;      // 同上的线性口径（最长边占画幅）最小值

        [MenuItem("Tools/PartAtlas/Capture", false, 1)]
        public static void CaptureMenu()
        {
            // 重活不能直接在菜单回调里跑：挂 delayCall 后菜单立刻返回，MCP 不会卡住。
            EditorApplication.delayCall += CaptureRun;
        }

        // ── 主流程 ───────────────────────────────────────────────────
        static void CaptureRun()
        {
            var report = new StringBuilder();
            var overlaySpec = new List<string>();
            int imageCount = 0;
            bool fail = false;
            string failWhy = null;
            DateTime t0 = DateTime.Now;
            report.AppendLine("# 部件图鉴 · 拍摄报告（DSH 自动生成）");
            report.AppendLine();
            report.AppendLine("- 生成时间：" + t0.ToString("yyyy-MM-dd HH:mm:ss"));
            report.AppendLine("- 工程：" + PROJ);

            if (File.Exists(LOCK_PATH))
            {
                Debug.LogError("[PartAtlas] 单飞锁已存在，拒绝执行：" + LOCK_PATH);
                return;
            }
            Directory.CreateDirectory(Path.GetDirectoryName(LOCK_PATH));
            File.WriteAllText(LOCK_PATH, "PartAtlas " + t0.ToString("s"), new UTF8Encoding(false));

            GameObject clone = null;
            GameObject avatar = null;
            PacStudio studio = null;
            SceneHide sceneHide = null;
            int hideClosed = 0, hideParticles = 0;   // 跨头像根累计（多根时收尾要报总数，不是最后一组）
            var scene = UnityEngine.SceneManagement.SceneManager.GetActiveScene();
            try
            {
                _skinCache.Clear();
                _clipParamCache = null;
                _unreadable = 0;
                _unreadableBounds = 0;
                _boneFallback = 0;
                _boneDistFallback = 0;

                string cfgPath = Path.Combine(PROJ, CONFIG_REL);
                if (!File.Exists(cfgPath)) throw new Exception("找不到配置 " + cfgPath);
                var cfg = JsonUtility.FromJson<PacConfig>(File.ReadAllText(cfgPath, Encoding.UTF8));
                if (cfg == null || cfg.outfits == null || cfg.outfits.Length == 0)
                    throw new Exception("配置解析失败或 outfits 为空");
                _partFrameExpand = cfg.partFrameExpand > 0f ? cfg.partFrameExpand : PART_FRAME_EXPAND_DEF;
                _partFrameMinRatio = cfg.partFrameMinRatio > 0f ? cfg.partFrameMinRatio : PART_FRAME_MIN_RATIO_DEF;
                _bodyRoots = (cfg.bodyRoots != null && cfg.bodyRoots.Length > 0) ? cfg.bodyRoots : BODY_ROOTS_DEF;
                _minPartRatio = 1f;
                _minPartLong = 1f;

                report.AppendLine("- 场景：" + scene.path + "  isDirty(改前)=" + scene.isDirty);
                report.AppendLine("- 配置：" + cfgPath);
                _sceneMd5Start = Md5File(Path.Combine(PROJ, scene.path));
                report.AppendLine("- 场景文件 md5(改前)=" + _sceneMd5Start);
                report.AppendLine("- 输出根：" + cfg.outputRoot);
                report.AppendLine("- 素体身体节点：" + string.Join(" / ", _bodyRoots) + "（配置）");

                _manifestStart = Manifest(scene);
                _manifestMd5Start = Md5(_manifestStart);
                report.AppendLine("- 根列表(改前)=" + RootList(scene));
                report.AppendLine("- 层级 md5(改前)=" + _manifestMd5Start);

                // 一套配置可跨多个头像根（衣装 A / B）：按 avatarRoot 分组，一组克隆一次、跑完销毁再下一组。
                var rootOrder = new List<string>();
                var byRoot = new Dictionary<string, List<PacOutfit>>();
                foreach (var o in cfg.outfits)
                {
                    string ar = string.IsNullOrEmpty(o.avatarRoot) ? cfg.avatarRoot : o.avatarRoot;
                    if (!byRoot.ContainsKey(ar)) { byRoot[ar] = new List<PacOutfit>(); rootOrder.Add(ar); }
                    byRoot[ar].Add(o);
                }

                studio = new PacStudio();
                studio.Setup();

                foreach (var ar in rootOrder)
                {
                    avatar = FindByName(scene.GetRootGameObjects(), ar);
                    if (avatar == null) throw new Exception("场景里找不到头像根 " + ar);
                    report.AppendLine();
                    report.AppendLine("## 头像根 " + ar + "  active=" + avatar.activeSelf
                        + "（套 " + byRoot[ar].Count + "）");

                    clone = UnityEngine.Object.Instantiate(avatar);
                    clone.name = "~PartAtlasClone";
                    var clonePos = avatar.transform.position;
                    clone.transform.position = new Vector3(clonePos.x + CLONE_DX, clonePos.y, clonePos.z);
                    report.AppendLine("- 克隆：~PartAtlasClone @ x=" + Num(clone.transform.position.x)
                        + "（原名 " + avatar.name + " @ x=" + Num(clonePos.x) + "）");

                    if (cfg.cloneBlendshapeSync)
                        report.AppendLine("- 克隆形态键同步(MA BlendshapeSync)：" + SyncCloneBlendshapes(clone));

                    _skinCache.Clear();
                    var snap = new CloneSnapshot(clone);
                    var bodyIdx = BodyIndex.Build(clone);
                    report.AppendLine("- 素体顶点索引：" + string.Join("/", _bodyRoots) + " 共 " + bodyIdx.pos.Length
                        + " 顶点，按主导骨分 " + bodyIdx.regionCount + " 个身体部位");

                    // 克隆之外的一切 Renderer/ParticleSystem 全关：正交侧视会把克隆正后方的原头像/其它头像拍进来
                    sceneHide = new SceneHide();
                    report.AppendLine("- 场景外泄核对：非克隆 Renderer 关闭 " + sceneHide.Hide(clone)
                        + " 个 / ParticleSystem 停止 " + sceneHide.ParticleCount + " 个");

                    try
                    {
                        foreach (var o in byRoot[ar])
                        {
                            try
                            {
                                int n = ProcessOutfit(cfg, o, clone, avatar, snap, bodyIdx, studio, report, overlaySpec);
                                imageCount += n;
                            }
                            catch (Exception e)
                            {
                                fail = true; failWhy = "套 " + o.product + " 抛异常: " + e.Message;
                                report.AppendLine();
                                report.AppendLine("## !! 套 " + o.product + " 失败：" + e.Message);
                                report.AppendLine("```\n" + e + "\n```");
                            }
                        }
                    }
                    finally
                    {
                        if (sceneHide != null)
                        {
                            hideClosed += sceneHide.RestoredCount;
                            hideParticles += sceneHide.ParticleCount;
                            try { sceneHide.Restore(); } catch { }
                            sceneHide = null;
                        }
                        if (clone != null) { try { UnityEngine.Object.DestroyImmediate(clone); } catch { } clone = null; }
                    }
                }
            }
            catch (Exception e)
            {
                fail = true; failWhy = "主流程异常: " + e.Message;
                report.AppendLine();
                report.AppendLine("## !! 主流程失败：" + e.Message);
                report.AppendLine("```\n" + e + "\n```");
            }
            finally
            {
                if (sceneHide != null) { try { sceneHide.Restore(); } catch { } }
                if (studio != null) { try { studio.Restore(); } catch { } }
                if (clone != null) { try { UnityEngine.Object.DestroyImmediate(clone); } catch { } }
            }

            // ── 叠字（PIL，在 Unity 外面做）──
            string overlayOut = "(未跑)";
            if (!fail && overlaySpec.Count > 0)
            {
                try
                {
                    string json = "{\"font_size\":22,\"images\":[" + string.Join(",", overlaySpec) + "]}";
                    File.WriteAllText(OVERLAY_JSON, json, new UTF8Encoding(false));
                    string py = Path.Combine(WORKSPACE, OVERLAY_PY_REL);
                    var psi = new System.Diagnostics.ProcessStartInfo
                    {
                        FileName = "python3",
                        Arguments = "\"" + py + "\" \"" + OVERLAY_JSON + "\"",
                        RedirectStandardOutput = true,
                        RedirectStandardError = true,
                        UseShellExecute = false,
                        WorkingDirectory = WORKSPACE
                    };
                    var proc = System.Diagnostics.Process.Start(psi);
                    string so = proc.StandardOutput.ReadToEnd();
                    string se = proc.StandardError.ReadToEnd();
                    proc.WaitForExit();
                    overlayOut = "exit=" + proc.ExitCode + " stdout=" + so.Trim() + " stderr=" + se.Trim();
                    if (proc.ExitCode != 0) { fail = true; failWhy = "叠字失败: " + se.Trim(); }
                }
                catch (Exception e)
                {
                    fail = true; failWhy = "叠字调用异常: " + e.Message;
                    overlayOut = "异常 " + e.Message;
                }
            }
            report.AppendLine();
            report.AppendLine("## 叠字（PIL）");
            report.AppendLine("- 清单：" + OVERLAY_JSON + "（" + overlaySpec.Count + " 条）");
            report.AppendLine("- " + overlayOut);

            // ── 收尾核对 ──
            try
            {
                var scene2 = UnityEngine.SceneManagement.SceneManager.GetActiveScene();
                string manifestAfter = Manifest(scene2);
                string md5After = Md5(manifestAfter);
                string sceneMd5After = Md5File(Path.Combine(PROJ, scene2.path));
                bool same = md5After == _manifestMd5Start;
                bool sceneSame = sceneMd5After == _sceneMd5Start;
                report.AppendLine();
                report.AppendLine("## 收尾核对");
                report.AppendLine("- 根列表(改后)=" + RootList(scene2));
                report.AppendLine("- 层级 md5(改前)=" + _manifestMd5Start);
                report.AppendLine("- 层级 md5(改后)=" + md5After);
                report.AppendLine("- 层级 md5 一致=" + same);
                report.AppendLine("- 场景 isDirty(改后)=" + scene2.isDirty);
                report.AppendLine("- 场景文件 md5(改后)=" + sceneMd5After + "  未变=" + sceneSame);
                report.AppendLine("- 场景外泄核对(恢复)：非克隆 Renderer 恢复 "
                    + hideClosed + " 个 / ParticleSystem 恢复 " + hideParticles
                    + " 个（跨头像根累计；各组的「关闭」读数见上文每组一行）");
                report.AppendLine("- 克隆已销毁=" + (clone == null));
                if (!same) { fail = true; failWhy = "层级 md5 改前改后不一致"; }
                if (!sceneSame) { fail = true; failWhy = "场景文件被动过"; }
            }
            catch (Exception e)
            {
                report.AppendLine("- 收尾核对异常：" + e.Message);
                fail = true; failWhy = "收尾核对异常: " + e.Message;
            }

            report.AppendLine();
            report.AppendLine("## 计数");
            report.AppendLine("- 图片总数=" + imageCount + "（叠字条目=" + overlaySpec.Count + "）");
            report.AppendLine("- 网格不可读(顶点取不到)次数=" + _unreadable
                + "  其中用 renderer.bounds 兜底=" + _unreadableBounds
                + "  用骨骼并集兜底=" + _boneFallback
                + "  主导骨退化用骨距=" + _boneDistFallback);
            report.AppendLine("- 整套对比部件占画幅(面积)最小值=" + Num(_minPartRatio * 100f) + "% / 最长边最小值="
                + Num(_minPartLong * 100f) + "%（面积下限 " + Num(_partFrameMinRatio * 100f)
                + "%，扩展=" + Num(_partFrameExpand) + " 倍；极扁部件面积口径达不到下限时保住整件可见）");
            report.AppendLine("- 失败原因=" + (failWhy ?? "(无)"));
            report.AppendLine();
            report.AppendLine(fail ? "FAIL" : "DONE");

            try { File.WriteAllText(Path.Combine(PROJ, REPORT_REL), report.ToString(), new UTF8Encoding(false)); }
            catch (Exception e) { Debug.LogError("[PartAtlas] 写报告失败 " + e.Message); }
            try { File.Delete(LOCK_PATH); } catch { }

            Debug.Log("[PartAtlas] " + (fail ? "FAIL" : "DONE") + " 图片=" + imageCount
                + " 叠字=" + overlayOut);
        }

        // ── 单套 ─────────────────────────────────────────────────────
        static int ProcessOutfit(PacConfig cfg, PacOutfit o, GameObject clone, GameObject avatar,
                                 CloneSnapshot snap, BodyIndex bodyIdx, PacStudio studio,
                                 StringBuilder report, List<string> overlaySpec)
        {
            var ot = ResolveTransform(clone.transform, o.root);
            if (ot == null) throw new Exception("克隆里找不到服装根 " + o.root);
            ot.gameObject.SetActive(true);                    // 取网格数据要它是活的
            snap.SetOutfit(ot);

            var allRenderers = ot.GetComponentsInChildren<Renderer>(true)
                .Where(r => r is SkinnedMeshRenderer || r is MeshRenderer).ToArray();
            bool subset = cfg.onlyParts != null && cfg.onlyParts.Length > 0;
            var renderers = allRenderers;
            if (subset)
            {
                // 子集重拍：只拍点名部件；序号仍按全列表算（文件名/清单里的 1-based 序号保持稳定）
                var want = new HashSet<string>(cfg.onlyParts);
                renderers = allRenderers.Where(r => want.Contains(r.gameObject.name)).ToArray();
                if (renderers.Length == 0)
                {
                    report.AppendLine();
                    report.AppendLine("## 套 " + o.product + "（根 " + o.root + "）");
                    report.AppendLine("- 只拍子集在本套无命中，跳过（全列表 " + allRenderers.Length + " 件）");
                    return 0;
                }
            }
            else if (cfg.maxRenderersPerOutfit > 0 && renderers.Length > cfg.maxRenderersPerOutfit)
                renderers = renderers.Take(cfg.maxRenderersPerOutfit).ToArray();

            string outDir = Path.Combine(cfg.outputRoot, o.product, "部件图");
            Directory.CreateDirectory(outDir);
            string jsonPath = Path.Combine(cfg.outputRoot, o.product, "部件清单.json");

            // 厂商预制件优先用配置点名（有的场景节点是手工建的，
            // 反查只会得到整台素体的 prefab，不是厂商的服装 prefab）
            string srcPrefab = o.vendorPrefab ?? "";
            string srcFrom = "配置点名";
            if (string.IsNullOrEmpty(srcPrefab))
            {
                srcFrom = "场景节点反查";
                // 必须从**场景原对象**反查：克隆上的对应关系拿不到（实测返回 null）
                var otOrig = ResolveTransform(avatar.transform, o.root);
                if (otOrig != null)
                {
                    var srcObj = PrefabUtility.GetCorrespondingObjectFromSource(otOrig.gameObject);
                    if (srcObj == null) srcObj = PrefabUtility.GetCorrespondingObjectFromOriginalSource(otOrig.gameObject);
                    if (srcObj != null) srcPrefab = AssetDatabase.GetAssetPath(srcObj);
                }
            }
            if (string.IsNullOrEmpty(srcPrefab))
                report.AppendLine("- !! 取不到厂商预制件（root=" + o.root + "）");
            var vendor = VendorInfo.Collect(o, srcPrefab, cfg.commonClipDirs, renderers, avatar);
            _curVendor = vendor;

            var bodyRenderers = new List<Renderer>();
            foreach (var nm in _bodyRoots)
            {
                var t = FindTransform(clone.transform, nm);
                if (t != null) foreach (var r in t.GetComponentsInChildren<Renderer>(true)) bodyRenderers.Add(r);
            }
            Bounds bodyBounds = new Bounds(); bool bodyInit = false;
            foreach (var r in bodyRenderers)
            {
                var b = BoundsOf(r);
                if (b.size == Vector3.zero) continue;
                if (bodyInit) bodyBounds.Encapsulate(b); else { bodyBounds = b; bodyInit = true; }
            }

            var an = clone.GetComponent<Animator>();
            Transform headBone = an != null ? an.GetBoneTransform(HumanBodyBones.Head) : null;
            Vector3 headFwd = headBone != null ? headBone.forward : clone.transform.forward;
            headFwd.y = 0f;
            if (headFwd.sqrMagnitude < 1e-6f) headFwd = Vector3.forward;
            headFwd.Normalize();

            report.AppendLine();
            report.AppendLine("## 套 " + o.product + "（根 " + o.root + "）");
            report.AppendLine("- Renderer 数=" + allRenderers.Length
                + (subset ? "  本次拍摄=" + renderers.Length + "（只拍子集 " + string.Join("/", cfg.onlyParts) + "）" : "")
                + "  预制件=" + srcPrefab + "（" + srcFrom + "）");
            report.AppendLine("- 输出目录=" + outDir);
            report.AppendLine("- front 基准：Head 骨=" + (headBone != null ? headBone.name : "(无)")
                + "  水平 forward=" + F3(headFwd)
                + "  head.y=" + Num(headBone != null ? headBone.position.y : 0f));
            report.AppendLine("- 厂商菜单安装=" + vendor.menuInstallers.Count
                + "  厂商参数=" + vendor.parameters.Count
                + "  菜单树节点=" + vendor.menuTreeLines.Count
                + "  clip 曲线命中=" + vendor.clipHitCount
                + "  颜色变体=" + vendor.variants.Count);
            report.AppendLine("- clip 扫描目录=" + string.Join(" | ", vendor.scanDirs));

            var json = new StringBuilder();
            json.Append("{\n");
            json.Append("  \"商品名\": ").Append(Q(o.product)).Append(",\n");
            json.Append("  \"服装根\": ").Append(Q(o.root)).Append(",\n");
            json.Append("  \"头像根\": ").Append(Q(avatar.name)).Append(",\n");
            json.Append("  \"场景\": ").Append(Q(UnityEngine.SceneManagement.SceneManager.GetActiveScene().path)).Append(",\n");
            json.Append("  \"生成时间\": ").Append(Q(DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss"))).Append(",\n");
            json.Append("  \"渲染器数\": ").Append(allRenderers.Length)
                .Append(subset ? ",\n  \"本次拍摄部件数\": " + renderers.Length : "").Append(",\n");
            json.Append("  \"包围盒口径\": ").Append(Q("世界坐标；蒙皮网格按 Σ w·(bone.localToWorld·bindpose)·v 逐顶点算；编辑期 Renderer.bounds 对未激活过的蒙皮网格虚报成 2×2×2，不可用")).Append(",\n");
            json.Append("  \"主贴图口径\": ").Append(Q(SKIN_TEX)).Append(",\n");
            json.Append("  \"front基准\": {\"骨\": ").Append(Q(headBone != null ? headBone.name : ""))
                .Append(", \"水平forward\": ").Append(V3(headFwd))
                .Append(", \"headWorldY\": ").Append(Num(headBone != null ? headBone.position.y : 0f)).Append("},\n");
            json.Append("  \"厂商展示图目录\": ").Append(Q(o.vendorImageDir)).Append(",\n");
            json.Append("  \"厂商展示图\": ").Append(QArr(ListVendorImages(o.vendorImageDir))).Append(",\n");
            json.Append("  \"厂商菜单树\": ").Append(QArr(vendor.menuTreeLines)).Append(",\n");
            json.Append("  \"场景头像菜单树\": ").Append(QArr(vendor.sceneMenuTree)).Append(",\n");
            json.Append("  \"厂商菜单安装\": [").Append(string.Join(", ", vendor.menuInstallers)).Append("],\n");
            json.Append("  \"厂商参数\": [").Append(string.Join(", ", vendor.parameters)).Append("],\n");
            json.Append("  \"厂商开关组件\": [").Append(string.Join(", ", vendor.toggleComps)).Append("],\n");
            json.Append("  \"厂商形态键驱动\": [").Append(string.Join(", ", vendor.shapeDrivers)).Append("],\n");
            json.Append("  \"clip扫描目录\": ").Append(QArr(vendor.scanDirs)).Append(",\n");
            json.Append("  \"颜色变体参考预制件\": ").Append(Q(srcPrefab)).Append(",\n");
            json.Append("  \"颜色变体\": [").Append(string.Join(", ", vendor.variants)).Append("],\n");
            json.Append("  \"部件\": [\n");

            int idx = 0, img = 0;
            var entries = new List<string>();
            var hitSet = new HashSet<Renderer>(renderers);
            foreach (var r in allRenderers)
            {
                idx++;
                if (!hitSet.Contains(r)) continue;      // 子集：序号照数，但不拍
                int before = img;
                string rel = RelPath(r.transform, clone.transform);
                var sink = new ImageSink((file, lines) =>
                    overlaySpec.Add("{\"file\":" + Q(file) + ",\"lines\":" + QArr(lines) + "}"));
                entries.Add(ProcessRenderer(o, r, rel, idx, snap, bodyIdx, studio, outDir,
                                            bodyBounds, headFwd, ref img, sink, report));
                if (img == before) throw new Exception("部件 " + rel + " 一张图都没出");
            }
            json.Append(string.Join(",\n", entries));
            json.Append("\n  ],\n");
            json.Append("  \"图片数\": ").Append(img).Append("\n");
            json.Append("}\n");
            string jsonText = json.ToString();
            if (subset && cfg.mergeExistingManifest && File.Exists(jsonPath))
                jsonText = MergeManifestEntries(File.ReadAllText(jsonPath, Encoding.UTF8), entries,
                    DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss"));
            File.WriteAllText(jsonPath, jsonText, new UTF8Encoding(false));

            report.AppendLine("- 部件清单：" + jsonPath + "（本次 " + entries.Count + " 条"
                + (subset && cfg.mergeExistingManifest ? "，并回已存在清单、保留其余条目" : "") + "）");
            report.AppendLine("- 出图：" + img + " 张");
            return img;
        }

        delegate void ImageSink(string file, string[] lines);

        static string ProcessRenderer(PacOutfit o, Renderer r, string rel, int idx, CloneSnapshot snap,
                                      BodyIndex bodyIdx, PacStudio studio, string outDir, Bounds bodyBounds,
                                      Vector3 headFwd, ref int img, ImageSink sink, StringBuilder report)
        {
            var pos = WorldPositions(r);
            string bMethod;
            var bounds = BoundsOf(r, out bMethod);
            var mesh = MeshOf(r);
            int tris = 0;
            if (mesh != null)
                for (int i = 0; i < mesh.subMeshCount; i++) tris += (int)(mesh.GetIndexCount(i) / 3);

            var dom = DominantBones(r, 5);
            var regions = new HashSet<string>(dom.Select(d => d.region));
            var ctxRegions = new HashSet<string>(regions);
            foreach (var rg in regions) foreach (var nb in Neighbors(rg)) ctxRegions.Add(nb);

            var mats = r.sharedMaterials.Select(m => m != null ? m.name : "null").ToList();
            string lastTwo = LastTwo(rel);
            string safe = Safe(r.gameObject.name);

            // 取景：部件 ∪ 相关身体部位（含相邻部位）
            var union = bounds; bool abInit = false;
            foreach (var rg in ctxRegions)
            {
                var rb = bodyIdx.RegionBounds(rg);
                if (rb.size == Vector3.zero) continue;
                if (abInit) union.Encapsulate(rb); else { union = rb; abInit = true; }
            }
            if (abInit) union.Encapsulate(bounds);

            // ── ① 在身上单独看（正/侧/背）──
            ScenarioOnlyPart(snap, r, true);
            double frontAngle = 0;
            var views = new[]
            {
                new object[] { "在身上-正面", "在身上-正面", 0f, true },
                new object[] { "在身上-侧面", "在身上-侧面", 90f, false },
                new object[] { "在身上-背面", "在身上-背面", 180f, false },
            };
            foreach (var vv in views)
            {
                string key = (string)vv[0], label = (string)vv[1];
                float yaw = (float)vv[2];
                bool isFront = (bool)vv[3];
                Vector3 dir = Quaternion.AngleAxis(yaw, Vector3.up) * headFwd;
                if (isFront) frontAngle = Vector3.Angle(headFwd, dir);
                var fr = MakeFrame(pos, bounds, union, dir, true);
                string f = Path.Combine(outDir, string.Format("{0:D2}_{1}_{2}.png", idx, safe, key));
                studio.Shoot(fr.target, dir, fr.ortho);
                SaveTex(studio.Last, f);
                img++;
                sink(f, new[] { o.product + " / " + lastTwo + " / " + label,
                                "tris=" + tris + " / mats=" + string.Join(",", mats) });
            }

            // ── ② 仅部件（正面）──
            ScenarioOnlyPart(snap, r, false);
            {
                var fr = MakeFrame(pos, bounds, bounds, headFwd, true);
                string f = Path.Combine(outDir, string.Format("{0:D2}_{1}_仅部件-正面.png", idx, safe));
                studio.Shoot(fr.target, headFwd, fr.ortho);
                SaveTex(studio.Last, f);
                img++;
                sink(f, new[] { o.product + " / " + lastTwo + " / 仅部件-正面",
                                "tris=" + tris + " / mats=" + string.Join(",", mats) });
            }

            // ── ③ 整套有/无对比（新：按部件取景；旧：全身取景，改名 整套全身-*）──
            ScenarioWholeOutfit(snap, r, true);
            var whole = bodyBounds;
            var vis = VisibleBounds(snap);
            if (vis.size != Vector3.zero) whole.Encapsulate(vis);

            // 按部件取景框：部件包围盒扩到 _partFrameExpand 倍，再并进相邻身体部位
            var partFrame = bounds;
            partFrame.size = bounds.size * _partFrameExpand;
            foreach (var rg in ctxRegions)
            {
                var rb = bodyIdx.RegionBounds(rg);
                if (rb.size == Vector3.zero) continue;
                partFrame.Encapsulate(rb);
            }

            bool onBack = false;
            {
                float depth = Mathf.Abs(Vector3.Dot(bodyBounds.size, headFwd));
                float d = Vector3.Dot(bounds.center - bodyBounds.center, headFwd);
                onBack = depth > 1e-4f && d < -0.15f * depth;
            }
            string partFlag = "tris=" + tris + " / mats=" + string.Join(",", mats);
            var tags = onBack ? new[] { "正面", "背面" } : new[] { "正面" };
            float partRatioFront = 1f, partLongFront = 1f, orthoFront = 0f;
            for (int ti = 0; ti < tags.Length; ti++)
            {
                string tag = tags[ti];
                float yaw = tag == "背面" ? 180f : 0f;
                Vector3 dir = Quaternion.AngleAxis(yaw, Vector3.up) * headFwd;

                // 新：按部件取景（有/无同机位；部件投影框小于下限就往里收，但不切件）
                var frp = MakeFrame(pos, bounds, partFrame, dir, false);
                float orthoP = FitPartFrame(pos, bounds, dir, frp.ortho, _partFrameMinRatio);
                float ratio = PartFrameRatio(pos, bounds, dir, orthoP);
                float ratioLong = PartFrameLong(pos, bounds, dir, orthoP);
                if (ti == 0) { partRatioFront = ratio; partLongFront = ratioLong; orthoFront = orthoP; }
                if (ratio < _minPartRatio) _minPartRatio = ratio;
                if (ratioLong < _minPartLong) _minPartLong = ratioLong;
                string fOn = Path.Combine(outDir, string.Format("{0:D2}_{1}_整套-有-{2}.png", idx, safe, tag));
                ScenarioWholeOutfit(snap, r, true);
                studio.Shoot(frp.target, dir, orthoP); SaveTex(studio.Last, fOn); img++;
                sink(fOn, new[] { o.product + " / " + lastTwo + " / 整套-有-" + tag, partFlag });
                string fOff = Path.Combine(outDir, string.Format("{0:D2}_{1}_整套-无-{2}.png", idx, safe, tag));
                ScenarioWholeOutfit(snap, r, false);
                studio.Shoot(frp.target, dir, orthoP); SaveTex(studio.Last, fOff); img++;
                sink(fOff, new[] { o.product + " / " + lastTwo + " / 整套-无-" + tag, partFlag });

                // 旧：全身取景（保留），改名 整套全身-*，有/无同机位
                var frw = MakeFrame(null, whole, whole, dir, false);
                string gOn = Path.Combine(outDir, string.Format("{0:D2}_{1}_整套全身-有-{2}.png", idx, safe, tag));
                ScenarioWholeOutfit(snap, r, true);
                studio.Shoot(frw.target, dir, frw.ortho); SaveTex(studio.Last, gOn); img++;
                sink(gOn, new[] { o.product + " / " + lastTwo + " / 整套全身-有-" + tag, partFlag });
                string gOff = Path.Combine(outDir, string.Format("{0:D2}_{1}_整套全身-无-{2}.png", idx, safe, tag));
                ScenarioWholeOutfit(snap, r, false);
                studio.Shoot(frw.target, dir, frw.ortho); SaveTex(studio.Last, gOff); img++;
                sink(gOff, new[] { o.product + " / " + lastTwo + " / 整套全身-无-" + tag, partFlag });
            }
            snap.ResetAll();

            report.AppendLine("- [" + idx.ToString("D2") + "] " + rel + "  tris=" + tris
                + "  mats=" + mats.Count + "  包围盒口径=" + bMethod
                + "  身体部位=" + string.Join("/", regions.OrderBy(x => x))
                + "  正视夹角=" + Num((float)frontAngle) + "°  背面补图=" + onBack
                + "  整套对比部件占画幅=" + Num(partRatioFront * 100f) + "%(面积)/"
                + Num(partLongFront * 100f) + "%(最长边)");

            // ── 清单条目 ──
            var js = new StringBuilder();
            js.Append("    {\n");
            js.Append("      \"相对头像根路径\": ").Append(Q(rel)).Append(",\n");
            js.Append("      \"网格名\": ").Append(Q(mesh != null ? mesh.name : "")).Append(",\n");
            js.Append("      \"渲染器类型\": ").Append(Q(r.GetType().Name)).Append(",\n");
            js.Append("      \"三角数\": ").Append(tris).Append(",\n");
            js.Append("      \"包围盒世界\": {\"center\": ").Append(V3(bounds.center))
              .Append(", \"size\": ").Append(V3(bounds.size))
              .Append(", \"min\": ").Append(V3(bounds.min))
              .Append(", \"max\": ").Append(V3(bounds.max))
              .Append(", \"口径\": ").Append(Q(bMethod)).Append("},\n");
            js.Append("      \"取景框世界\": {\"center\": ").Append(V3(union.center))
              .Append(", \"size\": ").Append(V3(union.size)).Append("},\n");
            js.Append("      \"整套对比取景\": {\"部件投影占画幅\": ").Append(Num(partRatioFront))
              .Append(", \"部件投影最长边占画幅\": ").Append(Num(partLongFront))
              .Append(", \"取景半宽\": ").Append(Num(orthoFront))
              .Append(", \"扩展倍数\": ").Append(Num(_partFrameExpand))
              .Append(", \"占画幅下限\": ").Append(Num(_partFrameMinRatio))
              .Append(", \"口径\": ").Append(Q("整套-有/无 新图：部件包围盒扩 N 倍并并进相邻身体部位；部件投影外接框 <5% 画幅就往里收，但绝不切件；有/无同机位")).Append("},\n");
            js.Append("      \"默认\": {\"activeSelf\": ").Append(snap.defActive[r.gameObject] ? "true" : "false")
              .Append(", \"enabled\": ").Append(snap.defEnabled[r] ? "true" : "false")
              .Append(", \"父链activeSelf\": ").Append(QArr(ChainActive(r.transform))).Append("},\n");
            js.Append("      \"材质\": [").Append(string.Join(", ", MatEntries(r))).Append("],\n");
            js.Append("      \"主导骨前5\": [")
              .Append(string.Join(", ", dom.Select(d =>
                  "{\"骨\": " + Q(d.bone) + ", \"权重和\": " + (d.w < 0f ? "null" : Num(d.w))
                  + ", \"顶点数\": " + d.v + ", \"身体部位\": " + Q(d.region) + ", \"口径\": " + Q(d.method) + "}")))
              .Append("],\n");
            js.Append("      \"相关身体部位\": ").Append(QArr(regions.OrderBy(x => x))).Append(",\n");
            js.Append("      \"取景身体部位(含相邻)\": ").Append(QArr(ctxRegions.OrderBy(x => x))).Append(",\n");
            js.Append("      \"形态键总数\": ").Append(mesh != null ? mesh.blendShapeCount : 0).Append(",\n");
            js.Append("      \"形态键\": [").Append(string.Join(", ", BlendShapeEntries(r, mesh))).Append("],\n");
            js.Append("      \"正视夹角_度\": ").Append(Num((float)frontAngle))
              .Append(",\n      \"正视夹角_口径\": ").Append(Q("Head 骨水平 forward 与『部件→相机』方向的夹角；0° = 正脸朝镜头")).Append(",\n");
            js.Append("      \"出图\": ").Append(QArr(ImageNames(outDir, idx, safe))).Append(",\n");
            js.Append("      \"厂商开关引用\": ").Append(VendorRefs(rel)).Append("\n");
            js.Append("    }");
            return js.ToString();
        }

        // ── 子集重拍的两个帮手（H-03）────────────────────────────────
        // 克隆上按 MA BlendshapeSync 把 LocalBlendshape 跟到参照网格当前值（构建期语义）：
        // 编辑模式里 NDMF 预览有没有跑、跑没跑完都不确定，拍照克隆必须先落到「构建期同步后」的形态键。
        static string SyncCloneBlendshapes(GameObject clone)
        {
            var lines = new List<string>();
            const string MA_SYNC = "nadena.dev.modular_avatar.core.ModularAvatarBlendshapeSync";
            var bf = System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.NonPublic
                     | System.Reflection.BindingFlags.Instance;
            foreach (var c in clone.GetComponentsInChildren<Component>(true))
            {
                if (c == null || c.GetType().FullName != MA_SYNC) continue;
                var bindF = c.GetType().GetField("Bindings", bf);
                var list = bindF != null ? bindF.GetValue(c) as IEnumerable : null;
                if (list == null) continue;
                var smr = c.GetComponent<SkinnedMeshRenderer>();
                if (smr == null) smr = c.GetComponentInChildren<SkinnedMeshRenderer>(true);
                if (smr == null) { lines.Add(RelPath(c.transform, clone.transform) + " · 无 SMR，跳过"); continue; }
                foreach (var b in list)
                {
                    if (b == null) continue;
                    var bt = b.GetType();
                    var rmF = bt.GetField("ReferenceMesh", bf);
                    var blF = bt.GetField("Blendshape", bf);
                    var lbF = bt.GetField("LocalBlendshape", bf);
                    if (rmF == null || blF == null || lbF == null) continue;
                    string key = blF.GetValue(b) as string;
                    string local = lbF.GetValue(b) as string;
                    var rm = rmF.GetValue(b);
                    if (rm == null || string.IsNullOrEmpty(key)) continue;
                    var getM = rm.GetType().GetMethod("Get", new[] { typeof(Component) });
                    var refGo = getM != null ? getM.Invoke(rm, new object[] { c }) as GameObject : null;
                    if (refGo == null) { lines.Add(key + " · 参照网格解析失败"); continue; }
                    var refSmr = refGo.GetComponent<SkinnedMeshRenderer>();
                    if (refSmr == null || refSmr.sharedMesh == null) { lines.Add(key + " · 参照网格无 SMR"); continue; }
                    int ri = refSmr.sharedMesh.GetBlendShapeIndex(key);
                    if (ri < 0) { lines.Add(key + " · 参照键不存在"); continue; }
                    string lk = string.IsNullOrEmpty(local) ? key : local;
                    int li = smr.sharedMesh != null ? smr.sharedMesh.GetBlendShapeIndex(lk) : -1;
                    if (li < 0) { lines.Add(lk + " · 本地键不存在"); continue; }
                    float before = smr.GetBlendShapeWeight(li);
                    float v = refSmr.GetBlendShapeWeight(ri);
                    smr.SetBlendShapeWeight(li, v);
                    lines.Add(RelPath(smr.transform, clone.transform) + " · " + lk + " " + Num(before) + "→" + Num(v)
                        + "（参照 " + RelPath(refGo.transform, clone.transform) + " · " + key + "=" + Num(v) + "）");
                }
            }
            return lines.Count == 0 ? "无绑定" : string.Join("；", lines);
        }

        // 只拍子集时把命中条目的新读数并回已存在清单：条目按「相对头像根路径」定位、整块替换，
        // 同套其余条目与套级字段原样保留（否则整份清单会只剩命中的几条）。
        static string MergeManifestEntries(string existing, List<string> newEntries, string stamp)
        {
            int gi = existing.IndexOf("\"生成时间\": ", StringComparison.Ordinal);
            if (gi >= 0)
            {
                int gs = existing.IndexOf('"', gi + "\"生成时间\": ".Length);
                int ge = gs >= 0 ? existing.IndexOf('"', gs + 1) : -1;
                if (gs > 0 && ge > gs) existing = existing.Substring(0, gs + 1) + stamp + existing.Substring(ge);
            }
            foreach (var ne in newEntries)
            {
                int k = ne.IndexOf("\"相对头像根路径\": ", StringComparison.Ordinal);
                if (k < 0) throw new Exception("新条目缺少相对头像根路径");
                int eol = ne.IndexOf('\n', k);
                string line = (eol > k ? ne.Substring(k, eol - k) : ne.Substring(k)).TrimEnd(',');
                int m = existing.IndexOf(line, StringComparison.Ordinal);
                if (m < 0) throw new Exception("已存在清单里找不到条目 " + line);
                int start = existing.LastIndexOf("    {", m, StringComparison.Ordinal);
                int end = existing.IndexOf("\n    }", m, StringComparison.Ordinal);
                if (start < 0 || end < 0) throw new Exception("条目边界定位失败 " + line);
                end += "\n    }".Length;
                existing = existing.Substring(0, start) + ne + existing.Substring(end);
            }
            return existing;
        }

        // ── 场景状态切换 ─────────────────────────────────────────────
        static Bounds VisibleBounds(CloneSnapshot snap)
        {
            var b = new Bounds(); bool init = false;
            foreach (var r in snap.renderers)
            {
                if (r == null || !r.enabled || !r.gameObject.activeInHierarchy) continue;
                var rb = BoundsOf(r);
                if (rb.size == Vector3.zero) continue;
                if (init) b.Encapsulate(rb); else { b = rb; init = true; }
            }
            return init ? b : new Bounds();
        }

        static void ScenarioOnlyPart(CloneSnapshot snap, Renderer target, bool includeBody)
        {
            snap.ResetAll();
            foreach (var r in snap.renderers) r.enabled = false;         // 含 ParticleSystemRenderer
            foreach (var ps in snap.particles) ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            snap.ActivateChain(target.gameObject);
            target.enabled = true;
            foreach (var ps in target.GetComponentsInChildren<ParticleSystem>(true)) ps.Play();  // 目标自带粒子例外
            if (includeBody)
                foreach (var r in snap.bodyRenderers) { snap.ActivateChain(r.gameObject); r.enabled = true; }
        }

        static void ScenarioWholeOutfit(CloneSnapshot snap, Renderer target, bool partOn)
        {
            snap.ResetAll();
            var keep = new HashSet<Renderer>(snap.bodyRenderers);
            foreach (var r in snap.outfitRenderers) keep.Add(r);
            foreach (var r in snap.renderers) if (!keep.Contains(r)) r.enabled = false;
            foreach (var r in snap.bodyRenderers) { snap.ActivateChain(r.gameObject); r.enabled = true; }
            snap.ActivateChain(snap.outfitRoot);
            snap.ActivateChain(target.gameObject);
            target.enabled = partOn;
        }

        // ── 取景 ─────────────────────────────────────────────────────
        static (Vector3 target, float ortho) MakeFrame(Vector3[] partPos, Bounds part, Bounds union,
                                                       Vector3 dirToCam, bool cap)
        {
            dirToCam = dirToCam.normalized;
            Quaternion q = Quaternion.LookRotation(-dirToCam, Vector3.up);
            Vector3 cr = q * Vector3.right, cu = q * Vector3.up;
            Vector3 center = part.size != Vector3.zero ? part.center : union.center;
            float phx = 0f, phy = 0f, uhx = 0f, uhy = 0f;
            // 部件半宽：有顶点用顶点（准），没有（网格不可读）退化为包围盒 8 角
            var partPts = partPos != null && partPos.Length > 0 ? partPos : Corners(part).ToArray();
            foreach (var p in partPts)
            {
                float x = Mathf.Abs(Vector3.Dot(p - center, cr));
                float y = Mathf.Abs(Vector3.Dot(p - center, cu));
                if (x > phx) phx = x;
                if (y > phy) phy = y;
            }
            foreach (var c in Corners(union))
            {
                float x = Mathf.Abs(Vector3.Dot(c - center, cr));
                float y = Mathf.Abs(Vector3.Dot(c - center, cu));
                if (x > uhx) uhx = x;
                if (y > uhy) uhy = y;
            }
            if (phx <= 0f) phx = uhx;
            if (phy <= 0f) phy = uhy;
            float hx = uhx, hy = uhy;
            if (cap)
            {
                // 身体部位只作上下文，最多占 2.2 倍部件半宽 —— 保证小部件（乳贴/项圈）不会缩成几十像素
                hx = Mathf.Min(uhx, Mathf.Max(phx * 2.2f, phx + 0.04f));
                hy = Mathf.Min(uhy, Mathf.Max(phy * 2.2f, phy + 0.04f));
            }
            return (center, Mathf.Max(hx, hy) * 1.12f);
        }

        // 部件投影半宽/半高（与 MakeFrame 同一口径：有顶点用顶点，没有退化为包围盒 8 角）
        static void PartFrameHW(Vector3[] partPos, Bounds part, Vector3 dirToCam, out float phx, out float phy)
        {
            dirToCam = dirToCam.normalized;
            Quaternion q = Quaternion.LookRotation(-dirToCam, Vector3.up);
            Vector3 cr = q * Vector3.right, cu = q * Vector3.up;
            Vector3 center = part.center;
            var pts = partPos != null && partPos.Length > 0 ? partPos : Corners(part).ToArray();
            phx = 0f; phy = 0f;
            foreach (var p in pts)
            {
                float x = Mathf.Abs(Vector3.Dot(p - center, cr));
                float y = Mathf.Abs(Vector3.Dot(p - center, cu));
                if (x > phx) phx = x;
                if (y > phy) phy = y;
            }
        }

        // 部件投影外接框占画幅比例（画幅半宽=半高=ortho，故 = (2phx·2phy)/(2ortho)²）
        static float PartFrameRatio(Vector3[] partPos, Bounds part, Vector3 dirToCam, float ortho)
        {
            float phx, phy; PartFrameHW(partPos, part, dirToCam, out phx, out phy);
            if (phx <= 0f || phy <= 0f || ortho <= 0f) return 1f;
            return (phx * phy) / (ortho * ortho);
        }

        // 部件投影框小于 minRatio 就把 ortho 往里收 —— 「小部件不许只占几个像素」的硬保证。
        // 但绝不切掉部件：ortho 至少 = 部件投影半宽/半高。极扁的部件（如双手指甲 46:1）面积口径
        // 数学上到不了 minRatio，此时保住「整件可见」，如实给出实际占比。
        static float FitPartFrame(Vector3[] partPos, Bounds part, Vector3 dirToCam, float ortho, float minRatio)
        {
            if (minRatio <= 0f) return ortho;
            float phx, phy; PartFrameHW(partPos, part, dirToCam, out phx, out phy);
            if (phx <= 0f || phy <= 0f) return ortho;
            float need = Mathf.Max(Mathf.Sqrt(phx * phy / minRatio), Mathf.Max(phx, phy));
            return Mathf.Min(ortho, need);
        }

        // 部件投影最长边占画幅（线性口径；对极扁部件比面积口径更能反映「看得清」）
        static float PartFrameLong(Vector3[] partPos, Bounds part, Vector3 dirToCam, float ortho)
        {
            float phx, phy; PartFrameHW(partPos, part, dirToCam, out phx, out phy);
            if (ortho <= 0f) return 1f;
            return Mathf.Max(phx, phy) / ortho;
        }

        static IEnumerable<Vector3> Corners(Bounds b)
        {
            var c = b.center; var e = b.extents;
            for (int i = 0; i < 8; i++)
                yield return c + new Vector3((i & 1) == 0 ? -e.x : e.x,
                                             (i & 2) == 0 ? -e.y : e.y,
                                             (i & 4) == 0 ? -e.z : e.z);
        }

        static void SaveTex(Texture2D tex, string path)
        {
            if (tex == null) throw new Exception("渲染失败（无纹理）" + path);
            File.WriteAllBytes(path, tex.EncodeToPNG());
            UnityEngine.Object.DestroyImmediate(tex);
        }

        // ── 包围盒 / 蒙皮 ────────────────────────────────────────────
        static Mesh MeshOf(Renderer r)
        {
            var s = r as SkinnedMeshRenderer;
            if (s != null) return s.sharedMesh;
            var mf = r.GetComponent<MeshFilter>();
            return mf != null ? mf.sharedMesh : null;
        }

        static Bounds BoundsOf(Renderer r) { string m; return BoundsOf(r, out m); }

        // 口径优先级：① 网格可读 → 自己逐顶点算（最准，蒙皮按骨权重）
        //             ② 网格不可读（厂商 FBX 关了 Read/Write，实测 Velour 9 个网格全中）→ 用
        //                `Renderer.bounds`（它由序列化的 localBounds 推出，实测 Velour 准）
        //             ③ `Renderer.bounds` 退化（kaguya_cloth 的 localBounds 序列化成 2×2×2）→ 骨骼并集兜底
        static Bounds BoundsOf(Renderer r, out string method)
        {
            var pos = WorldPositions(r);
            if (pos.Length > 0)
            {
                method = r is SkinnedMeshRenderer ? "蒙皮逐顶点" : "MeshFilter.localToWorld";
                var b0 = new Bounds(pos[0], Vector3.zero);
                for (int i = 1; i < pos.Length; i++) b0.Encapsulate(pos[i]);
                return b0;
            }
            var rb = r.bounds;
            if (!Degenerate(rb))
            {
                method = "renderer.bounds（网格不可读）";
                _unreadableBounds++;
                return rb;
            }
            method = "骨骼并集（网格不可读且 bounds 退化）";
            _boneFallback++;
            var b = new Bounds(); bool init = false;
            var s = r as SkinnedMeshRenderer;
            if (s != null && s.bones != null)
                foreach (var bn in s.bones)
                {
                    if (bn == null) continue;
                    if (init) b.Encapsulate(bn.position); else { b = new Bounds(bn.position, Vector3.zero); init = true; }
                }
            if (!init) b = new Bounds(r.transform.position, Vector3.zero);
            return b;
        }

        static bool Degenerate(Bounds b)
        {
            if (b.size == Vector3.zero) return true;
            return Mathf.Abs(b.size.x - 2f) < 0.01f && Mathf.Abs(b.size.y - 2f) < 0.01f && Mathf.Abs(b.size.z - 2f) < 0.01f;
        }

        static int _unreadableBounds, _boneFallback;

        static Vector3[] WorldPositions(Renderer r)
        {
            var s = r as SkinnedMeshRenderer;
            if (s != null) return SkinPositions(s);
            var mf = r.GetComponent<MeshFilter>();
            if (mf == null || mf.sharedMesh == null) return new Vector3[0];
            var m = mf.sharedMesh;
            if (!m.isReadable) { _unreadable++; return new Vector3[0]; }
            var mtx = r.transform.localToWorldMatrix;
            var vs = m.vertices;
            var outv = new Vector3[vs.Length];
            for (int i = 0; i < vs.Length; i++) outv[i] = mtx.MultiplyPoint3x4(vs[i]);
            return outv;
        }

        static int _unreadable;

        static Vector3[] SkinPositions(SkinnedMeshRenderer s)
        {
            Vector3[] cached;
            if (_skinCache.TryGetValue(s, out cached)) return cached;
            var mesh = s.sharedMesh;
            if (mesh == null || !mesh.isReadable) { _unreadable++; return _skinCache[s] = new Vector3[0]; }
            var vs = mesh.vertices;
            var bw = mesh.boneWeights;
            var bones = s.bones;
            var bp = mesh.bindposes;
            var outv = new Vector3[vs.Length];
            if (bw == null || bw.Length != vs.Length || bones == null || bones.Length == 0)
            {
                for (int i = 0; i < vs.Length; i++) outv[i] = s.transform.TransformPoint(vs[i]);
                return _skinCache[s] = outv;
            }
            var mats = new Matrix4x4[bones.Length];
            for (int i = 0; i < bones.Length; i++)
                mats[i] = bones[i] != null ? bones[i].localToWorldMatrix * bp[i] : Matrix4x4.identity;
            for (int i = 0; i < vs.Length; i++)
            {
                var w = bw[i]; var v = vs[i]; Vector3 p = Vector3.zero; float tw = 0f;
                if (w.weight0 > 0f) { p += w.weight0 * mats[w.boneIndex0].MultiplyPoint3x4(v); tw += w.weight0; }
                if (w.weight1 > 0f) { p += w.weight1 * mats[w.boneIndex1].MultiplyPoint3x4(v); tw += w.weight1; }
                if (w.weight2 > 0f) { p += w.weight2 * mats[w.boneIndex2].MultiplyPoint3x4(v); tw += w.weight2; }
                if (w.weight3 > 0f) { p += w.weight3 * mats[w.boneIndex3].MultiplyPoint3x4(v); tw += w.weight3; }
                outv[i] = tw > 0f ? p / tw : s.transform.TransformPoint(v);
            }
            return _skinCache[s] = outv;
        }

        struct DomBone { public string bone; public float w; public int v; public string region; public string method; }

        static List<DomBone> DominantBones(Renderer r, int top)
        {
            var res = new List<DomBone>();
            var s = r as SkinnedMeshRenderer;
            if (s == null || s.sharedMesh == null) return res;
            var mesh = s.sharedMesh;
            var bones = s.bones;
            if (bones == null) return res;

            // 网格可读 → 按蒙皮权重和排序（真口径）
            if (mesh.isReadable)
            {
                var bw = mesh.boneWeights;
                if (bw != null && bw.Length > 0)
                {
                    var wsum = new Dictionary<int, float>();
                    var vcnt = new Dictionary<int, int>();
                    for (int i = 0; i < bw.Length; i++)
                    {
                        var w = bw[i];
                        AddW(w.boneIndex0, w.weight0, wsum, vcnt);
                        AddW(w.boneIndex1, w.weight1, wsum, vcnt);
                        AddW(w.boneIndex2, w.weight2, wsum, vcnt);
                        AddW(w.boneIndex3, w.weight3, wsum, vcnt);
                    }
                    foreach (var kv in wsum.OrderByDescending(k => k.Value).Take(top))
                    {
                        var b = kv.Key < bones.Length ? bones[kv.Key] : null;
                        res.Add(new DomBone
                        {
                            bone = b != null ? b.name : "(null)",
                            w = kv.Value,
                            v = vcnt.ContainsKey(kv.Key) ? vcnt[kv.Key] : 0,
                            region = BoneRegions.RegionOf(b),
                            method = "蒙皮权重和"
                        });
                    }
                    return res;
                }
            }

            // 网格不可读（读不到 boneWeights）→ 退化为「骨骼到部件包围盒的距离」排序，
            // 只用于给取景找身体部位上下文，口径写进清单，不冒充权重结论。
            _boneDistFallback++;
            var bb = BoundsOf(r);
            var cand = new List<Tuple<float, Transform>>();
            var seen = new HashSet<Transform>();
            foreach (var bn in bones)
            {
                if (bn == null || !seen.Add(bn)) continue;
                cand.Add(Tuple.Create(DistanceToBounds(bn.position, bb), bn));
            }
            foreach (var t in cand.OrderBy(x => x.Item1).Take(top))
                res.Add(new DomBone
                {
                    bone = t.Item2.name,
                    w = -1f,
                    v = 0,
                    region = BoneRegions.RegionOf(t.Item2),
                    method = "骨骼到包围盒距离（网格不可读）"
                });
            return res;
        }

        static int _boneDistFallback;

        static float DistanceToBounds(Vector3 p, Bounds b)
        {
            var c = b.ClosestPoint(p);
            return Vector3.Distance(p, c);
        }

        static void AddW(int idx, float w, Dictionary<int, float> s, Dictionary<int, int> c)
        {
            if (w <= 0f) return;
            s[idx] = (s.ContainsKey(idx) ? s[idx] : 0f) + w;
            c[idx] = (c.ContainsKey(idx) ? c[idx] : 0) + 1;
        }

        static string[] Neighbors(string r)
        {
            switch (r)
            {
                case "头": return new[] { "颈" };
                case "颈": return new[] { "头", "胸" };
                case "胸": return new[] { "颈", "腰", "上臂" };
                case "腰": return new[] { "胸", "臀" };
                case "臀": return new[] { "腰", "大腿" };
                case "上臂": return new[] { "胸", "前臂" };
                case "前臂": return new[] { "上臂", "手" };
                case "手": return new[] { "前臂" };
                case "大腿": return new[] { "臀", "小腿" };
                case "小腿": return new[] { "大腿", "脚" };
                case "脚": return new[] { "小腿" };
                default: return new string[0];
            }
        }

        // ── 身体部位索引 ─────────────────────────────────────────────
        class BodyIndex
        {
            public Vector3[] pos;
            public string[] region;
            public int regionCount;
            Dictionary<string, Bounds> _cache = new Dictionary<string, Bounds>();

            public static BodyIndex Build(GameObject clone)
            {
                var bi = new BodyIndex();
                BoneRegions.RegisterHumanoid(clone.GetComponent<Animator>());
                var ps = new List<Vector3>();
                var rs = new List<string>();
                foreach (var nm in _bodyRoots)
                {
                    var t = FindTransform(clone.transform, nm);
                    if (t == null) continue;
                    foreach (var s in t.GetComponentsInChildren<SkinnedMeshRenderer>(true))
                    {
                        var mesh = s.sharedMesh;
                        if (mesh == null) continue;
                        var bws = mesh.boneWeights;
                        var bones = s.bones;
                        var wp = SkinPositions(s);
                        for (int i = 0; i < mesh.vertexCount; i++)
                        {
                            if (bws == null || i >= bws.Length || bws[i].weight0 <= 0f) continue;
                            int bi0 = bws[i].boneIndex0;
                            var bone = bones != null && bi0 < bones.Length ? bones[bi0] : null;
                            ps.Add(wp[i]);
                            rs.Add(BoneRegions.RegionOf(bone));
                        }
                    }
                }
                bi.pos = ps.ToArray();
                bi.region = rs.ToArray();
                bi.regionCount = bi.region.Distinct().Count();
                return bi;
            }

            public Bounds RegionBounds(string rg)
            {
                Bounds b;
                if (_cache.TryGetValue(rg, out b)) return b;
                b = new Bounds(); bool init = false;
                for (int i = 0; i < region.Length; i++)
                    if (region[i] == rg)
                    {
                        if (init) b.Encapsulate(pos[i]);
                        else { b = new Bounds(pos[i], Vector3.zero); init = true; }
                    }
                _cache[rg] = b;
                return b;
            }
        }

        // ── 骨名 → 身体部位 ──────────────────────────────────────────
        static class BoneRegions
        {
            static readonly Dictionary<HumanBodyBones, string> MAP = new Dictionary<HumanBodyBones, string>();
            static readonly Dictionary<string, HumanBodyBones> NAMES = new Dictionary<string, HumanBodyBones>();

            static BoneRegions()
            {
                Set("头", HumanBodyBones.Head, HumanBodyBones.LeftEye, HumanBodyBones.RightEye);
                Set("颈", HumanBodyBones.Neck);
                Set("胸", HumanBodyBones.Chest, HumanBodyBones.UpperChest,
                    HumanBodyBones.LeftShoulder, HumanBodyBones.RightShoulder);
                Set("腰", HumanBodyBones.Spine);
                Set("臀", HumanBodyBones.Hips);
                Set("上臂", HumanBodyBones.LeftUpperArm, HumanBodyBones.RightUpperArm);
                Set("前臂", HumanBodyBones.LeftLowerArm, HumanBodyBones.RightLowerArm);
                Set("手", HumanBodyBones.LeftHand, HumanBodyBones.RightHand,
                    HumanBodyBones.LeftThumbProximal, HumanBodyBones.LeftThumbIntermediate, HumanBodyBones.LeftThumbDistal,
                    HumanBodyBones.LeftIndexProximal, HumanBodyBones.LeftIndexIntermediate, HumanBodyBones.LeftIndexDistal,
                    HumanBodyBones.LeftMiddleProximal, HumanBodyBones.LeftMiddleIntermediate, HumanBodyBones.LeftMiddleDistal,
                    HumanBodyBones.LeftRingProximal, HumanBodyBones.LeftRingIntermediate, HumanBodyBones.LeftRingDistal,
                    HumanBodyBones.LeftLittleProximal, HumanBodyBones.LeftLittleIntermediate, HumanBodyBones.LeftLittleDistal,
                    HumanBodyBones.RightThumbProximal, HumanBodyBones.RightThumbIntermediate, HumanBodyBones.RightThumbDistal,
                    HumanBodyBones.RightIndexProximal, HumanBodyBones.RightIndexIntermediate, HumanBodyBones.RightIndexDistal,
                    HumanBodyBones.RightMiddleProximal, HumanBodyBones.RightMiddleIntermediate, HumanBodyBones.RightMiddleDistal,
                    HumanBodyBones.RightRingProximal, HumanBodyBones.RightRingIntermediate, HumanBodyBones.RightRingDistal,
                    HumanBodyBones.RightLittleProximal, HumanBodyBones.RightLittleIntermediate, HumanBodyBones.RightLittleDistal);
                Set("大腿", HumanBodyBones.LeftUpperLeg, HumanBodyBones.RightUpperLeg);
                Set("小腿", HumanBodyBones.LeftLowerLeg, HumanBodyBones.RightLowerLeg);
                Set("脚", HumanBodyBones.LeftFoot, HumanBodyBones.RightFoot,
                    HumanBodyBones.LeftToes, HumanBodyBones.RightToes);

                // 本工程（Kaguya）实测骨名 → HumanBodyBones
                Names("Hips", HumanBodyBones.Hips, "Spine", HumanBodyBones.Spine, "Chest", HumanBodyBones.Chest,
                      "Neck", HumanBodyBones.Neck, "Head", HumanBodyBones.Head);
                NAMES["eye.L"] = HumanBodyBones.LeftEye; NAMES["eye.R"] = HumanBodyBones.RightEye;
                NAMES["Shoulder_L"] = HumanBodyBones.LeftShoulder; NAMES["Shoulder_R"] = HumanBodyBones.RightShoulder;
                NAMES["Upperarm_L"] = HumanBodyBones.LeftUpperArm; NAMES["Upperarm_R"] = HumanBodyBones.RightUpperArm;
                NAMES["Lowerarm_L"] = HumanBodyBones.LeftLowerArm; NAMES["Lowerarm_R"] = HumanBodyBones.RightLowerArm;
                NAMES["Left Hand"] = HumanBodyBones.LeftHand; NAMES["Right Hand"] = HumanBodyBones.RightHand;
                NAMES["Upperleg_L"] = HumanBodyBones.LeftUpperLeg; NAMES["Upperleg_R"] = HumanBodyBones.RightUpperLeg;
                NAMES["Lowerleg_L"] = HumanBodyBones.LeftLowerLeg; NAMES["Lowerleg_R"] = HumanBodyBones.RightLowerLeg;
                NAMES["Foot_L"] = HumanBodyBones.LeftFoot; NAMES["Foot_R"] = HumanBodyBones.RightFoot;
                NAMES["Toe_L"] = HumanBodyBones.LeftToes; NAMES["Toe_R"] = HumanBodyBones.RightToes;
                string[] fingers = { "Thumb", "Index", "Middle", "Ring", "Little" };
                string[] segs = { "Proximal", "Intermediate", "Distal" };
                foreach (var side in new[] { "L", "R" })
                    foreach (var fi in fingers)
                        foreach (var sg in segs)
                        {
                            HumanBodyBones hb;
                            if (Enum.TryParse((side == "L" ? "Left" : "Right") + fi + sg, out hb))
                                NAMES[fi + " " + sg + "_" + side] = hb;
                        }
            }

            static void Set(string r, params HumanBodyBones[] bs)
            {
                foreach (var b in bs) MAP[b] = r;
            }

            // 用 Animator 的人形骨映射把「骨名 → HumanBodyBones」补全（换素体不用改下面的表）。
            // 撞过：Milfy 的 `Upper_arm.L` / `Lower_leg.L` / `Hand.L` 不在旧表里，RegionOf 沿父链
            // 退化成 Chest/Hips —— 于是袜子被标成「臀」、鞋被标成「臀」，整套取景的身体上下文全错。
            public static void RegisterHumanoid(Animator an)
            {
                if (an == null || !an.isHuman) return;
                foreach (HumanBodyBones hb in Enum.GetValues(typeof(HumanBodyBones)))
                {
                    if (hb == HumanBodyBones.LastBone) continue;
                    var t = an.GetBoneTransform(hb);
                    if (t != null && !NAMES.ContainsKey(t.name)) NAMES[t.name] = hb;
                }
            }

            static void Names(string n, HumanBodyBones b, string n2, HumanBodyBones b2,
                              string n3, HumanBodyBones b3, string n4, HumanBodyBones b4,
                              string n5, HumanBodyBones b5)
            {
                NAMES[n] = b; NAMES[n2] = b2; NAMES[n3] = b3; NAMES[n4] = b4; NAMES[n5] = b5;
            }

            public static string RegionOf(Transform bone)
            {
                for (var t = bone; t != null; t = t.parent)
                {
                    HumanBodyBones hb;
                    string r;
                    if (NAMES.TryGetValue(t.name, out hb) && MAP.TryGetValue(hb, out r)) return r;
                    // 厂商服装自带的骨架名常带部件后缀（Modular Avatar 就按 `骨名(部件名)` 合并回素体），
                    // 去掉尾部括号再试一次。撞过：00capettiya 四套的 `Hand.L(KemoHandMB)` 全落「其它」，
                    // 连取景的身体上下文都丢了（整套图退化成只框部件）。
                    string bare = BareName(t.name);
                    if (bare != t.name && NAMES.TryGetValue(bare, out hb) && MAP.TryGetValue(hb, out r)) return r;
                }
                return "其它";
            }

            static string BareName(string n)
            {
                int p = n.IndexOf('(');
                return p > 0 ? n.Substring(0, p) : n;
            }
        }

        // ── 克隆状态快照 ─────────────────────────────────────────────
        class CloneSnapshot
        {
            public GameObject root;
            public Dictionary<GameObject, bool> defActive = new Dictionary<GameObject, bool>();
            public Dictionary<Renderer, bool> defEnabled = new Dictionary<Renderer, bool>();
            public Renderer[] renderers;
            public ParticleSystem[] particles;
            public Renderer[] outfitRenderers;
            public List<Renderer> bodyRenderers = new List<Renderer>();
            public GameObject outfitRoot;

            public CloneSnapshot(GameObject clone)
            {
                root = clone;
                foreach (var t in clone.GetComponentsInChildren<Transform>(true))
                    defActive[t.gameObject] = t.gameObject.activeSelf;
                renderers = clone.GetComponentsInChildren<Renderer>(true);
                particles = clone.GetComponentsInChildren<ParticleSystem>(true);
                foreach (var r in renderers) defEnabled[r] = r.enabled;
                foreach (var nm in _bodyRoots)
                {
                    var t = FindTransform(clone.transform, nm);
                    if (t != null) foreach (var r in t.GetComponentsInChildren<Renderer>(true)) bodyRenderers.Add(r);
                }
            }

            public void SetOutfit(Transform ot)
            {
                outfitRoot = ot.gameObject;
                outfitRenderers = ot.GetComponentsInChildren<Renderer>(true)
                    .Where(r => r is SkinnedMeshRenderer || r is MeshRenderer).ToArray();
            }

            public void ResetAll()
            {
                foreach (var kv in defActive) if (kv.Key != null && kv.Key.activeSelf != kv.Value) kv.Key.SetActive(kv.Value);
                foreach (var kv in defEnabled) if (kv.Key != null && kv.Key.enabled != kv.Value) kv.Key.enabled = kv.Value;
            }

            public void ActivateChain(GameObject go)
            {
                for (var t = go.transform; t != null; t = t.parent)
                {
                    if (!t.gameObject.activeSelf) t.gameObject.SetActive(true);
                    if (t.gameObject == root) break;
                }
            }
        }

        // 克隆之外，场景里其它对象（尤其是克隆正后方那台原头像、乃至另一台在编辑的头像）在正交
        // 侧视里会被一起拍到。这里把「非克隆」的所有 Renderer（含 ParticleSystemRenderer）与
        // ParticleSystem 一律关掉，跑完原样恢复；层级 md5 只哈希 name/activeSelf/localPosition，
        // 不开关 Renderer，所以不受影响。
        class SceneHide
        {
            readonly List<Renderer> _rs = new List<Renderer>();
            readonly List<bool> _re = new List<bool>();
            readonly List<ParticleSystem> _ps = new List<ParticleSystem>();
            readonly List<bool> _pp = new List<bool>();

            public int ParticleCount { get { return _ps.Count; } }
            public int RestoredCount { get { return _rs.Count; } }

            public int Hide(GameObject clone)
            {
                var scene = UnityEngine.SceneManagement.SceneManager.GetActiveScene();
                foreach (var go in scene.GetRootGameObjects())
                {
                    if (go == clone) continue;                       // 克隆自己由 CloneSnapshot 白名单管
                    foreach (var r in go.GetComponentsInChildren<Renderer>(true))
                    {
                        _rs.Add(r); _re.Add(r.enabled); r.enabled = false;
                    }
                    foreach (var p in go.GetComponentsInChildren<ParticleSystem>(true))
                    {
                        _ps.Add(p); _pp.Add(p.isPlaying);
                        p.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
                    }
                }
                return _rs.Count;
            }

            public void Restore()
            {
                for (int i = 0; i < _rs.Count; i++) if (_rs[i] != null) _rs[i].enabled = _re[i];
                for (int i = 0; i < _ps.Count; i++) if (_ps[i] != null && _pp[i]) _ps[i].Play();
            }
        }

        // ── 渲染影棚 ─────────────────────────────────────────────────
        class PacStudio
        {
            List<(Light l, bool on)> _lights = new List<(Light, bool)>();
            AmbientMode _am; Color _ac; float _ai; Material _sky;
            GameObject _rig;
            Camera _cam;
            Light _key, _fill;

            public Texture2D Last;

            public void Setup()
            {
                foreach (var l in Resources.FindObjectsOfTypeAll<Light>())
                    if (l.gameObject.scene.IsValid()) { _lights.Add((l, l.enabled)); l.enabled = false; }
                _am = RenderSettings.ambientMode; _ac = RenderSettings.ambientLight;
                _ai = RenderSettings.ambientIntensity; _sky = RenderSettings.skybox;
                RenderSettings.ambientMode = AmbientMode.Flat;
                RenderSettings.ambientLight = new Color(0.42f, 0.42f, 0.46f);
                RenderSettings.ambientIntensity = 1f;
                RenderSettings.skybox = null;

                _rig = new GameObject("~PartAtlasRig") { hideFlags = HideFlags.HideAndDontSave };
                _key = MakeKey(_rig, 1.05f, new Color(1f, 0.98f, 0.95f));
                _fill = MakeKey(_rig, 0.42f, new Color(0.85f, 0.90f, 1.00f));

                var cgo = new GameObject("~PartAtlasCam") { hideFlags = HideFlags.HideAndDontSave };
                cgo.transform.SetParent(_rig.transform);
                _cam = cgo.AddComponent<Camera>();
                _cam.orthographic = true;
                _cam.nearClipPlane = 0.005f;
                _cam.farClipPlane = 200f;
                _cam.clearFlags = CameraClearFlags.SolidColor;
                _cam.backgroundColor = new Color(0.235f, 0.235f, 0.255f);
                _cam.allowHDR = false;
                _cam.allowMSAA = true;
                _cam.cullingMask = ~0;
            }

            static Light MakeKey(GameObject parent, float I, Color c)
            {
                var g = new GameObject("k") { hideFlags = HideFlags.HideAndDontSave };
                g.transform.SetParent(parent.transform);
                var l = g.AddComponent<Light>();
                l.type = LightType.Directional;
                l.intensity = I;
                l.color = c;
                l.shadows = LightShadows.None;
                return l;
            }

            public void Restore()
            {
                if (_rig != null) UnityEngine.Object.DestroyImmediate(_rig);
                foreach (var lp in _lights) if (lp.l != null) lp.l.enabled = lp.on;
                RenderSettings.ambientMode = _am;
                RenderSettings.ambientLight = _ac;
                RenderSettings.ambientIntensity = _ai;
                RenderSettings.skybox = _sky;
            }

            public void Shoot(Vector3 target, Vector3 dirToCam, float ortho)
            {
                dirToCam = dirToCam.normalized;
                float dist = Mathf.Max(2f, ortho * 6f);
                var camGo = _cam.gameObject;
                camGo.transform.position = target + dirToCam * dist;
                var rot = Quaternion.LookRotation(-dirToCam, Vector3.up);
                camGo.transform.rotation = rot;
                _cam.orthographicSize = ortho;
                _cam.aspect = 1f;
                _cam.farClipPlane = dist + 50f;
                // 灯光随相机转，保证每个视角曝光一致
                _key.transform.rotation = rot * Quaternion.Euler(28f, 25f, 0f);
                _fill.transform.rotation = rot * Quaternion.Euler(12f, -35f, 0f);

                var rt = new RenderTexture(RES, RES, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB)
                { antiAliasing = 8 };
                var prev = RenderTexture.active;
                try
                {
                    _cam.targetTexture = rt;
                    _cam.Render();
                    RenderTexture.active = rt;
                    var tex = new Texture2D(RES, RES, TextureFormat.RGB24, false, false);
                    tex.ReadPixels(new Rect(0, 0, RES, RES), 0, 0);
                    tex.Apply(false);
                    Last = tex;
                }
                finally
                {
                    RenderTexture.active = prev;
                    _cam.targetTexture = null;
                    rt.Release();
                    UnityEngine.Object.DestroyImmediate(rt);
                }
            }
        }

        // ── 厂商信息采集 ─────────────────────────────────────────────
        class VendorData
        {
            public List<string> menuTreeLines = new List<string>();
            public List<string> menuInstallers = new List<string>();
            public List<string> parameters = new List<string>();
            public List<string> toggleComps = new List<string>();
            public List<string> shapeDrivers = new List<string>();
            public List<string> scanDirs = new List<string>();
            public List<string> variants = new List<string>();
            public List<string> sceneMenuTree = new List<string>();
            public int clipHitCount;
            public Dictionary<string, List<string>> clipCurvesByPath = new Dictionary<string, List<string>>();
            public Dictionary<string, List<string>> clipMenuItemsByPath = new Dictionary<string, List<string>>();
            public Dictionary<string, List<string>> menuItemsByParam = new Dictionary<string, List<string>>();
        }

        static class VendorInfo
        {
            public static VendorData Collect(PacOutfit o, string srcPrefab, string[] commonDirs, Renderer[] renderers,
                                             GameObject sceneAvatar)
            {
                var v = new VendorData();
                var dirs = new List<string>();
                if (commonDirs != null)
                    foreach (var d in commonDirs) if (!string.IsNullOrEmpty(d) && !dirs.Contains(d)) dirs.Add(d);
                if (!string.IsNullOrEmpty(srcPrefab))
                {
                    string d = Path.GetDirectoryName(srcPrefab).Replace('\\', '/');
                    if (!dirs.Contains(d)) dirs.Add(d);
                }
                v.scanDirs = dirs;

                if (!string.IsNullOrEmpty(srcPrefab))
                {
                    var go = AssetDatabase.LoadAssetAtPath<GameObject>(srcPrefab);
                    if (go != null) CollectPrefabComps(go, v);
                    v.variants = VariantDiff(srcPrefab, renderers);
                }

                // 场景头像自己的菜单（工程自建，不是厂商的）——只用来把 clip 的控制器参数落到具体菜单项名上，
                // 出处用 `[场景]` 前缀标出，避免与 `[厂商]` 混为一谈。
                // 注意：最终菜单挂在 MA MenuInstaller 的 menuToAppend 上（实测 descriptor.expressionsMenu
                // = A2_Base 是空根，控件数为 0），所以两处都走一遍。
                if (sceneAvatar != null)
                {
                    var seenScene = new HashSet<VRC.SDK3.Avatars.ScriptableObjects.VRCExpressionsMenu>();
                    var d = sceneAvatar.GetComponent<VRC.SDK3.Avatars.Components.VRCAvatarDescriptor>();
                    if (d != null && d.expressionsMenu != null)
                        WalkMenu(d.expressionsMenu, v.sceneMenuTree, 0, seenScene, v.menuItemsByParam, "[场景] ");
                    foreach (var c in sceneAvatar.GetComponentsInChildren<Component>(true))
                    {
                        if (c == null) continue;
                        if (c.GetType().FullName != "nadena.dev.modular_avatar.core.ModularAvatarMenuInstaller") continue;
                        var menu = Field(c.GetType(), c, "menuToAppend")
                            as VRC.SDK3.Avatars.ScriptableObjects.VRCExpressionsMenu;
                        if (menu != null)
                            WalkMenu(menu, v.sceneMenuTree, 0, seenScene, v.menuItemsByParam, "[场景] ");
                    }
                }

                ScanClips(v, renderers);
                return v;
            }

            static void CollectPrefabComps(GameObject go, VendorData v)
            {
                var seenMenu = new HashSet<VRC.SDK3.Avatars.ScriptableObjects.VRCExpressionsMenu>();
                foreach (var c in go.GetComponentsInChildren<Component>(true))
                {
                    if (c == null) continue;
                    string tn = c.GetType().FullName ?? "";
                    if (tn == "nadena.dev.modular_avatar.core.ModularAvatarMenuInstaller")
                    {
                        var t = c.GetType();
                        var menu = Field(t, c, "menuToAppend") as VRC.SDK3.Avatars.ScriptableObjects.VRCExpressionsMenu;
                        var tgt = Field(t, c, "installTargetMenu") as VRC.SDK3.Avatars.ScriptableObjects.VRCExpressionsMenu;
                        string mp = menu != null ? AssetDatabase.GetAssetPath(menu) : "";
                        v.menuInstallers.Add("{\"宿主\": " + Q(c.gameObject.name) + ", \"菜单资产\": " + Q(mp)
                            + ", \"安装到\": " + Q(tgt != null ? tgt.name : "") + "}");
                        if (menu != null) WalkMenu(menu, v.menuTreeLines, 0, seenMenu, v.menuItemsByParam, "[厂商] ");
                    }
                    else if (tn == "nadena.dev.modular_avatar.core.ModularAvatarParameters")
                    {
                        var list = Field(c.GetType(), c, "parameters") as IEnumerable;
                        if (list == null) continue;
                        foreach (var q in list)
                        {
                            var qt = q.GetType();
                            v.parameters.Add("{\"宿主\": " + Q(c.gameObject.name)
                                + ", \"名\": " + Q(Str(qt, q, "nameOrPrefix"))
                                + ", \"默认\": " + Q(Str(qt, q, "defaultValue"))
                                + ", \"同步\": " + Q(Str(qt, q, "syncType"))
                                + ", \"保存\": " + Q(Str(qt, q, "saved")) + "}");
                        }
                    }
                    else if (tn == "nadena.dev.modular_avatar.core.ModularAvatarMenuItem"
                          || tn == "nadena.dev.modular_avatar.core.ModularAvatarObjectToggle"
                          || tn.EndsWith("Toggle"))
                    {
                        v.toggleComps.Add("{\"类型\": " + Q(tn) + ", \"宿主\": " + Q(c.gameObject.name)
                            + ", \"字段\": " + Q(FieldsOf(c)) + "}");
                    }
                    else if (tn.Contains("ModularAvatarShapeChanger") || tn.Contains("ModularAvatarBlendshapeSync"))
                    {
                        v.shapeDrivers.Add("{\"类型\": " + Q(tn) + ", \"宿主\": " + Q(c.gameObject.name) + "}");
                    }
                }
            }

            static void WalkMenu(VRC.SDK3.Avatars.ScriptableObjects.VRCExpressionsMenu menu,
                                 List<string> lines, int depth,
                                 HashSet<VRC.SDK3.Avatars.ScriptableObjects.VRCExpressionsMenu> seen,
                                 Dictionary<string, List<string>> byParam, string tag)
            {
                if (menu == null || !seen.Add(menu)) return;
                foreach (var c in menu.controls)
                {
                    if (c == null) continue;
                    string p = c.parameter != null ? c.parameter.name : "";
                    lines.Add(tag + new string(' ', depth * 2) + "· " + c.name + "  [" + c.type + "]"
                        + (string.IsNullOrEmpty(p) ? "" : "  → " + p));
                    if (!string.IsNullOrEmpty(p))
                        AddMenuParam(byParam, p, tag + menu.name + " / " + c.name + " ← " + p);
                    if (c.subParameters != null)
                        foreach (var sp in c.subParameters)
                            if (sp != null && !string.IsNullOrEmpty(sp.name))
                                AddMenuParam(byParam, sp.name, tag + menu.name + " / " + c.name + " (sub) ← " + sp.name);
                    if (c.type == VRC.SDK3.Avatars.ScriptableObjects.VRCExpressionsMenu.Control.ControlType.SubMenu)
                        WalkMenu(c.subMenu, lines, depth + 1, seen, byParam, tag);
                }
            }

            static void AddMenuParam(Dictionary<string, List<string>> byParam, string p, string item)
            {
                List<string> l;
                if (!byParam.TryGetValue(p, out l)) byParam[p] = l = new List<string>();
                l.Add(item);
            }

            static void ScanClips(VendorData v, Renderer[] renderers)
            {
                var paths = new HashSet<string>();
                foreach (var r in renderers) paths.Add(RelPath(r.transform, r.transform.root));
                if (paths.Count == 0) return;

                var byClipParam = BuildClipParamIndex(v.scanDirs);
                var guids = AssetDatabase.FindAssets("t:AnimationClip");
                foreach (var g in guids)
                {
                    string p = AssetDatabase.GUIDToAssetPath(g);
                    bool inScope = false;
                    foreach (var d in v.scanDirs) if (p.StartsWith(d)) { inScope = true; break; }
                    if (!inScope) continue;
                    var clip = AssetDatabase.LoadAssetAtPath<AnimationClip>(p);
                    if (clip == null) continue;
                    var bindings = AnimationUtility.GetCurveBindings(clip)
                        .Concat<EditorCurveBinding>(AnimationUtility.GetObjectReferenceCurveBindings(clip));
                    foreach (var b in bindings)
                    {
                        if (!paths.Contains(b.path)) continue;
                        string prop = b.propertyName;
                        bool isSwitch = prop == "m_IsActive" || prop == "m_Enabled"
                                     || prop.StartsWith("material.") || prop.StartsWith("m_Materials.Array.data[")
                                     || prop.StartsWith("blendShape.") || prop.StartsWith("m_LocalScale");
                        if (!isSwitch) continue;
                        string val = "?";
                        var curve = AnimationUtility.GetEditorCurve(clip, b);
                        if (curve != null && curve.keys.Length > 0) val = Num(curve.keys[0].value);
                        var objCurve = AnimationUtility.GetObjectReferenceCurve(clip, b);
                        if (objCurve != null && objCurve.Length > 0 && objCurve[0].value != null)
                            val = ((UnityEngine.Object)objCurve[0].value).name;

                        List<string> pars;
                        if (!byClipParam.TryGetValue(clip, out pars)) pars = new List<string>();
                        var menuItems = new List<string>();
                        foreach (var pp in pars)
                        {
                            List<string> mi;
                            if (v.menuItemsByParam.TryGetValue(pp, out mi)) menuItems.AddRange(mi);
                        }
                        List<string> bucket;
                        if (!v.clipCurvesByPath.TryGetValue(b.path, out bucket))
                            v.clipCurvesByPath[b.path] = bucket = new List<string>();
                        // 菜单项同时按路径聚合一份（给「厂商开关引用.命中菜单项」用；不要回头去解析自己写的 JSON 字符串）
                        List<string> mb;
                        if (!v.clipMenuItemsByPath.TryGetValue(b.path, out mb))
                            v.clipMenuItemsByPath[b.path] = mb = new List<string>();
                        foreach (var x in menuItems) if (!mb.Contains(x)) mb.Add(x);
                        bucket.Add("{\"clip\": " + Q(clip.name) + ", \"资产\": " + Q(p)
                            + ", \"属性\": " + Q(prop) + ", \"值\": " + Q(val)
                            + ", \"转入/混合树参数\": " + QArr(pars.Distinct())
                            + ", \"菜单项\": " + QArr(menuItems.Distinct()) + "}");
                        v.clipHitCount++;
                    }
                }
            }

            // clip → 触发它的转移条件参数（扫描目录内的 AnimatorController）
            static Dictionary<AnimationClip, List<string>> BuildClipParamIndex(List<string> scanDirs)
            {
                if (_clipParamCache != null) return _clipParamCache;
                var idx = new Dictionary<AnimationClip, List<string>>();
                // 全工程控制器都扫：厂商 clip 的参数写在厂商自己的 FX 控制器里（实测 kaguya 的
                // `kaguya beret/outer/sailor/...` 参数在 <厂商 FX 控制器路径> none.controller），
                // 只扫服装目录会一个参数都解析不到。289 个控制器，跑一次缓存住。
                foreach (var g in AssetDatabase.FindAssets("t:AnimatorController"))
                {
                    var ac = AssetDatabase.LoadAssetAtPath<AnimatorController>(AssetDatabase.GUIDToAssetPath(g));
                    if (ac != null) WalkSM(ac, idx);
                }
                _clipParamCache = idx;
                return idx;
            }

            // 每份控制器单独跑：`inbound` 是**层内**的，不能跨控制器共享
            static void WalkSM(AnimatorController ac, Dictionary<AnimationClip, List<string>> idx)
            {
                foreach (var layer in ac.layers) WalkSM(layer.stateMachine, idx);
            }

            static void WalkSM(AnimatorStateMachine sm, Dictionary<AnimationClip, List<string>> idx)
            {
                if (sm == null) return;
                var inbound = new Dictionary<AnimatorState, HashSet<string>>();
                foreach (var t in sm.anyStateTransitions) AddTrans(t, null, inbound);
                foreach (var t in sm.entryTransitions) AddTrans(t, null, inbound);
                foreach (var cs in sm.states)
                {
                    if (cs.state == null) continue;
                    foreach (var t in cs.state.transitions) AddTrans(t, cs.state, inbound);
                    AddClipParams(cs.state.motion, cs.state, inbound, idx, null);
                }
                foreach (var csm in sm.stateMachines)
                {
                    if (csm.stateMachine == null) continue;
                    foreach (var t in sm.GetStateMachineTransitions(csm.stateMachine)) AddTrans(t, null, inbound);
                    WalkSM(csm.stateMachine, idx);
                }
            }

            static void AddTrans(AnimatorTransitionBase t, AnimatorState from,
                                 Dictionary<AnimatorState, HashSet<string>> inbound)
            {
                if (t == null || t.conditions == null) return;
                var target = t.destinationState != null ? t.destinationState : from;
                if (target == null) return;
                HashSet<string> s;
                if (!inbound.TryGetValue(target, out s)) inbound[target] = s = new HashSet<string>();
                foreach (var c in t.conditions) if (!string.IsNullOrEmpty(c.parameter)) s.Add(c.parameter);
            }

            // 顺带收 BlendTree 的 blendParameter / Direct 的 directBlendParameter ——
            // 「整套/配色」这类层是用混合树驱动的，没有转移条件，只收转移条件会全空。
            static void AddClipParams(Motion m, AnimatorState st, Dictionary<AnimatorState, HashSet<string>> inbound,
                                      Dictionary<AnimationClip, List<string>> idx, List<string> extra)
            {
                var bt = m as BlendTree;
                if (bt != null)
                {
                    var ex = extra != null ? new List<string>(extra) : new List<string>();
                    if (!string.IsNullOrEmpty(bt.blendParameter)) ex.Add(bt.blendParameter);
                    if (!string.IsNullOrEmpty(bt.blendParameterY)) ex.Add(bt.blendParameterY);
                    foreach (var ch in bt.children)
                    {
                        if (bt.blendType == BlendTreeType.Direct && !string.IsNullOrEmpty(ch.directBlendParameter))
                        {
                            var ex2 = new List<string>(ex); ex2.Add(ch.directBlendParameter);
                            AddClipParams(ch.motion, st, inbound, idx, ex2);
                        }
                        else AddClipParams(ch.motion, st, inbound, idx, ex);
                    }
                    return;
                }
                var clip = m as AnimationClip;
                if (clip == null) return;
                HashSet<string> s;
                if (!inbound.TryGetValue(st, out s)) s = new HashSet<string>();
                List<string> l;
                if (!idx.TryGetValue(clip, out l)) idx[clip] = l = new List<string>();
                foreach (var x in s) if (!l.Contains(x)) l.Add(x);
                if (extra != null) foreach (var x in extra) if (!l.Contains(x)) l.Add(x);
            }
        }

        // ── 颜色变体材质差异 ─────────────────────────────────────────
        static List<string> VariantDiff(string basePrefab, Renderer[] renderers)
        {
            var res = new List<string>();
            if (string.IsNullOrEmpty(basePrefab)) return res;
            string dir = Path.GetDirectoryName(basePrefab).Replace('\\', '/');
            if (!Directory.Exists(dir)) return res;
            var baseMats = new Dictionary<string, string>();
            foreach (var r in renderers) baseMats[r.gameObject.name] = MatsOf(r);
            foreach (var f in Directory.GetFiles(dir, "*.prefab").OrderBy(x => x))
            {
                string ap = f.Replace('\\', '/');
                if (ap == basePrefab) continue;
                var go = AssetDatabase.LoadAssetAtPath<GameObject>(ap);
                if (go == null) continue;
                var diff = new List<string>();
                foreach (var r in go.GetComponentsInChildren<Renderer>(true))
                {
                    if (!(r is SkinnedMeshRenderer || r is MeshRenderer)) continue;
                    string bm;
                    if (!baseMats.TryGetValue(r.gameObject.name, out bm)) continue;
                    if (bm != MatsOf(r)) diff.Add(r.gameObject.name);
                }
                if (diff.Count > 0)
                    res.Add("{\"预制件\": " + Q(ap) + ", \"材质不同的部件\": " + QArr(diff.Distinct()) + "}");
            }
            return res;
        }

        static string MatsOf(Renderer r)
        {
            return string.Join("|", r.sharedMaterials.Select(m => m != null ? m.name : "null"));
        }

        // ── 条目辅助 ─────────────────────────────────────────────────
        static List<string> MatEntries(Renderer r)
        {
            var res = new List<string>();
            foreach (var m in r.sharedMaterials)
            {
                if (m == null) { res.Add("{\"name\": null, \"shader\": null, \"主贴图\": null}"); continue; }
                string main = null;
                try
                {
                    foreach (var p in new[] { "_MainTex", "_BaseMap", "_BaseColorMap" })
                        if (m.HasProperty(p) && m.GetTexture(p) != null) { main = m.GetTexture(p).name; break; }
                    if (main == null && m.shader != null)
                    {
                        int n = ShaderUtil.GetPropertyCount(m.shader);
                        for (int i = 0; i < n; i++)
                            if (ShaderUtil.GetPropertyType(m.shader, i) == ShaderUtil.ShaderPropertyType.TexEnv)
                            {
                                var t = m.GetTexture(ShaderUtil.GetPropertyName(m.shader, i));
                                if (t != null) { main = t.name; break; }
                            }
                    }
                }
                catch { }
                res.Add("{\"name\": " + Q(m.name) + ", \"shader\": " + Q(m.shader != null ? m.shader.name : "")
                    + ", \"主贴图\": " + Q(main) + "}");
            }
            return res;
        }

        static List<string> BlendShapeEntries(Renderer r, Mesh mesh)
        {
            var res = new List<string>();
            var s = r as SkinnedMeshRenderer;
            if (mesh == null || s == null) return res;
            for (int i = 0; i < mesh.blendShapeCount; i++)
            {
                float w = 0f;
                try { w = s.GetBlendShapeWeight(i); } catch { }
                res.Add("{\"名\": " + Q(mesh.GetBlendShapeName(i)) + ", \"权重\": " + Num(w) + "}");
            }
            return res;
        }

        static List<string> ImageNames(string outDir, int idx, string safe)
        {
            var res = new List<string>();
            if (!Directory.Exists(outDir)) return res;
            foreach (var f in Directory.GetFiles(outDir, string.Format("{0:D2}_{1}_*.png", idx, safe)).OrderBy(x => x))
                res.Add(Path.GetFileName(f));
            return res;
        }

        static string VendorRefs(string rel)
        {
            var v = _curVendor;
            if (v == null) return "{\"说明\": \"未采集\"}";
            List<string> curves;
            v.clipCurvesByPath.TryGetValue(rel, out curves);
            if (curves == null) curves = new List<string>();
            List<string> menu;
            v.clipMenuItemsByPath.TryGetValue(rel, out menu);
            if (menu == null) menu = new List<string>();
            return "{\"预制件组件\": []"
                + ", \"动画clip曲线\": [" + string.Join(", ", curves) + "]"
                + ", \"命中菜单项\": " + QArr(menu)
                + ", \"口径\": " + Q("曲线只收目标路径上的 m_IsActive/m_Enabled/material.*/m_Materials.*/blendShape.*/m_LocalScale；" +
                                      "「命中菜单项」= 曲线所在状态的转移条件/混合树参数，经「[厂商] 厂商菜单」与「[场景] 场景头像菜单」反查到的菜单项名（含参数名）；" +
                                      "预制件里的 MA MenuItem/ObjectToggle/Toggle 组件见套装级「厂商开关组件」，菜单原文见「厂商菜单树」") + "}";
        }

        // ── 通用小工具 ───────────────────────────────────────────────
        static object Field(Type t, object o, string name)
        {
            var f = t.GetField(name);
            return f != null ? f.GetValue(o) : null;
        }

        static string Str(Type t, object o, string name)
        {
            var v = Field(t, o, name);
            if (v == null) return "";
            try { return v.ToString(); } catch { return "(取值失败)"; }
        }

        static string FieldsOf(Component c)
        {
            var parts = new List<string>();
            foreach (var f in c.GetType().GetFields(System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.Instance))
            {
                object val = null;
                try { val = f.GetValue(c); } catch { }
                if (val == null) { parts.Add(f.Name + "=null"); continue; }
                var vt = val.GetType();
                if (vt.IsPrimitive || vt == typeof(string)) parts.Add(f.Name + "=" + val);
                else if (val is UnityEngine.Object)
                {
                    // 未指派的序列化引用（fake-null）读 .name 会抛 UnassignedReferenceException，
                    // 必须先用 Unity 的 == 判空（撞过：MA `ModularAvatarMenuItem.menuSource_otherObjectChildren`）
                    var uo = (UnityEngine.Object)val;
                    if (uo == null) parts.Add(f.Name + "=null(未指派)");
                    else { string nm; try { nm = uo.name; } catch { nm = "(取名字失败)"; } parts.Add(f.Name + "=" + nm); }
                }
                else parts.Add(f.Name + "<" + vt.Name + ">");
            }
            return string.Join(", ", parts);
        }

        static GameObject FindByName(GameObject[] roots, string name)
        {
            foreach (var g in roots) if (g.name == name) return g;
            foreach (var g in roots) { var t = FindTransform(g.transform, name); if (t != null) return t.gameObject; }
            return null;
        }

        static Transform FindTransform(Transform root, string name)
        {
            if (name == null) return root;
            if (root.name == name) return root;
            for (int i = 0; i < root.childCount; i++)
            {
                var t = FindTransform(root.GetChild(i), name);
                if (t != null) return t;
            }
            return null;
        }

        // 服装根解析：spec 含 '/' 时按「相对 root 的路径」解析（`_Outfit/1` 这种名字会撞车，
        // 例：Peridot 的 `_Outfit/1` 与手机模型里的 `1` 同名，按名字找会先命中手机）；
        // 不含 '/' 时退回原来的「整棵子树按名字找」。
        static Transform ResolveTransform(Transform root, string spec)
        {
            if (string.IsNullOrEmpty(spec)) return root;
            if (spec.IndexOf('/') >= 0) return root.Find(spec);
            return FindTransform(root, spec);
        }

        static string RelPath(Transform t, Transform stop)
        {
            var parts = new List<string>();
            for (var p = t; p != null && p != stop; p = p.parent) parts.Add(p.name);
            parts.Reverse();
            return string.Join("/", parts);
        }

        static string LastTwo(string rel)
        {
            var parts = rel.Split('/');
            return parts.Length <= 2 ? rel : parts[parts.Length - 2] + "/" + parts[parts.Length - 1];
        }

        static List<string> ChainActive(Transform t)
        {
            var res = new List<string>();
            for (var p = t.parent; p != null; p = p.parent)
                res.Add(p.name + "=" + (p.gameObject.activeSelf ? "1" : "0"));
            res.Reverse();
            return res;
        }

        static string Safe(string s)
        {
            var sb = new StringBuilder();
            foreach (char c in s)
            {
                if (char.IsLetterOrDigit(c) || c == '-' || c == '_' || c == '.' || c > 127) sb.Append(c);
                else sb.Append('_');
            }
            return sb.ToString().Trim('_');
        }

        static string Manifest(UnityEngine.SceneManagement.Scene scene)
        {
            var sb = new StringBuilder();
            foreach (var g in scene.GetRootGameObjects().OrderBy(x => x.name))
                WalkManifest(g.transform, "", sb);
            return sb.ToString();
        }

        static void WalkManifest(Transform t, string prefix, StringBuilder sb)
        {
            sb.Append(prefix).Append(t.name).Append('|').Append(t.gameObject.activeSelf ? '1' : '0')
              .Append('|').Append(F3(t.localPosition)).Append('\n');
            foreach (var c in t.Cast<Transform>().OrderBy(x => x.GetSiblingIndex()))
                WalkManifest(c, prefix + "  ", sb);
        }

        static string RootList(UnityEngine.SceneManagement.Scene scene)
        {
            return string.Join(", ", scene.GetRootGameObjects().OrderBy(x => x.name)
                .Select(g => g.name + "(" + g.activeSelf + ")"));
        }

        static string Md5(string s)
        {
            using (var md5 = MD5.Create())
                return BitConverter.ToString(md5.ComputeHash(Encoding.UTF8.GetBytes(s))).Replace("-", "").ToLowerInvariant();
        }

        static string Md5File(string path)
        {
            if (!File.Exists(path)) return "(缺文件)";
            using (var md5 = MD5.Create())
            using (var fs = File.OpenRead(path))
                return BitConverter.ToString(md5.ComputeHash(fs)).Replace("-", "").ToLowerInvariant();
        }

        static string F3(Vector3 v) { return "(" + Num(v.x) + "," + Num(v.y) + "," + Num(v.z) + ")"; }
        static string V3(Vector3 v) { return "[" + Num(v.x) + ", " + Num(v.y) + ", " + Num(v.z) + "]"; }
        static string Num(float f) { return f.ToString("0.#####", CultureInfo.InvariantCulture); }

        static string Q(string s)
        {
            if (s == null) return "null";
            var sb = new StringBuilder("\"");
            foreach (char c in s)
            {
                switch (c)
                {
                    case '"': sb.Append("\\\""); break;
                    case '\\': sb.Append("\\\\"); break;
                    case '\n': sb.Append("\\n"); break;
                    case '\r': sb.Append("\\r"); break;
                    case '\t': sb.Append("\\t"); break;
                    default:
                        if (c < 0x20) sb.Append("\\u").Append(((int)c).ToString("x4"));
                        else sb.Append(c);
                        break;
                }
            }
            return sb.Append('"').ToString();
        }

        static string QArr(IEnumerable<string> xs)
        {
            return "[" + string.Join(", ", xs.Select(Q)) + "]";
        }

        static List<string> ListVendorImages(string dir)
        {
            var res = new List<string>();
            try
            {
                if (!string.IsNullOrEmpty(dir) && Directory.Exists(dir))
                    foreach (var f in Directory.GetFiles(dir).OrderBy(x => x)) res.Add(f);
            }
            catch { }
            return res;
        }
    }
}
