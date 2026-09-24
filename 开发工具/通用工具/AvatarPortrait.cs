// ══════════════════════════════════════════════════════════════════
// 【项目沉淀】通用工具
// 适用素体：人形素体（有 Humanoid Animator 的都行，没有则退回包围盒）
// 相关素材：无
// 工具链　：Unity 2022.3.22f1 / VRChat SDK 3.10.x
// 可复用性：★★★ 换个单子直接能用
// 用途　　：自带相机与布光，渲染角色形象定妆照（正面/四分之三/背面/面部）+ 规格 JSON
//           可在 GUI 里走菜单，也可在 -batchmode 下走 -executeMethod，无人值守批量跑
// ══════════════════════════════════════════════════════════════════
// 与 SceneViewShots 的分工：那个是「同机位 A/B 对比」，依赖 SceneView，批处理下用不了；
// 这个是「离屏渲染定妆照」，自建 Camera + RenderTexture，不受编辑器视图状态影响，
// 也不会把工具栏/坐标球/网格拍进画面。
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Profiling;
using UnityEngine.Rendering;

namespace AvatarGen
{
    public static class AvatarPortrait
    {
        // ── 命令行参数 ───────────────────────────────────────────────
        // Overrides 让别的编辑器脚本能在交互模式下驱动本工具（批处理下没人设它，行为不变）。
        // 组合截图验收要连拍几十张，不可能每张开一次 Unity。
        public static readonly Dictionary<string, string> Overrides = new Dictionary<string, string>();

        static string Arg(string key, string def)
        {
            if (Overrides.TryGetValue(key, out var ov)) return ov;
            string[] a = Environment.GetCommandLineArgs();
            for (int i = 0; i < a.Length - 1; i++) if (a[i] == key) return a[i + 1];
            return def;
        }

        [MenuItem("Tools/AvatarGen/Portrait - 渲染定妆照")]
        public static void RunMenu() { Run(); }

        // batchmode 入口：-executeMethod AvatarGen.AvatarPortrait.Run
        //   -portraitOut   <绝对目录>     输出目录（默认 <工程>/Captures/Portrait）
        //   -portraitScene <Assets/x.unity> 先打开这个场景（默认用当前已打开的）
        //   -portraitTag   <前缀>         文件名前缀（默认工程文件夹名）
        public static void Run()
        {
            string outDir = Arg("-portraitOut", Path.Combine(Directory.GetCurrentDirectory(), "Captures/Portrait"));
            string scene  = Arg("-portraitScene", null);
            string tag    = Arg("-portraitTag", new DirectoryInfo(Directory.GetCurrentDirectory()).Name);
            Directory.CreateDirectory(outDir);

            var log = new StringBuilder();
            void L(string s) { log.AppendLine(s); Debug.Log("[Portrait] " + s); }

            try
            {
                if (!string.IsNullOrEmpty(scene))
                {
                    L("open scene: " + scene);
                    EditorSceneManager.OpenScene(scene, OpenSceneMode.Single);
                }
                L("scene = " + UnityEngine.SceneManagement.SceneManager.GetActiveScene().path);

                var descs = Resources.FindObjectsOfTypeAll<VRC.SDK3.Avatars.Components.VRCAvatarDescriptor>()
                    .Where(d => d != null && d.gameObject.scene.IsValid())
                    .ToArray();
                L("descriptors found = " + descs.Length);
                if (descs.Length == 0) { L("NO AVATAR"); Flush(outDir, tag, log); return; }

                // 场景里常有多台头像（面捕版 / Quest 版 / 厂商样例），而且往往都摆在原点。
                // 不做隔离的话，别的头像会一起入镜、还会把自动取景的外接框撑大。
                // 所以：逐台拍，拍谁就只留谁激活，拍完全部还原。
                var roots = descs.Select(d => d.gameObject).Distinct().ToArray();
                var wasActive = roots.ToDictionary(g => g, g => g.activeSelf);
                foreach (var kv in wasActive) if (!kv.Value) L("inactive avatar (will shoot front only): " + kv.Key.name);

                var studio = new Studio();
                studio.Setup();
                var hidden = new List<Renderer>();
                var dressedOn = new List<GameObject>();
                var reEnabled = new List<Renderer>();
                try
                {
                    for (int idx = 0; idx < roots.Length; idx++)
                    {
                        var target = roots[idx];
                        foreach (var g in roots) g.SetActive(g == target);
                        Dress(target, dressedOn, reEnabled, L);   // 先穿衣，再屏蔽标记
                        HideNonCharacter(target, hidden, L);
                        bool orig = wasActive[target];
                        string nm = Sanitize(target.name);
                        string prefix = roots.Length > 1 ? $"{tag}_{idx:00}_{nm}" : $"{tag}_{nm}";
                        if (!orig) prefix += "_[未激活]";
                        L($"--- avatar[{idx}] {target.name}  原本激活={orig}");
                        try { Shoot(target, outDir, prefix, L, frontOnly: !orig); }
                        catch (Exception e) { L("SHOOT FAILED: " + e); }
                        try
                        {
                            File.WriteAllText(Path.Combine(outDir, prefix + ".json"),
                                Spec(descs.First(d => d.gameObject == target), orig), new UTF8Encoding(false));
                        }
                        catch (Exception e) { L("SPEC FAILED: " + e); }
                    }
                }
                finally
                {
                    studio.Restore();
                    foreach (var r in hidden) if (r != null) r.enabled = true;
                    foreach (var r in reEnabled) if (r != null) r.enabled = false;
                    foreach (var g in dressedOn) if (g != null) g.SetActive(false);
                    foreach (var kv in wasActive) if (kv.Key != null) kv.Key.SetActive(kv.Value);
                }
            }
            catch (Exception e) { log.AppendLine("FATAL: " + e); }

            Flush(outDir, tag, log);
        }

