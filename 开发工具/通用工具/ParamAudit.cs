// ══════════════════════════════════════════════════════════════════
// 【项目沉淀】通用工具
// 适用素体：任意
// 相关素材：无
// 工具链　：Unity 2022.3.22f1 / VRChat SDK 3.10.4
// 可复用性：★★★ 自动识别头像，换单直接能用
// 用途　　：审计表情参数——每个参数占多少位、是否被菜单引用、是否被动画层使用，找出可删的
// ══════════════════════════════════════════════════════════════════
// 参数预算 256 位是硬上限。素体自带的参数里常有大量「厂商默认服装/发型的调节项」，
// 换成客户自己的衣柜后就再没人用，但位数照占。
//
// 判定一个参数能不能删，要同时看两处：
//   ① 菜单里有没有控件引用它（用户能不能操作到）
//   ② 动画层里有没有它（有没有东西响应它）
// 两处都没有 = 死参数，删了只省位不改行为。
// 只有菜单没动画层 = 菜单上有个按钮但按了没反应，同样是死的。
// 只有动画层没菜单 = 可能由 Contact/OSC/其他系统驱动，别删。
//
// 「动画层使用」按真实读写位置算（转移条件 / Motion Time 等四个状态参数 / BlendTree 含 Direct /
// VRCAvatarParameterDriver / 递归子状态机），不按控制器的声明表算。
// 来由（2026-09-22）：旧版直接把 `AnimatorController.parameters`（声明表）当成「动画层在用」，
// 删掉层之后残留的声明被误判成「只有动画层没菜单，可能由 Contact/OSC 驱动，别删」——结论正好反了。
// 因此另出一段「已声明但没有任何层使用」，专收这类残留声明（只作信息，不参与上面的可删判定）。
using System.Collections.Generic;
using System.Linq;
using System.Text;
using UnityEngine;
using UnityEditor;
using UnityEditor.Animations;
using VRC.SDK3.Avatars.Components;
using VRC.SDK3.Avatars.ScriptableObjects;
using VRC.SDKBase;

namespace AvatarGen
{
    public static class ParamAudit
    {
        static GameObject Avatar()
        {
            var sel = Selection.activeGameObject;
            if (sel != null)
            {
                var d0 = sel.GetComponentInParent<VRCAvatarDescriptor>();
                if (d0 != null) return d0.gameObject;
            }
            var all = Object.FindObjectsOfType<VRCAvatarDescriptor>();
            var g = all.FirstOrDefault(d => d.gameObject.activeInHierarchy);
            return g != null ? g.gameObject : (all.Length > 0 ? all[0].gameObject : null);
        }

        static int Cost(VRCExpressionParameters.Parameter p)
        {
            if (!p.networkSynced) return 0;
            return p.valueType == VRCExpressionParameters.ValueType.Bool ? 1 : 8;
        }

        static void WalkMenu(VRCExpressionsMenu menu, HashSet<string> used, HashSet<VRCExpressionsMenu> seen, List<string> trail, StringBuilder tree, int depth)
        {
            if (menu == null || !seen.Add(menu)) return;
            foreach (var c in menu.controls)
            {
                tree.AppendLine(new string(' ', depth * 2) + "· " + c.name + "   [" + c.type + "]"
                    + (string.IsNullOrEmpty(c.parameter?.name) ? "" : "  → " + c.parameter.name));
                if (!string.IsNullOrEmpty(c.parameter?.name)) used.Add(c.parameter.name);
                if (c.subParameters != null)
                    foreach (var sp in c.subParameters)
                        if (!string.IsNullOrEmpty(sp?.name)) used.Add(sp.name);
                if (c.type == VRCExpressionsMenu.Control.ControlType.SubMenu)
                    WalkMenu(c.subMenu, used, seen, trail, tree, depth + 1);
            }
        }

        // ── 真实使用收集：动画层里任何读/写参数的位置都算「动画层在用」──

