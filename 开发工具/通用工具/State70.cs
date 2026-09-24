/**
 * 【项目沉淀】通用工具
 * 适用素体：无关
 * 相关素材：工程场景与 AvatarDescriptor
 * 工具链　：Unity 2022.3.22f1 / VRChat SDK 3.10.4
 * 可复用性：★★ 求值器通用，参数表按素体填
 * 用途　　：70 · 「按一组参数把头像摆成交付状态」的共用求值器，验收渲图/脚型测量/组合遍历三处共用同一套语义。
 */
using System;
using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEditor.Animations;
using UnityEngine;
using VRC.SDK3.Avatars.Components;
using VRC.SDK3.Avatars.ScriptableObjects;
using VRC.SDKBase;

// 70 · 「按一组参数把头像摆成交付状态」的共用求值器
//
// 抽出来的理由：验收渲图、脚型测量、组合遍历三处都要同一套语义，
// 各写一份必然漂移（记忆 generated-asset-verification：验收要由**真动画数据**驱动）。
//
// 三条踩过的坑，都固化在这里：
//   ① 只跑我方 clip 不够 —— `LEM/Jacket`、`Toggle-NekomimiHB` 这些开关的**网格显隐写在厂商层里**，
//      我方只驱动参数。要把场景里所有 MA MergeAnimator 的控制器一并求值，路径补 Relative 前缀。
//   ② **求值顺序**：先跑我方的层算出 Driver 写给厂商参数的值 → 再跑厂商的层 → 最后我方属性覆盖。
//      反过来的话厂商参数还停在控制器默认值，会渲出一张自信的错图。
//   ③ 不能只应用 `m_IsActive` —— 脚型、胸围这些是 `blendShape.*`，漏了就量不出鞋合不合脚。
namespace Milfy60
{
    public static class State70
    {
        // 还原用的快照：物体激活状态 + 形态键值
        public class Snapshot
        {
            public Dictionary<GameObject, bool> active = new Dictionary<GameObject, bool>();
            public Dictionary<(SkinnedMeshRenderer, int), float> shapes = new Dictionary<(SkinnedMeshRenderer, int), float>();
            public int Restore()
            {
                int n = 0;
                foreach (var kv in active) if (kv.Key != null && kv.Key.activeSelf != kv.Value) { kv.Key.SetActive(kv.Value); n++; }
                foreach (var kv in shapes) if (kv.Key.Item1 != null) kv.Key.Item1.SetBlendShapeWeight(kv.Key.Item2, kv.Value);
                return n;
            }
        }

        public static Dictionary<string, float> Defaults(VRCExpressionParameters pars)
        {
            var d = new Dictionary<string, float>();
            foreach (var p in pars.parameters) d[p.name] = p.defaultValue;
            return d;
        }

        // 厂商 `*_OFF` 参数 → 它管的素体网格（70d / `_60胸围与Kumachan.md` 实测，不是猜的）
        static readonly Dictionary<string, string> OffParamMesh = new Dictionary<string, string> {
            { "Cardigan_OFF", "Cardigan" }, { "Bottoms_OFF", "Bottoms" },
            { "Crown_OFF", "Crown" },       { "Slippers_OFF", "Kumachan_Slippers" },
        };

        static bool Cond(AnimatorCondition c, Dictionary<string, float> pv)
        {
            if (!pv.TryGetValue(c.parameter, out var v)) return false;
            switch (c.mode)
            {
                case AnimatorConditionMode.If: return v > 0.5f;
                case AnimatorConditionMode.IfNot: return v <= 0.5f;
                case AnimatorConditionMode.Greater: return v > c.threshold;
                case AnimatorConditionMode.Less: return v < c.threshold;
                case AnimatorConditionMode.Equals: return Mathf.Approximately(v, c.threshold);
                case AnimatorConditionMode.NotEqual: return !Mathf.Approximately(v, c.threshold);
            }
            return false;
        }

        // 按条件挑状态：AnyState 优先，否则从默认态沿满足条件的转移走几步
        static AnimatorState Pick(AnimatorStateMachine sm, Dictionary<string, float> pv)
        {
            foreach (var t in sm.anyStateTransitions)
                if (t.destinationState != null && t.conditions.Length > 0 && t.conditions.All(x => Cond(x, pv)))
                    return t.destinationState;
            var cur = sm.defaultState;
            for (int k = 0; k < 8 && cur != null; k++)
            {
                var t = cur.transitions.FirstOrDefault(x => x.destinationState != null
                            && x.conditions.Length > 0 && x.conditions.All(y => Cond(y, pv)));
                if (t == null) break;
                cur = t.destinationState;
            }
            return cur;
        }