        static void Flush(string outDir, string tag, StringBuilder log)
        {
            try { File.WriteAllText(Path.Combine(outDir, tag + "_portrait.log"), log.ToString(), new UTF8Encoding(false)); }
            catch { }
        }

        static string Sanitize(string s)
        {
            foreach (char c in Path.GetInvalidFileNameChars()) s = s.Replace(c, '_');
            return s.Replace(' ', '_');
        }

        // ── 影棚：接管布光，拍完还原 ─────────────────────────────────
        // 工程自带的灯光千差万别（有的没灯、有的三盏补光把 lilToon 打到全白），
        // 直接用原场景光照，14 个工程的图没有可比性。所以统一布光。
        // internal（而非默认 private）：工程C 30a-1 候选渲图需要跨多组候选复用
        // 同一套灯光（不重复 Setup/Restore），从 CommCSetup 里直接 new 这个类。
        internal class Studio
        {
            List<(Light l, bool on)> _lights = new List<(Light, bool)>();
            AmbientMode _am; Color _ac; float _ai; Material _sky; GameObject _rig;

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

                _rig = new GameObject("~PortraitRig") { hideFlags = HideFlags.HideAndDontSave };
                Key(_rig, new Vector3(28f, 205f, 0f), 1.05f, new Color(1f, 0.98f, 0.95f));  // 主光，斜上前方
                Key(_rig, new Vector3(12f, 25f, 0f), 0.42f, new Color(0.85f, 0.90f, 1.00f)); // 背侧补光
            }
            static void Key(GameObject parent, Vector3 euler, float I, Color c)
            {
                var g = new GameObject("k") { hideFlags = HideFlags.HideAndDontSave };
                g.transform.SetParent(parent.transform);
                g.transform.rotation = Quaternion.Euler(euler);
                var l = g.AddComponent<Light>();
                l.type = LightType.Directional; l.intensity = I; l.color = c; l.shadows = LightShadows.None;
            }
            public void Restore()
            {
                if (_rig != null) UnityEngine.Object.DestroyImmediate(_rig);
                foreach (var (l, on) in _lights) if (l != null) l.enabled = on;
                RenderSettings.ambientMode = _am; RenderSettings.ambientLight = _ac;
                RenderSettings.ambientIntensity = _ai; RenderSettings.skybox = _sky;
            }
        }