        // 转移条件（状态转移 / AnyState / Entry / 子状态机转移都走这里）
        static void CollectTransitions(IEnumerable<AnimatorTransitionBase> ts, HashSet<string> used)
        {
            if (ts == null) return;
            foreach (var t in ts)
            {
                if (t == null || t.conditions == null) continue;
                foreach (var c in t.conditions)
                    if (!string.IsNullOrEmpty(c.parameter)) used.Add(c.parameter);
            }
        }

        // VRCAvatarParameterDriver：name 是写，Copy 型的 source 是读
        static void CollectDrivers(StateMachineBehaviour[] bs, HashSet<string> used)
        {
            if (bs == null) return;
            foreach (var b in bs)
            {
                var drv = b as VRCAvatarParameterDriver;
                if (drv == null || drv.parameters == null) continue;
                foreach (var p in drv.parameters)
                {
                    if (p == null) continue;
                    if (!string.IsNullOrEmpty(p.name)) used.Add(p.name);
                    if (p.type == VRC_AvatarParameterDriver.ChangeType.Copy && !string.IsNullOrEmpty(p.source))
                        used.Add(p.source);
                }
            }
        }

        // BlendTree：blendParameter / blendParameterY；Direct 型的 children 还各有 directBlendParameter；子节点递归
        static void CollectMotion(Motion m, HashSet<string> used)
        {
            var bt = m as BlendTree;
            if (bt == null) return;
            if (!string.IsNullOrEmpty(bt.blendParameter)) used.Add(bt.blendParameter);
            if (!string.IsNullOrEmpty(bt.blendParameterY)) used.Add(bt.blendParameterY);
            if (bt.children == null) return;
            foreach (var ch in bt.children)
            {
                if (bt.blendType == BlendTreeType.Direct && !string.IsNullOrEmpty(ch.directBlendParameter))
                    used.Add(ch.directBlendParameter);
                CollectMotion(ch.motion, used);
            }
        }

        // 单个状态：四个状态参数只在 *Active 为 true 时算；再加上 motion / 转移 / Driver
        static void CollectState(AnimatorState st, HashSet<string> used)
        {
            if (st == null) return;
            if (st.timeParameterActive && !string.IsNullOrEmpty(st.timeParameter)) used.Add(st.timeParameter);
            if (st.speedParameterActive && !string.IsNullOrEmpty(st.speedParameter)) used.Add(st.speedParameter);
            if (st.mirrorParameterActive && !string.IsNullOrEmpty(st.mirrorParameter)) used.Add(st.mirrorParameter);
            if (st.cycleOffsetParameterActive && !string.IsNullOrEmpty(st.cycleOffsetParameter)) used.Add(st.cycleOffsetParameter);
            CollectMotion(st.motion, used);
            CollectTransitions(st.transitions, used);
            CollectDrivers(st.behaviours, used);
        }

        // 状态机递归：AnyState / Entry / 本机 Driver / 各状态 / 各子状态机（含跨机转移）
        static void CollectStateMachine(AnimatorStateMachine sm, HashSet<string> used)
        {
            if (sm == null) return;
            CollectTransitions(sm.anyStateTransitions, used);
            CollectTransitions(sm.entryTransitions, used);
            CollectDrivers(sm.behaviours, used);
            if (sm.states != null)
                foreach (var cs in sm.states) CollectState(cs.state, used);
            if (sm.stateMachines != null)
                foreach (var csm in sm.stateMachines)
                {
                    if (csm.stateMachine == null) continue;
                    CollectTransitions(sm.GetStateMachineTransitions(csm.stateMachine), used);
                    CollectStateMachine(csm.stateMachine, used);
                }
        }

