// ══════════════════════════════════════════════════════════════════
// 【项目沉淀】通用工具
// 适用素体：任意
// 相关素材：无
// 工具链　：Unity 2022.3.22f1 / VRChat SDK 3.10.4
// 可复用性：★★ 改开头的参数名表就能用
// 用途　　：追一个参数到底驱动了什么——参数→动画层→片段→曲线目标，并检查目标是否还存在
// ══════════════════════════════════════════════════════════════════
// 判断参数能不能删，光看「动画层里有没有」不够 —— 动画层里在，不代表它驱动的对象还在。
// 素体自带参数常常驱动的是已被删掉的默认服装/发型网格：层还在跑，作用于空气。
//
// 这里把链路走到底：找到引用该参数的层 → 层里所有片段 → 片段的曲线绑定 →
// 逐条检查 path 能不能在头像下解析到、形状键在不在该渲染器上。
//
// 运行模式下跑：那时 MA/VRCFury 已经把控制器合并生成完毕，参数名可能带 VF##_ 前缀，
// 所以匹配用「后缀匹配」而不是全等。
using System.Collections.Generic;
using System.Linq;
using System.Text;
using UnityEngine;
using UnityEditor;
using UnityEditor.Animations;
using VRC.SDK3.Avatars.Components;

namespace AvatarGen
{
    public static class TraceParam
    {
        static readonly string[] Targets = {
            "Sleeve", "Cardigan_OFF", "Bottoms_OFF", "Crown_OFF", "Slippers_OFF",
        };

        static bool Match(string paramName, string want) =>
            paramName == want || paramName.EndsWith("_" + want) || paramName.EndsWith(want);

        static IEnumerable<AnimationClip> ClipsOf(Motion m)
        {
            if (m is AnimationClip c) { yield return c; yield break; }
            if (m is BlendTree bt)
                foreach (var ch in bt.children)
                    foreach (var cc in ClipsOf(ch.motion)) yield return cc;
        }

        [MenuItem("Tools/AvatarGen/Perf - 追踪参数去向", false, 332)]
        public static void Trace()
        {
            var all = Object.FindObjectsOfType<VRCAvatarDescriptor>();
            var d = all.FirstOrDefault(x => x.gameObject.activeInHierarchy) ?? all.FirstOrDefault();
            if (d == null) { Debug.LogError("[Trace] 找不到头像"); return; }
            var root = d.transform;

            var ctrls = d.baseAnimationLayers.Concat(d.specialAnimationLayers)
                         .Select(l => l.animatorController as AnimatorController)
                         .Where(c => c != null).ToList();

            var sb = new StringBuilder();
            sb.AppendLine($"[Trace] {d.name}   控制器 {ctrls.Count} 个（运行模式={Application.isPlaying}）");
            sb.AppendLine();

            foreach (var want in Targets)
            {
                sb.AppendLine(new string('=', 60));
                sb.AppendLine($"■ {want}");
                var clips = new HashSet<AnimationClip>();
                var layerNames = new List<string>();

                foreach (var ac in ctrls)
                {
                    var pn = ac.parameters.Select(p => p.name).Where(n => Match(n, want)).ToList();
                    if (pn.Count == 0) continue;
                    foreach (var layer in ac.layers)
                    {
                        bool used = false;
                        foreach (var st in layer.stateMachine.states)
                        {
                            // 状态用它做 motion time / 速度，或转换条件里用到
                            if (pn.Any(n => st.state.timeParameter == n || st.state.speedParameter == n
                                         || st.state.cycleOffsetParameter == n || st.state.mirrorParameter == n)) used = true;
                            foreach (var tr in st.state.transitions)
                                if (tr.conditions.Any(c => pn.Contains(c.parameter))) used = true;
                            if (st.state.motion is BlendTree b0 && pn.Contains(b0.blendParameter)) used = true;
                        }
                        foreach (var tr in layer.stateMachine.anyStateTransitions)
                            if (tr.conditions.Any(c => pn.Contains(c.parameter))) used = true;
                        if (!used) continue;
                        layerNames.Add($"{ac.name}/{layer.name}");
                        foreach (var st in layer.stateMachine.states)
                            foreach (var c in ClipsOf(st.state.motion)) clips.Add(c);
                    }
                }

                sb.AppendLine($"  引用它的动画层：{layerNames.Count} 个   {string.Join(", ", layerNames.Take(4))}");
                sb.AppendLine($"  这些层里的动画片段：{clips.Count} 个");

                int ok = 0, deadPath = 0, deadShape = 0;
                var deadSamples = new List<string>();
                var okSamples = new List<string>();
                foreach (var clip in clips)
                {
                    foreach (var b in AnimationUtility.GetCurveBindings(clip))
                    {
                        var t = string.IsNullOrEmpty(b.path) ? root : root.Find(b.path);
                        if (t == null)
                        {
                            deadPath++;
                            if (deadSamples.Count < 6) deadSamples.Add($"路径不存在: {b.path}  ({b.propertyName})");
                            continue;
                        }
                        if (b.propertyName.StartsWith("blendShape."))
                        {
                            var smr = t.GetComponent<SkinnedMeshRenderer>();
                            var shape = b.propertyName.Substring("blendShape.".Length);
                            if (smr == null || smr.sharedMesh == null || smr.sharedMesh.GetBlendShapeIndex(shape) < 0)
                            {
                                deadShape++;
                                if (deadSamples.Count < 6) deadSamples.Add($"形状键不存在: {b.path} → {shape}");
                                continue;
                            }
                        }
                        ok++;
                        if (okSamples.Count < 4) okSamples.Add($"{b.path} → {b.propertyName}");
                    }
                }

                sb.AppendLine($"  曲线绑定：可解析 {ok} 条 · 路径不存在 {deadPath} 条 · 形状键不存在 {deadShape} 条");
                foreach (var s in okSamples) sb.AppendLine($"      ✓ {s}");
                foreach (var s in deadSamples) sb.AppendLine($"      ✗ {s}");
                sb.AppendLine(ok == 0 && (deadPath + deadShape) > 0
                    ? "  → 判定：死参数，驱动的对象全都不存在，可删"
                    : ok > 0 ? "  → 判定：★活的，仍在驱动存在的对象，不要删"
                             : "  → 判定：查不到任何曲线，需人工看");
                sb.AppendLine();
            }

            var dir = System.IO.Path.Combine(System.IO.Directory.GetCurrentDirectory(), "Captures");
            System.IO.Directory.CreateDirectory(dir);
            System.IO.File.WriteAllText(System.IO.Path.Combine(dir, "trace_param.txt"), sb.ToString());
            Debug.Log("[Trace] 明细见 Captures/trace_param.txt\n" + sb.ToString().Substring(0, Mathf.Min(800, sb.Length)));
        }
    }
}