        // 只求值、不碰场景。`includeVendor=false` 时只算我方控制器
        // （组合遍历的断言是按「我方层写了什么」定义的，掺进厂商层会改变判据语义）。
        public static void Evaluate(Transform root, AnimatorController ctrl,
                                    Dictionary<string, float> ps,
                                    out Dictionary<string, bool> outActive,
                                    out Dictionary<(string path, string key), float> outShape,
                                    bool includeVendor = true)
        {
            var pv = new Dictionary<string, float>(ps);
            var ours = new Dictionary<string, bool>();
            var oursShape = new Dictionary<(string path, string key), float>();
            var state = new Dictionary<string, bool>();
            var shape = new Dictionary<(string path, string key), float>();

            void Collect(AnimatorState st, Dictionary<string, bool> act,
                         Dictionary<(string, string), float> shp, string prefix)
            {
                if (st == null) return;
                var c = st.motion as AnimationClip;
                if (c != null)
                    foreach (var b in AnimationUtility.GetCurveBindings(c))
                    {
                        float v = AnimationUtility.GetEditorCurve(c, b).Evaluate(0f);
                        if (b.propertyName == "m_IsActive" && b.type == typeof(GameObject)) act[prefix + b.path] = v > 0.5f;
                        else if (b.propertyName.StartsWith("blendShape.")) shp[(prefix + b.path, b.propertyName.Substring(11))] = v;
                    }
                foreach (var d in st.behaviours.OfType<VRCAvatarParameterDriver>())
                    foreach (var q in d.parameters)
                    {
                        if (q.type == VRC_AvatarParameterDriver.ChangeType.Set) pv[q.name] = q.value;
                        else if (q.type == VRC_AvatarParameterDriver.ChangeType.Copy && pv.TryGetValue(q.source, out var sv))
                            pv[q.name] = q.convertRange
                                ? Mathf.LerpUnclamped(q.destMin, q.destMax,
                                    Mathf.Approximately(q.sourceMax, q.sourceMin) ? 0f
                                    : (sv - q.sourceMin) / (q.sourceMax - q.sourceMin))
                                : sv;
                    }
            }

            // ── 第一遍：我方的层（顺带把 Driver 写给厂商参数的值算出来）──
            foreach (var l in ctrl.layers) Collect(Pick(l.stateMachine, pv), ours, oursShape, "");

            // ── 第二遍：厂商 MergeAnimator 的层，用算好的参数值 ──
            if (includeVendor)
            foreach (var ma in root.GetComponentsInChildren<
                         nadena.dev.modular_avatar.core.ModularAvatarMergeAnimator>(true))
            {
                if (!(ma.animator is AnimatorController vc) || vc == ctrl) continue;
                var q2 = new List<string>();
                for (var c2 = ma.transform; c2 != null && c2 != root; c2 = c2.parent) q2.Add(c2.name);
                q2.Reverse();
                string prefix = ma.pathMode == nadena.dev.modular_avatar.core.MergeAnimatorPathMode.Relative
                    ? (q2.Count == 0 ? "" : string.Join("/", q2) + "/") : "";
                foreach (var p in vc.parameters)          // 我方没驱动到的，用控制器默认值兜底
                    if (!pv.ContainsKey(p.name))
                        pv[p.name] = p.type == AnimatorControllerParameterType.Bool ? (p.defaultBool ? 1f : 0f)
                                   : (p.type == AnimatorControllerParameterType.Int ? p.defaultInt : p.defaultFloat);
                foreach (var l in vc.layers) Collect(Pick(l.stateMachine, pv), state, shape, prefix);
            }

            // ── 我方写的最后覆盖上去（MA 把我方的层追加在后面）──
            foreach (var kv in ours) state[kv.Key] = kv.Value;
            foreach (var kv in oursShape) shape[kv.Key] = kv.Value;
            foreach (var kv in OffParamMesh)
                if (pv.TryGetValue(kv.Key, out var v)) state[kv.Value] = v <= 0.5f;   // `_OFF` 语义相反

            outActive = state; outShape = shape;
        }

        // 求值 ＋ 落到场景，同时记快照供还原
        public static void Apply(Transform root, AnimatorController ctrl,
                                 Dictionary<string, float> ps, Snapshot snap)
        {
            Evaluate(root, ctrl, ps, out var state, out var shape, true);
            foreach (var kv in state)
            {
                var t = root.Find(kv.Key);
                if (t == null) continue;      // 厂商 clip 里的悬空绑定（如 `HelloWorld`），场景里没这物体
                if (!snap.active.ContainsKey(t.gameObject)) snap.active[t.gameObject] = t.gameObject.activeSelf;
                t.gameObject.SetActive(kv.Value);
            }
            foreach (var kv in shape)
            {
                var t = root.Find(kv.Key.path);
                var smr = t == null ? null : t.GetComponent<SkinnedMeshRenderer>();
                if (smr == null || smr.sharedMesh == null) continue;
                int idx = smr.sharedMesh.GetBlendShapeIndex(kv.Key.key);
                if (idx < 0) continue;
                if (!snap.shapes.ContainsKey((smr, idx))) snap.shapes[(smr, idx)] = smr.GetBlendShapeWeight(idx);
                smr.SetBlendShapeWeight(idx, kv.Value);
            }
        }
    }
}