        // ── 屏蔽不属于「角色形象」的东西 ─────────────────────────────
        // 三类：① 编辑器专用预览物（VRCFury/SPS 的 socket 标记走 hideFlags，会在画面上
        // 印出红色 TARGET 方块）② 按名字/材质命中的标记 ③ 命令行 -portraitHide 点名排除的道具
        // （例如 Eku 那把 Umbrella_R，占满画面把角色挤成一个点）。
        // 命中的是「自身或任一祖先」的名字 —— 标记通常挂在一个成组的父物体下，
        // 例如 PCS 的 `<PCS Target> Boobs`、面捕的 `Face Tracking`（里面那个绿色头显占位）。
        static readonly string[] MARKER_HINTS = {
            "<pcs ", "pcs contacts", "pcs preview icon", "pcs particle", "pcs target",
            "face tracking", "spssocketmarker", "spsscreenmarker", "spsdatagrabpass",
            "vrcfury hidden", "socketmarker", "plugmarker", "target objects",
            "eyemask", "sleepeyemask", "lockdev"
        };
        static string Chain(Transform t)
        {
            var sb = new StringBuilder();
            for (var p = t; p != null; p = p.parent) sb.Append('/').Append(p.name.ToLowerInvariant());
            return sb.ToString();
        }
        internal static void HideNonCharacter(GameObject root, List<Renderer> hidden, Action<string> L)
        {
            string[] extra = Arg("-portraitHide", "")
                .Split(new[] { ';' }, StringSplitOptions.RemoveEmptyEntries)
                .Select(s => s.Trim().ToLowerInvariant()).Where(s => s.Length > 0).ToArray();

            int a = 0, b = 0, c = 0;
            foreach (var r in root.GetComponentsInChildren<Renderer>(false))
            {
                if (!r.enabled) continue;
                bool hide = false; string why = null;
                string chain = Chain(r.transform);

                if (r.gameObject.hideFlags != HideFlags.None) { hide = true; why = "hideFlags=" + r.gameObject.hideFlags; a++; }

                if (!hide)
                {
                    string probe = chain;
                    foreach (var m in r.sharedMaterials)
                    {
                        if (m == null) continue;
                        probe += "|" + m.name.ToLowerInvariant();
                        if (m.shader != null) probe += "|" + m.shader.name.ToLowerInvariant();
                    }
                    foreach (var h in MARKER_HINTS)
                        if (probe.Contains(h)) { hide = true; why = "marker:" + h; b++; break; }
                }

                // 前缀 `=` 表示精确匹配渲染器自身的名字。素体默认发型就叫 `Hair`，
                // 用子串匹配会把 `Hair_GoldenHour` 一起干掉。
                if (!hide && extra.Length > 0)
                {
                    string self = r.gameObject.name.ToLowerInvariant();
                    foreach (var e in extra)
                    {
                        bool m = e.StartsWith("=") ? self == e.Substring(1) : chain.Contains(e);
                        if (m) { hide = true; why = "-portraitHide:" + e; c++; break; }
                    }
                }

                if (hide) { r.enabled = false; hidden.Add(r); L($"    hide {r.gameObject.name}  ({why})"); }
            }
            if (a + b + c > 0) L($"    已屏蔽 {a + b + c} 个渲染器（编辑器专用 {a} / 标记 {b} / 点名 {c}）");
        }

        // ── 显式穿衣：把点名的部件打开 ───────────────────────────────
        // 换装工程编辑期常把整柜衣服都关着（成品形态是运行时由 FX 层组装的），
        // 直接拍会拍出光身子。全开又会把互斥的两套叠在一起（Rurune 有 cloth 和 swim 两套）。
        // 所以只认 `-portraitDress "名1;名2"` 点名，选了哪几件写进日志，可审计。
        internal static void Dress(GameObject root, List<GameObject> turnedOn, List<Renderer> reEnabled, Action<string> L)
        {
            string[] want = Arg("-portraitDress", "")
                .Split(new[] { ';' }, StringSplitOptions.RemoveEmptyEntries)
                .Select(s => s.Trim().ToLowerInvariant()).Where(s => s.Length > 0).ToArray();
            if (want.Length == 0) return;
            int n = 0;
            foreach (var t in root.GetComponentsInChildren<Transform>(true))
            {
                string nm = t.name.ToLowerInvariant();
                if (!want.Contains(nm)) continue;
                if (!t.gameObject.activeSelf) { t.gameObject.SetActive(true); turnedOn.Add(t.gameObject); n++; L($"    dress ON  {t.name}"); }
                foreach (var r in t.GetComponentsInChildren<Renderer>(true))
                    if (!r.enabled) { r.enabled = true; reEnabled.Add(r); }
            }
            L($"    穿衣：点名 {want.Length} 项，实际打开 {n} 个物体");
        }