        [MenuItem("Tools/AvatarGen/Perf - 参数审计", false, 330)]
        public static void Audit()
        {
            var go = Avatar();
            if (go == null) { Debug.LogError("[Param] 找不到头像"); return; }
            var d = go.GetComponent<VRCAvatarDescriptor>();
            var pars = d.expressionParameters;
            if (pars == null) { Debug.LogError("[Param] 头像没有 ExpressionParameters"); return; }

            // 菜单里被引用的参数
            var inMenu = new HashSet<string>();
            var tree = new StringBuilder();
            WalkMenu(d.expressionsMenu, inMenu, new HashSet<VRCExpressionsMenu>(), new List<string>(), tree, 0);

            // 动画层真实读写的参数（含所有 playable layer 的 controller）＋ 各控制器的声明表
            var inAnim = new HashSet<string>();
            var declared = new HashSet<string>();
            var declaredByCtrl = new List<KeyValuePair<string, List<string>>>();
            var ctrls = new List<RuntimeAnimatorController>();
            foreach (var l in d.baseAnimationLayers.Concat(d.specialAnimationLayers))
                if (l.animatorController != null) ctrls.Add(l.animatorController);
            foreach (var rc in ctrls)
            {
                var ac = rc as AnimatorController;
                if (ac == null) continue;
                foreach (var l in ac.layers) CollectStateMachine(l.stateMachine, inAnim);
                var decl = new List<string>();
                foreach (var p in ac.parameters) { declared.Add(p.name); decl.Add(p.name); }
                declaredByCtrl.Add(new KeyValuePair<string, List<string>>(ac.name, decl));
            }

            var sb = new StringBuilder();
            int total = pars.parameters.Sum(Cost);
            sb.AppendLine($"[Param] {go.name}   参数 {pars.parameters.Length} 个 · 同步位 {total} / 256");
            sb.AppendLine($"        动画层 {ctrls.Count} 个，其中可解析的参数 {inAnim.Count} 个");
            sb.AppendLine();
            sb.AppendLine("位  类型    菜单 动画  参数名");
            sb.AppendLine("--- ------- ---- ----  ------------------------------");

            int dead = 0, deadBits = 0, menuOnly = 0, animOnly = 0;
            foreach (var p in pars.parameters.OrderByDescending(Cost).ThenBy(p => p.name))
            {
                bool m = inMenu.Contains(p.name), a = inAnim.Contains(p.name);
                string tag = m && a ? "" : (!m && !a ? "  ★死参数（菜单和动画层都没有）"
                            : (m ? "  ○ 菜单有、动画层没有 —— 按了没反应" : "  △ 动画层有、菜单没有 —— 可能由 Contact/OSC 驱动，别删"));
                if (!m && !a) { dead++; deadBits += Cost(p); }
                else if (m && !a) menuOnly++;
                else if (!m && a) animOnly++;
                sb.AppendLine($"{Cost(p),3} {p.valueType,-7} {(m ? "有" : "无"),-4} {(a ? "有" : "无"),-4}  {p.name}{tag}");
            }

            sb.AppendLine();
            sb.AppendLine($"死参数 {dead} 个，合计 {deadBits} 位可回收");
            sb.AppendLine($"菜单有但动画层没有 {menuOnly} 个 · 动画层有但菜单没有 {animOnly} 个");

            // 信息段：控制器声明表里有、但没有任何层真实读写的参数（删层后残留的声明）
            int unusedDeclared = declared.Count(n => !inAnim.Contains(n));
            sb.AppendLine();
            sb.AppendLine($"=== 已声明但没有任何层使用 {unusedDeclared} 个（只剩声明，优先清理）===");
            foreach (var kv in declaredByCtrl)
            {
                var un = kv.Value.Where(n => !inAnim.Contains(n)).ToList();
                if (un.Count > 0) sb.AppendLine($"· {kv.Key}（{un.Count}）: {string.Join(", ", un)}");
            }
            if (unusedDeclared == 0) sb.AppendLine("（无）");

            sb.AppendLine();
            sb.AppendLine("=== 菜单树 ===");
            sb.Append(tree);

            var dir = System.IO.Path.Combine(System.IO.Directory.GetCurrentDirectory(), "Captures");
            System.IO.Directory.CreateDirectory(dir);
            System.IO.File.WriteAllText(System.IO.Path.Combine(dir, "param_audit.txt"), sb.ToString());
            Debug.Log("[Param] 明细见 Captures/param_audit.txt\n" + sb.ToString().Substring(0, Mathf.Min(900, sb.Length)));
        }
    }
}
