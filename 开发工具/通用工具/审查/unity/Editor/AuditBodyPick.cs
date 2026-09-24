/**
 * 【项目沉淀】通用工具
 * 适用素体：无关
 * 相关素材：工程网格与蒙皮权重
 * 工具链　：Unity 2022.3.22f1 / VRChat SDK 3.10.4
 * 可复用性：★★ 审查工具链的一环
 * 用途　　：「哪块网格是身体」的共享判据（蒙皮权重同时覆盖脚与躯干），抽出来给 T-05/T-10/T2 三处共用。
 */
// ══════════════════════════════════════════════════════════════════════════
// AuditBodyPick —— 「哪块网格是身体」的共享判据（任务 AY，并 K7 / K19 / K20）
//
// 为什么单独一份：
//   T-05 部件盘点（AuditPartInventory.FindBodySmr）、T-10 poke（AuditProbes.PickBodyPath）、
//   T2 贴合探针（AuditFitProbe 的 body=auto）此前各写一套「按骨骼部位集合认身体」的启发式。
//   Kipfel 素体上脸网格 `Body`（顶点比真身体 `Body_Base` 还多）会被当成身体，导出/探针全错。
//   任务 AM 只在 T-05 里改成「按蒙皮权重判覆盖」，本文件把同一判据抽出来给三处共用，
//   避免再次各修各的（AM 教训 1 遗留的 K20）。
//
// 判据（与 AM 的 AuditPartInventory 版本逐字一致）：
//   1) 名字候选（大小写不敏感：Body_b / Body_base / Body）里优先选**蒙皮权重同时覆盖脚与躯干**
//      的那个，多个满足取顶点最多；
//   2) 名字都不满足（网格不可读等）再退回几何启发：骨骼部位集合同时含脚与躯干、可见、顶点最多。
//   名字里含 Body 的全身服装同理，故名字候选也必须过权重这一关。
//
// 权重份额阈值 0.1%：真身体（Kipfel Body_Base）脚 0.32、躯干 0.17；脸网格（Body）脚/躯干恰好 0。
// 取 0.1% 足以分开，又不会被个别错绑顶点的噪声权重骗过（AM 标定）。
//
// 只读：只读 Mesh 权重，不改任何资产。
// ══════════════════════════════════════════════════════════════════════════

using System;
using System.Collections.Generic;
using System.Text;
using Unity.Collections;
using UnityEngine;

namespace AvatarAudit
{
    /// <summary>身体网格识别共享判据。regionOf 由调用方给（人形映射三处实现不同，故用委托）。</summary>
    internal static class AuditBodyPick
    {
        /// <summary>「脚」检测部位（含小腿，与 T2 auto 的 LeftFoot|LeftLowerLeg 同口径）。
        /// 注意这只是**识别身体**用，鞋底最低点另用 AuditPartInventory 的 FootRegionNames。</summary>
        public static readonly string[] FootDetectRegions =
            { "LeftFoot", "LeftToes", "LeftLowerLeg", "RightFoot", "RightToes", "RightLowerLeg" };

        /// <summary>「躯干」检测部位。</summary>
        public static readonly string[] TorsoDetectRegions =
            { "Hips", "Spine", "Chest", "UpperChest" };

        /// <summary>脚/躯干各自的最低权重份额（占该网格全部蒙皮权重）。0.1%，来源见文件头。</summary>
        public const float MinWeightShare = 0.001f;

        /// <summary>父链上溯保护（防环/防坏层级）。</summary>
        public const int BoneWalkGuard = 512;

        /// <summary>名字候选（大小写不敏感）。</summary>
        public static bool IsKnownBodyName(string n)
        {
            if (string.IsNullOrEmpty(n)) return false;
            n = n.Trim();
            return string.Equals(n, "Body_b", StringComparison.OrdinalIgnoreCase)
                || string.Equals(n, "Body_base", StringComparison.OrdinalIgnoreCase)
                || string.Equals(n, "Body", StringComparison.OrdinalIgnoreCase);
        }

        /// <summary>可见且启用、有网格。</summary>
        public static bool IsEligible(SkinnedMeshRenderer smr)
        {
            if (smr == null || smr.sharedMesh == null) return false;
            if (!smr.gameObject.activeInHierarchy || !smr.enabled) return false;
            return true;
        }

        public static bool IsFootDetectRegion(string r) { return ExactIn(FootDetectRegions, r); }
        public static bool IsTorsoRegion(string r) { return ExactIn(TorsoDetectRegions, r); }