        // ── 量身高：骨骼优先，蒙皮包围盒只作兜底 ─────────────────────
        // 沿用 SceneViewShots 的判据：SkinnedMeshRenderer.bounds 常年虚报（实测 0.755m 的
        // 素体报到 2.24m），Head/Foot 骨骼世界坐标才是准的。
        internal static bool Measure(GameObject root, out float H, out float footY, out Transform head, out Vector3 c)
        {
            H = 0; footY = 0; head = null; c = Vector3.zero;
            var an = root.GetComponent<Animator>();
            Transform foot = null;
            if (an != null && an.isHuman)
            {
                head = an.GetBoneTransform(HumanBodyBones.Head);
                foot = an.GetBoneTransform(HumanBodyBones.LeftFoot);
            }
            if (head == null)
                foreach (Transform t in root.GetComponentsInChildren<Transform>(true))
                    if (t.name.ToLower() == "head") { head = t; break; }

            if (head != null)
            {
                footY = foot != null ? foot.position.y : root.transform.position.y;
                H = Mathf.Max(0.2f, (head.position.y - footY) / 0.87f);
                c = new Vector3(root.transform.position.x, footY, root.transform.position.z);
                return true;
            }
            // 兜底：包围盒（明知偏大，只在没有骨骼时用）
            var b = WorldBounds(root, 0f);
            if (b.size == Vector3.zero) return false;
            footY = b.min.y; H = Mathf.Max(0.2f, b.size.y); c = new Vector3(b.center.x, footY, b.center.z);
            return true;
        }

        // maxSpan > 0 时，丢掉单个尺寸超过 maxSpan*8 的渲染器 —— 粒子/拖尾之外，
        // 偶尔还有把 AABB 顶到十米级的手柄类物件（见 FixAPSBounds 那条），
        // 一个就能把取景毁掉，宁可漏拍也不能让主体缩成一个点。
        static Bounds WorldBounds(GameObject root, float maxSpan)
        {
            var b = new Bounds(); bool init = false;
            foreach (var r in root.GetComponentsInChildren<Renderer>(false))
            {
                if (!r.enabled || !r.gameObject.activeInHierarchy) continue;
                if (r is ParticleSystemRenderer || r is TrailRenderer || r is LineRenderer) continue;
                var rb = r.bounds;
                if (rb.size == Vector3.zero) continue;
                if (maxSpan > 0f && rb.size.magnitude > maxSpan * 8f) continue;
                if (init) b.Encapsulate(rb); else { b = rb; init = true; }
            }
            return init ? b : new Bounds();
        }