        /// <summary>
        /// 找身体 SMR。smrs 应是同一头像根下的候选（调用方自己决定要不要先过滤可见）。
        /// 找不到返回 null（调用方各自退路：T-10 退顶点最多、T2 抛异常、T-05 留空+warning）。
        /// </summary>
        public static SkinnedMeshRenderer FindBodySmr(IList<SkinnedMeshRenderer> smrs,
            Func<Transform, string> regionOf)
        {
            if (smrs == null || regionOf == null) return null;

            SkinnedMeshRenderer named = null; int namedV = -1;
            for (int i = 0; i < smrs.Count; i++)
            {
                SkinnedMeshRenderer smr = smrs[i];
                if (!IsEligible(smr)) continue;
                if (!IsKnownBodyName(smr.gameObject.name)) continue;
                if (!CoversFootAndTorsoByWeights(smr, regionOf)) continue;
                if (smr.sharedMesh.vertexCount > namedV) { namedV = smr.sharedMesh.vertexCount; named = smr; }
            }
            if (named != null) return named;

            SkinnedMeshRenderer best = null; int bestV = -1;
            for (int i = 0; i < smrs.Count; i++)
            {
                SkinnedMeshRenderer smr = smrs[i];
                if (!IsEligible(smr)) continue;
                Transform[] bones = smr.bones;
                if (bones == null || bones.Length == 0) continue;
                bool foot = false, torso = false;
                for (int b = 0; b < bones.Length; b++)
                {
                    string reg = regionOf(bones[b]);
                    if (IsFootDetectRegion(reg)) foot = true;
                    if (IsTorsoRegion(reg)) torso = true;
                    if (foot && torso) break;
                }
                if (!foot || !torso) continue;
                if (smr.sharedMesh.vertexCount > bestV) { bestV = smr.sharedMesh.vertexCount; best = smr; }
            }
            return best;
        }

        /// <summary>该 SMR 的蒙皮权重是否同时落在脚部与躯干人形部位（各自份额 ≥ MinWeightShare）。
        /// 优先新 API（GetBonesPerVertex/GetAllBoneWeights），退 legacy Mesh.boneWeights；都读不到
        /// 返回 false（让 FindBodySmr 走几何兜底），不抛异常。</summary>
        public static bool CoversFootAndTorsoByWeights(SkinnedMeshRenderer smr, Func<Transform, string> regionOf)
        {
            if (smr == null || regionOf == null) return false;
            Mesh mesh = smr.sharedMesh;
            Transform[] bones = smr.bones;
            if (mesh == null || bones == null || bones.Length == 0) return false;
            int vc = mesh.vertexCount;
            if (vc <= 0) return false;

            string[] boneRegion = new string[bones.Length];
            for (int b = 0; b < boneRegion.Length; b++) boneRegion[b] = regionOf(bones[b]);

            var wSum = new Dictionary<string, double>(StringComparer.Ordinal);
            bool got = false;

            try
            {
                NativeArray<byte> bpv = mesh.GetBonesPerVertex();
                if (bpv.Length == vc)
                {
                    NativeArray<BoneWeight1> bw = mesh.GetAllBoneWeights();
                    if (bw.Length > 0)
                    {
                        int k = 0;
                        for (int i = 0; i < vc; i++)
                        {
                            int c = bpv[i];
                            for (int j = 0; j < c; j++)
                            {
                                if (k >= bw.Length) break;
                                BoneWeight1 w = bw[k++];
                                if (w.weight <= 0f) continue;
                                string reg = (w.boneIndex >= 0 && w.boneIndex < boneRegion.Length)
                                    ? boneRegion[w.boneIndex] : "unknown";
                                AddW(wSum, reg, w.weight);
                            }
                        }
                        got = true;
                    }
                }
            }
            catch { }

            if (!got)
            {
                try
                {
                    BoneWeight[] bw = mesh.boneWeights;
                    if (bw != null && bw.Length == vc)
                    {
                        for (int i = 0; i < vc; i++)
                        {
                            BoneWeight w = bw[i];
                            AccW(wSum, w.boneIndex0, w.weight0, boneRegion);
                            AccW(wSum, w.boneIndex1, w.weight1, boneRegion);
                            AccW(wSum, w.boneIndex2, w.weight2, boneRegion);
                            AccW(wSum, w.boneIndex3, w.weight3, boneRegion);
                        }
                        got = true;
                    }
                }
                catch { }
            }
            if (!got) return false;

            double total = 0, foot = 0, torso = 0;
            foreach (var kv in wSum)
            {
                total += kv.Value;
                if (IsFootDetectRegion(kv.Key)) foot += kv.Value;
                if (IsTorsoRegion(kv.Key)) torso += kv.Value;
            }
            if (total <= 0) return false;
            return foot / total >= MinWeightShare && torso / total >= MinWeightShare;
        }

        // ─────────────────────────────────────────────────────────────
        // 部位名回退（给导入服装自带的独立骨架用；任务 AY / B-补-03）
        // ─────────────────────────────────────────────────────────────

        // 归一化后的「无侧别基础名」→ HumanBodyBones 枚举名（侧别另加 Left/Right 前缀）。
        // 覆盖 Blender/Maya 常见写法：Foot.L / Foot_L / Lower_leg.L / Upper_leg.R / Toe.L、
        // 以及 Unity 人形枚举本身的 lower-case（leftfoot…，由 left/right 前缀路径处理）。
        static readonly Dictionary<string, string> BaseNameToRegion = new Dictionary<string, string>(StringComparer.Ordinal)
        {
            { "hips", "Hips" },
            { "pelvis", "Hips" },
            { "spine", "Spine" },
            { "spine1", "Spine" },
            { "chest", "Chest" },
            { "spine2", "Chest" },
            { "upperchest", "UpperChest" },
            { "spine3", "UpperChest" },
            { "neck", "Neck" },
            { "head", "Head" },
            { "shoulder", "Shoulder" },
            { "clavicle", "Shoulder" },
            { "upperarm", "UpperArm" },
            { "lowerarm", "LowerArm" },
            { "forearm", "LowerArm" },
            { "hand", "Hand" },
            { "wrist", "Hand" },
            { "upperleg", "UpperLeg" },
            { "thigh", "UpperLeg" },
            { "lowerleg", "LowerLeg" },
            { "shin", "LowerLeg" },
            { "calf", "LowerLeg" },
            { "foot", "Foot" },
            { "ankle", "Foot" },
            { "toe", "Toes" },
            { "toes", "Toes" },
            { "toebase", "Toes" },
        };

        static readonly HashSet<string> SideNeutralRegions = new HashSet<string>(StringComparer.Ordinal)
        {
            "Hips", "Spine", "Chest", "UpperChest", "Neck", "Head",
        };

        /// <summary>把单根骨骼名按常见命名规则映射到 HumanBodyBones 枚举名（LeftFoot 等）。
        /// 认不出返回 false，不猜。用于导入服装自带独立骨架（bones 不是头像的人形 Transform，
        /// 按身份匹配全落 Other）——Kipfel/Milfy 服装 FBX 的 Foot.L / Toe.L 即此类。</summary>
        public static bool TryNameRegion(string boneName, out string region)
        {
            region = null;
            string n = NormBone(boneName);
            if (n.Length == 0) return false;

            string direct;
            if (BaseNameToRegion.TryGetValue(n, out direct)) { region = direct; return true; }

            string side = null;
            string body = n;
            if (n.Length > 1)
            {
                char last = n[n.Length - 1];
                if (last == 'l' || last == 'r')
                {
                    side = last == 'l' ? "Left" : "Right";
                    body = n.Substring(0, n.Length - 1);
                }
            }
            if (side == null)
            {
                if (n.StartsWith("left", StringComparison.Ordinal)) { side = "Left"; body = n.Substring(4); }
                else if (n.StartsWith("right", StringComparison.Ordinal)) { side = "Right"; body = n.Substring(5); }
            }

            string baseRegion;
            if (side != null && BaseNameToRegion.TryGetValue(body, out baseRegion))
            {
                region = SideNeutralRegions.Contains(baseRegion) ? baseRegion : side + baseRegion;
                return true;
            }
            region = null;
            return false;
        }

        /// <summary>沿父链找第一个能按名字判定部位的骨骼；找不到返回 null。
        /// 装饰骨（Shoes_Chain.001.L）自己认不出，但父链上会经过 Foot.L，故仍能归位。</summary>
        public static string RegionByNameChain(Transform t, Transform root)
        {
            Transform cur = t;
            int guard = 0;
            while (cur != null && guard++ < BoneWalkGuard)
            {
                string r;
                if (TryNameRegion(cur.name, out r)) return r;
                if (cur == root) break;
                cur = cur.parent;
            }
            return null;
        }

        static string NormBone(string s)
        {
            if (string.IsNullOrEmpty(s)) return "";
            var sb = new StringBuilder(s.Length);
            for (int i = 0; i < s.Length; i++)
            {
                char c = s[i];
                if (char.IsLetterOrDigit(c)) sb.Append(char.ToLowerInvariant(c));
            }
            return sb.ToString();
        }

        static void AccW(Dictionary<string, double> d, int bi, float weight, string[] boneRegion)
        {
            if (weight <= 0f) return;
            string reg = (bi >= 0 && bi < boneRegion.Length) ? boneRegion[bi] : "unknown";
            AddW(d, reg, weight);
        }

        static void AddW(Dictionary<string, double> d, string k, double v)
        {
            double cur; d.TryGetValue(k, out cur); d[k] = cur + v;
        }

        static bool ExactIn(string[] arr, string v)
        {
            if (string.IsNullOrEmpty(v)) return false;
            for (int i = 0; i < arr.Length; i++) if (arr[i] == v) return true;
            return false;
        }
    }
}