        // ── 出图 ─────────────────────────────────────────────────────
        internal static void Shoot(GameObject avatar, string outDir, string prefix, Action<string> L, bool frontOnly = false)
        {
            float H, footY; Transform head; Vector3 c;
            if (!Measure(avatar, out H, out footY, out head, out c)) { L("measure failed"); return; }
            L($"height={H:F3}m footY={footY:F3} center={c}");

            Vector3 fwd = avatar.transform.forward;                 // 角色朝向
            if (fwd.sqrMagnitude < 1e-4f) fwd = Vector3.forward;
            fwd.y = 0; fwd.Normalize();

            // 取景不能信 Renderer.bounds —— 蒙皮包围盒常年虚报（Milfy 实测报 2.38m，
            // 实际主体约 1.6m），直接用会把角色缩到画面一角、上方留一大片空。
            // 改两趟：先用色键背景拍低分辨率探针，量出主体在画面里的真实外接框，再高分辨率出图。
            Bounds b = WorldBounds(avatar, H);
            Vector3 seed = b.size != Vector3.zero ? b.center : new Vector3(c.x, footY + H * 0.50f, c.z);
            float seedOrtho = Mathf.Max(H * 0.62f,
                b.size != Vector3.zero ? Mathf.Max(b.extents.y, Mathf.Max(b.extents.x, b.extents.z)) : H * 0.62f);
            L($"bounds={(b.size != Vector3.zero ? b.size.ToString("F2") : "n/a")} seedOrtho={seedOrtho:F3}");

            var BG = new Color(0.235f, 0.235f, 0.255f); // 中性深灰，白色系角色也能看清轮廓
            var views = frontOnly
                ? new (string name, float yaw)[] { ("1正面", 0f) }
                : new (string name, float yaw)[] { ("1正面", 0f), ("2四分之三", -38f), ("3背面", 180f) };
            foreach (var v in views)
            {
                Vector3 dir = Quaternion.AngleAxis(v.yaw, Vector3.up) * fwd;
                Vector3 tgt; float ortho, aspect;
                if (!AutoFrame(seed, dir, seedOrtho, H, out tgt, out ortho, out aspect, L))
                { tgt = seed; ortho = seedOrtho; aspect = 0.667f; }
                int hh = 1500, ww = Mathf.Clamp(Mathf.RoundToInt(hh * aspect), 500, 3600);
                string p = Path.Combine(outDir, $"{prefix}_{v.name}.png");
                var tex = Capture(tgt, dir, ortho, H, ww, hh, BG);
                File.WriteAllBytes(p, tex.EncodeToPNG());
                UnityEngine.Object.DestroyImmediate(tex);
                L($"  wrote {Path.GetFileName(p)} {ww}x{hh} ortho={ortho:F3} yaw={v.yaw}");
            }

            // 面部单独走解析定位：脸和身体是连着的，自动裁框裁不出「只要脸」
            // 头骨在颅底，脸中心要往上抬一点；同时沿朝向前移，免得取到后脑
            // 0.105 会把头饰（王冠/蝴蝶结/兽耳）顶端切掉，实测 Milfy 王冠被切 —— 放宽到 0.13
            Vector3 faceTarget = head != null
                ? head.position + Vector3.up * (H * 0.045f) + fwd * (H * 0.01f)
                : seed + Vector3.up * (H * 0.40f);
            if (!frontOnly)
            {
                string p = Path.Combine(outDir, $"{prefix}_4面部.png");
                var tex = Capture(faceTarget, fwd, H * 0.13f, H, 1100, 1100, BG);
                File.WriteAllBytes(p, tex.EncodeToPNG());
                UnityEngine.Object.DestroyImmediate(tex);
                L($"  wrote {Path.GetFileName(p)} face ortho={H * 0.13f:F3}");
            }

            // 面部四分之三特写：捏脸评脸型/五官立体感需要非正面角度（鼻梁侧影、颧骨弧线正面看不出）。
            // 复用同一个 faceTarget 当轴心，相机绕它转 38°（与全身 3/4 那档同角度），焦距不变。
            if (!frontOnly)
            {
                Vector3 face34Dir = Quaternion.AngleAxis(-38f, Vector3.up) * fwd;
                string p = Path.Combine(outDir, $"{prefix}_4b面部四分之三.png");
                var tex = Capture(faceTarget, face34Dir, H * 0.13f, H, 1100, 1100, BG);
                File.WriteAllBytes(p, tex.EncodeToPNG());
                UnityEngine.Object.DestroyImmediate(tex);
                L($"  wrote {Path.GetFileName(p)} face3/4 ortho={H * 0.13f:F3} yaw=-38");
            }

            // 配饰特写：全身图里戒指只有几个像素，八根手指的图看起来完全一样，验收无从谈起。
            // -portraitCloseups 1 时补拍 头顶（光环/头饰）与左右手（腕饰/戒指）。
            // 手部用斜上方 45° 俯视 + 手背朝镜头，T-pose 下这个角度才看得见戴在哪根指头上。
            if (Arg("-portraitCloseups", "0") == "1")
            {
                var an = avatar.GetComponent<Animator>();
                var shots = new List<(string name, Transform bone, float frac, Vector3 dir, Vector3 off)>();
                if (head != null)
                    shots.Add(("5头顶", head, 0.30f, fwd, Vector3.up * (H * 0.10f)));
                if (an != null && an.isHuman)
                {
                    var lh = an.GetBoneTransform(HumanBodyBones.LeftHand);
                    var rh = an.GetBoneTransform(HumanBodyBones.RightHand);
                    // T-pose 手掌朝下，手背朝上 → 相机从上方偏前看下去
                    var handDir = (Vector3.up * 2.2f + fwd).normalized;
                    if (lh != null) shots.Add(("6左手", lh, 0.085f, handDir, -avatar.transform.right * (H * 0.045f)));
                    if (rh != null) shots.Add(("7右手", rh, 0.085f, handDir,  avatar.transform.right * (H * 0.045f)));
                    // 戒指只有 1 cm，手部视角里只占几十像素，看不出戴没戴。
                    // 再给一个对准无名指近节骨的超近特写（视野约 6 cm）。
                    var rr = an.GetBoneTransform(HumanBodyBones.RightRingProximal);
                    var lr = an.GetBoneTransform(HumanBodyBones.LeftRingProximal);
                    if (rr != null) shots.Add(("8右指", rr, 0.016f, handDir, Vector3.zero));
                    if (lr != null) shots.Add(("9左指", lr, 0.016f, handDir, Vector3.zero));
                }
                foreach (var s in shots)
                {
                    string p = Path.Combine(outDir, $"{prefix}_{s.name}.png");
                    var tex = Capture(s.bone.position + s.off, s.dir, H * s.frac, H, 1000, 1000, BG);
                    File.WriteAllBytes(p, tex.EncodeToPNG());
                    UnityEngine.Object.DestroyImmediate(tex);
                    L($"  wrote {Path.GetFileName(p)} ortho={H * s.frac:F3}");
                }
            }
        }

        // ── 单头像出图入口（供 30a-1 候选渲图复用）─────────────────────
        // Run() 内部循环体的单头像版：不开场景、不枚举 descriptor、不建/收 Studio 灯光
        // （调用方要在多组候选之间共用同一套 Studio，自己 Setup/Restore）。
        // 只做「穿衣 → 屏蔽非角色物体 → 拍 → 还原」，拍照前场景状态（含 BlendShape 权重）
        // 由调用方自己摆好，这里不碰。
        internal static void ShootOne(GameObject avatar, string outDir, string prefix, Action<string> L)
        {
            var hidden = new List<Renderer>();
            var dressedOn = new List<GameObject>();
            var reEnabled = new List<Renderer>();
            try
            {
                Dress(avatar, dressedOn, reEnabled, L);
                HideNonCharacter(avatar, hidden, L);
                Shoot(avatar, outDir, prefix, L, frontOnly: false);
            }
            finally
            {
                foreach (var r in hidden) if (r != null) r.enabled = true;
                foreach (var r in reEnabled) if (r != null) r.enabled = false;
                foreach (var g in dressedOn) if (g != null) g.SetActive(false);
            }
        }

        // 两趟取景的第一趟：色键探针。返回主体在世界里的精确取景参数。
        static bool AutoFrame(Vector3 seed, Vector3 dir, float seedOrtho, float H,
                              out Vector3 target, out float ortho, out float aspect, Action<string> L)
        {
            target = seed; ortho = seedOrtho; aspect = 0.667f;
            const int N = 384;
            var key = new Color(0f, 1f, 0f); // 纯绿只用于测量，不会出现在成片里
            float o = seedOrtho * 1.15f;
            for (int attempt = 0; attempt < 4; attempt++)
            {
                var tex = Capture(seed, dir, o, H, N, N, key);
                var px = tex.GetPixels32();
                UnityEngine.Object.DestroyImmediate(tex);
                int x0 = N, x1 = -1, y0 = N, y1 = -1;
                int bgCount = 0;
                for (int y = 0; y < N; y++)
                    for (int x = 0; x < N; x++)
                    {
                        var p = px[y * N + x];
                        if (p.g > 200 && p.r < 60 && p.b < 60) { bgCount++; continue; } // 背景
                        if (x < x0) x0 = x; if (x > x1) x1 = x;
                        if (y < y0) y0 = y; if (y > y1) y1 = y;
                    }
                if (Overrides.ContainsKey("-portraitDebugProbe"))
                {
                    var c00 = px[0]; var cCenter = px[(N / 2) * N + N / 2];
                    L($"    [probe] attempt={attempt} o={o:F3} bg%={100f * bgCount / (N * N):F1} bbox=({x0},{y0})-({x1},{y1}) corner00=({c00.r},{c00.g},{c00.b}) center=({cCenter.r},{cCenter.g},{cCenter.b})");
                }
                if (x1 < 0) { L("  autoframe: 探针全空"); return false; }
                if ((x0 == 0 || y0 == 0 || x1 == N - 1 || y1 == N - 1) && attempt < 3) { o *= 1.6f; continue; }

                // 像素 → 世界（正交、方形画幅，半高 = 半宽 = o；纹理 y=0 在下方，与世界 up 同向）
                float cx = ((x0 + x1 + 1) * 0.5f / N - 0.5f) * 2f * o;
                float cy = ((y0 + y1 + 1) * 0.5f / N - 0.5f) * 2f * o;
                float hw = (x1 - x0 + 1) * 0.5f / N * 2f * o;
                float hh = (y1 - y0 + 1) * 0.5f / N * 2f * o;
                Quaternion q = Quaternion.LookRotation(-dir.normalized, Vector3.up);
                target = seed + (q * Vector3.right) * cx + (q * Vector3.up) * cy;
                ortho = Mathf.Max(hh * 1.05f, H * 0.10f);
                aspect = Mathf.Clamp(hw * 1.05f / ortho, 0.60f, 2.60f);
                return true;
            }
            return false;
        }

        internal static Texture2D Capture(Vector3 target, Vector3 dirFromTargetToCam, float ortho, float H, int w, int h, Color bg)
        {
            var go = new GameObject("~PortraitCam") { hideFlags = HideFlags.HideAndDontSave };
            var cam = go.AddComponent<Camera>();
            try
            {
                float dist = Mathf.Max(2f, H * 4f);
                go.transform.position = target + dirFromTargetToCam.normalized * dist;
                go.transform.rotation = Quaternion.LookRotation(-dirFromTargetToCam.normalized, Vector3.up);

                cam.orthographic = true;
                cam.orthographicSize = ortho;
                cam.aspect = (float)w / h;
                // 素体常年只有 0.7~1.2m 高，自动近裁面会把脸切掉，必须显式给小值
                cam.nearClipPlane = 0.005f;
                cam.farClipPlane = dist + H * 8f;
                cam.clearFlags = CameraClearFlags.SolidColor;
                cam.backgroundColor = bg;
                cam.allowHDR = false; cam.allowMSAA = true;
                cam.cullingMask = ~0;

                var rt = new RenderTexture(w, h, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB) { antiAliasing = 8 };
                var prev = RenderTexture.active;
                try
                {
                    cam.targetTexture = rt;
                    cam.Render();
                    RenderTexture.active = rt;
                    var tex = new Texture2D(w, h, TextureFormat.RGB24, false, false);
                    tex.ReadPixels(new Rect(0, 0, w, h), 0, 0);
                    tex.Apply(false);
                    return tex;
                }
                finally
                {
                    RenderTexture.active = prev;
                    cam.targetTexture = null;
                    rt.Release(); UnityEngine.Object.DestroyImmediate(rt);
                }
            }
            finally { UnityEngine.Object.DestroyImmediate(go); }
        }

        // ── 规格：同一趟把「构建需求」的证据也采了 ───────────────────
        static string Spec(VRC.SDK3.Avatars.Components.VRCAvatarDescriptor d, bool wasActive)
        {
            var root = d.gameObject;
            var inv = CultureInfo.InvariantCulture;
            var skins = root.GetComponentsInChildren<SkinnedMeshRenderer>(true);
            var meshes = root.GetComponentsInChildren<MeshRenderer>(true);
            long tris = 0; int shapes = 0;
            var mats = new HashSet<string>(); var texs = new HashSet<Texture>();
            foreach (var r in skins)
            {
                if (r.sharedMesh != null && r.gameObject.activeInHierarchy && r.enabled)
                { for (int i = 0; i < r.sharedMesh.subMeshCount; i++) tris += r.sharedMesh.GetIndexCount(i) / 3; }
                if (r.sharedMesh != null) shapes += r.sharedMesh.blendShapeCount;
                CollectMat(r, mats, texs);
            }
            foreach (var r in meshes)
            {
                var mf = r.GetComponent<MeshFilter>();
                if (mf != null && mf.sharedMesh != null && r.gameObject.activeInHierarchy && r.enabled)
                { for (int i = 0; i < mf.sharedMesh.subMeshCount; i++) tris += mf.sharedMesh.GetIndexCount(i) / 3; }
                CollectMat(r, mats, texs);
            }
            long texBytes = 0;
            foreach (var t in texs) if (t != null) texBytes += Profiler.GetRuntimeMemorySizeLong(t);

            int pb = CountByType(root, "VRCPhysBone");
            int pbc = CountByType(root, "VRCPhysBoneCollider");
            int ct = CountByType(root, "VRCContactSender") + CountByType(root, "VRCContactReceiver");
            var bones = new HashSet<Transform>();
            foreach (var r in skins) if (r.bones != null) foreach (var b in r.bones) if (b != null) bones.Add(b);

            int prmCount = 0, prmBits = 0;
            if (d.expressionParameters != null && d.expressionParameters.parameters != null)
                foreach (var p in d.expressionParameters.parameters)
                {
                    if (p == null || string.IsNullOrEmpty(p.name)) continue;
                    prmCount++;
                    prmBits += p.valueType == VRC.SDK3.Avatars.ScriptableObjects.VRCExpressionParameters.ValueType.Bool ? 1 : 8;
                }

            var sb = new StringBuilder();
            sb.Append("{\n");
            sb.AppendFormat(inv, "  \"avatar\": {0},\n", Q(root.name));
            sb.AppendFormat(inv, "  \"scene\": {0},\n", Q(root.scene.path));
            sb.AppendFormat(inv, "  \"activeInScene\": {0},\n", wasActive ? "true" : "false");
            sb.AppendFormat(inv, "  \"triangles\": {0},\n", tris);
            sb.AppendFormat(inv, "  \"skinnedMeshes\": {0},\n", skins.Length);
            sb.AppendFormat(inv, "  \"meshRenderers\": {0},\n", meshes.Length);
            sb.AppendFormat(inv, "  \"materialSlots\": {0},\n", mats.Count);
            sb.AppendFormat(inv, "  \"textures\": {0},\n", texs.Count);
            sb.AppendFormat(inv, "  \"textureMiB\": {0:F1},\n", texBytes / 1048576.0);
            sb.AppendFormat(inv, "  \"blendShapes\": {0},\n", shapes);
            sb.AppendFormat(inv, "  \"bones\": {0},\n", bones.Count);
            sb.AppendFormat(inv, "  \"physBones\": {0},\n", pb);
            sb.AppendFormat(inv, "  \"physBoneColliders\": {0},\n", pbc);
            sb.AppendFormat(inv, "  \"contacts\": {0},\n", ct);
            sb.AppendFormat(inv, "  \"exprParams\": {0},\n", prmCount);
            sb.AppendFormat(inv, "  \"exprParamBits\": {0},\n", prmBits);
            sb.AppendFormat(inv, "  \"shaders\": [{0}]\n", string.Join(", ", mats.OrderBy(x => x).Select(Q)));
            sb.Append("}\n");
            return sb.ToString();
        }

        static void CollectMat(Renderer r, HashSet<string> mats, HashSet<Texture> texs)
        {
            foreach (var m in r.sharedMaterials)
            {
                if (m == null) continue;
                if (m.shader != null) mats.Add(m.shader.name);
                var sh = m.shader; if (sh == null) continue;
                int n = ShaderUtil.GetPropertyCount(sh);
                for (int i = 0; i < n; i++)
                    if (ShaderUtil.GetPropertyType(sh, i) == ShaderUtil.ShaderPropertyType.TexEnv)
                    {
                        var t = m.GetTexture(ShaderUtil.GetPropertyName(sh, i));
                        if (t != null) texs.Add(t);
                    }
            }
        }

        static int CountByType(GameObject root, string typeName)
        {
            int n = 0;
            foreach (var c in root.GetComponentsInChildren<Component>(true))
                if (c != null && c.GetType().Name == typeName) n++;
            return n;
        }

        static string Q(string s)
        {
            if (s == null) return "null";
            return "\"" + s.Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\n", " ") + "\"";
        }
    }
}
