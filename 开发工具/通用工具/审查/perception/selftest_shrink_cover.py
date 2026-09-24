#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""任务 CT/CU：shrink_cover「遮挡集合名单 + 自检 + 外向射线几何」纯离线自检（不起 Unity）。
【项目沉淀】通用工具
适用素体：无关
相关素材：仓库内 shrink_cover 样例数据
工具链　：Python 3（离线）
可复用性：★ 针对特定任务的离线自检，主要供参考
用途　　：shrink_cover「遮挡集合名单 + 自检 + 外向射线几何」纯离线自检（不起 Unity）。


为什么有这份：任务 CS 的 T-33 shrink_cover 第一次实跑，工程B Milfy 43% 的四个状态
**每一个键都判 uncovered、uncovered_ratio 全是 1.0**（连穿着外套的 Shoulder/Chest_2、
穿着袜子的 Ankle 也是）。根因不是几何，是名单：
  ① `garments_exclude` 拿整条路径匹配，默认串里的无界词 `ear` 命中 `_Outfit/LopEarMine/...`，
     整套在穿的 LopEar 外套/袜子/鞋被排除（`head`/`face` 命中祖先名同理）。
  ② 身体自己（`Body`）留在集合里，被测键却长在身体上（`Body_base`）——「身体盖自己」会反转成假阴性。
任务 CU 再把「遮挡」判据从「到衣服表面的距离」换成「身体外向射线」——距离回答的是「附近有没有布」，
不是「我外面有没有布」，宽松外套/鞋帮旁边的裸脚踝都会判错（见 seq_t33_calib）。

本脚本把 `unity/Editor/AuditProbes.cs` 里 `SHRINK_COVER_RULES_BEGIN/END` 标记之间的
纯层（`ShrinkCoverRules` 名单规则 + `ShrinkCoverRayRules` 外向射线几何，都不依赖 UnityEngine）
整段抽出来，配一个最小 C# 测试程序，用 mono 的 mcs 编译后直接 `mono` 运行——**测的就是生产同一份源码**，
不是重新写一份（生产中 PokeBvh.Raycast 也调这里的 RayHitsTriangle）。

覆盖（任务 CT 验收）：
  ① 路径含 `ear` 的衣服不被排除（叶子名 `LopEarMine`；`ear` 只是子串）
  ② 叶子名就是 `Ear` 的（`Ear` / `Hair_Front` / `Jacket_Ear`）被排除
  ③ 身体网格被排除（`Body_base` 指定 body → `Body` / `Body_b2` / body 自己）
  ④ `garments_used==0`（以及 keys 为空 / 全 uncovered / used:considered<0.2）→ verdict 全 `undecidable`
  ⑤ 生产 43% 快照的可见 SMR 夹具：旧口径 used=3（Body/Bra/Crown）复现误报，新口径把 LopEar 整套收回集合

覆盖（任务 CU 验收，几何级，自造三角形 + 顶点法线，不需要 Unity）：
  ⑥① 顶点外侧 20 mm 有布 → 判遮住；⑥② 布在顶点旁边（法线方向没有）→ 判没遮住；
  ⑥③ `any` 与 `majority` 各一例（votes=1 时 any 遮/majority 不遮；votes=3 时两者都遮）；
  ⑥④/⑤ `cover_ray_mm` 真的参与（50 mm 够不着 55 mm 的布，60 mm 够得着）。

覆盖（任务 CX / B-T33b 验收，纯规则级）：
  ⑦ `verdict_rule` 四种取值各一例（含正样本形态「ratio 不过但 area 过 → or 判 uncovered、and 判 ok」）
     + `verdict_by` 的 ratio/area/both/none 四值 + 归一化 + `DefaultAreaThrCm2`=1.0。

产物落到 `_长程任务_20260918/派工/tmp/cu/`（.cs / .exe / .log），不改任何工程文件。
用法：`python3 开发工具/通用工具/审查/perception/selftest_shrink_cover.py`
"""

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[4]   # …/perception/selftest_*.py → parents[0]=perception … parents[4]=工作区根
PROBE = ROOT / "开发工具/通用工具/审查/unity/Editor/AuditProbes.cs"
OUT = ROOT / "_长程任务_20260918/派工/tmp/cu"
PROD_STATE = (ROOT / "_长程任务_20260918/审查产出/工程B/"
                     "seq_lopear_r9/01_measure/state_m_all_on.json")
PROD_SC = (ROOT / "_长程任务_20260918/审查产出/工程B/"
                  "seq_lopear_r9/01_measure/shrink_cover_m_all_on.json")

sys.path.insert(0, str(ROOT / "开发工具/通用工具"))
import kit_env  # noqa: E402  mono/mcs 取自 Unity 自带的 MonoBleedingEdge（kit.env 的 UNITY_DATA / UNITY_EDITOR_ROOT+UNITY_VERSION）

UNITY_DATA = kit_env.unity_data()
MONO = UNITY_DATA / "MonoBleedingEdge/bin/mono"
MCS = UNITY_DATA / "MonoBleedingEdge/lib/mono/4.5/mcs.exe"

BEGIN = "// >>> SHRINK_COVER_RULES_BEGIN"
END = "// <<< SHRINK_COVER_RULES_END"


def cs_escape(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


def extract_rules(text):
    if BEGIN not in text or END not in text:
        raise SystemExit("AuditProbes.cs 里找不到 SHRINK_COVER_RULES 标记，无法抽取规则层。")
    i = text.index(BEGIN)
    j = text.index(END)
    body = text[text.index("\n", i) + 1:j]
    # 规则层不得引用 UnityEngine；抽出来单独编译能过就是证明（注释里提到类型名不算）。
    code_lines = [ln for ln in body.splitlines() if not ln.lstrip().startswith("//")]
    code = "\n".join(code_lines)
    for bad in ("using UnityEngine", "UnityEngine.", "MonoBehaviour", "Vector3", "new Mesh", "SkinnedMeshRenderer"):
        if bad in code:
            raise SystemExit("规则层引用了 Unity 类型 '" + bad + "'，离线自检无法编译。")
    return body.rstrip()


def load_prod_fixture():
    """从生产快照取可见 SMR 夹具（叶子名 + 父路径 + 是否 body 自己）。读不到就返回 None。"""
    if not PROD_STATE.exists():
        return None
    d = json.loads(PROD_STATE.read_text(encoding="utf-8"))
    body = "Body_base"
    if PROD_SC.exists():
        sc = json.loads(PROD_SC.read_text(encoding="utf-8"))
        body = sc.get("body") or body
    entries = []
    for r in d.get("renderers", []):
        if r.get("type") != "SkinnedMeshRenderer" or not r.get("visible"):
            continue
        path = r["path"]
        leaf = path.split("/")[-1]
        parent = path.rsplit("/", 1)[0] if "/" in path else ""
        entries.append((path, leaf))
    body_parent = body.rsplit("/", 1)[0] if "/" in body else ""
    return body, body_parent, entries


def emit_entries(name, body_leaf, entries_with_parent):
    lines = []
    for path, leaf, parent in entries_with_parent:
        is_self = (path == body_leaf)
        same = (parent == (body_leaf.rsplit("/", 1)[0] if "/" in body_leaf else ""))
        lines.append('                new Entry("%s", "%s", %s, %s),'
                     % (cs_escape(path), cs_escape(leaf),
                        "true" if is_self else "false",
                        "true" if same else "false"))
    return "        static List<Entry> %s()\n        {\n            return new List<Entry>\n            {\n%s\n            };\n        }\n" % (name, "\n".join(lines))


def build_program(rules_region, prod):
    if prod is None:
        prod_method = ("        static List<Entry> ProdEntries()\n"
                       "        {\n            return new List<Entry>();\n        }\n")
        prod_note = 'Console.WriteLine("  SKIP  生产 43% 快照不存在，跳过夹具回归：" + PROD_PATH);'
    else:
        body, body_parent, entries = prod
        entries_with_parent = [(p, l, (p.rsplit("/", 1)[0] if "/" in p else "")) for p, l in entries]
        prod_method = emit_entries("ProdEntries", body, entries_with_parent)
        prod_note = 'Console.WriteLine("  生产夹具 body=" + PROD_BODY + "，可见 SMR=" + ProdEntries().Count);'

    template = r'''// 任务 CT 离线自检（由 perception/selftest_shrink_cover.py 自动生成）
using System;
using System.Collections.Generic;
using System.Text.RegularExpressions;

namespace AvatarAudit
{
__RULES__

    internal static class ShrinkCoverOfflineSelfCheck
    {
        static int pass = 0, fail = 0;
        const string PROD_PATH = "__PROD_PATH__";
        const string PROD_BODY = "__PROD_BODY__";

        static void Check(string name, bool ok) { Check(name, ok, ""); }
        static void Check(string name, bool ok, string detail)
        {
            if (ok) { pass++; Console.WriteLine("  PASS  " + name); }
            else { fail++; Console.WriteLine("  FAIL  " + name + "   " + detail); }
        }

        sealed class Entry
        {
            public string Path, Leaf; public bool Self, SameParent;
            public Entry(string p, string l, bool s, bool sp) { Path = p; Leaf = l; Self = s; SameParent = sp; }
        }

        sealed class Sim
        {
            public int Considered, Used, Excluded;
            public List<string> UsedLeaves = new List<string>();
            public List<string> ExcludedLeaves = new List<string>();
            public bool Suspicious; public string Reason;
        }

        // 生产同一份名单规则：可见 SMR − 身体家族 − garments_exclude（叶子名整词匹配）
        static Sim RunRules(List<Entry> entries, string bodyLeaf, int keysTotal, int keysUncovered)
        {
            var re = new Regex(ShrinkCoverRules.DefaultExcludeRegex, RegexOptions.CultureInvariant);
            var sim = new Sim();
            for (int i = 0; i < entries.Count; i++)
            {
                var e = entries[i];
                sim.Considered++;
                string hit;
                if (e.Self || ShrinkCoverRules.IsBodyLike(e.Leaf, e.Self, e.SameParent, bodyLeaf))
                { sim.Excluded++; sim.ExcludedLeaves.Add(e.Leaf + "|body"); continue; }
                if (ShrinkCoverRules.ExcludeHit(re, e.Leaf, out hit))
                { sim.Excluded++; sim.ExcludedLeaves.Add(e.Leaf + "|exclude:" + hit); continue; }
                sim.Used++; sim.UsedLeaves.Add(e.Leaf);
            }
            sim.Suspicious = ShrinkCoverRules.SelfCheckSuspicious(sim.Considered, sim.Used, keysTotal, keysUncovered, out sim.Reason);
            return sim;
        }

        // 旧口径（任务 CS 第一次实跑）：只排 body 自己；garments_exclude 拿名字或**整条路径**子串匹配。
        static List<string> OldUsed(List<Entry> entries)
        {
            var oldRe = new Regex("(?i)(hair|nail|lash|eye|face|tooth|tongue|head|halo|particle|avatarhight|tail|ear)",
                RegexOptions.CultureInvariant);
            var res = new List<string>();
            for (int i = 0; i < entries.Count; i++)
            {
                var e = entries[i];
                if (e.Self) continue;
                if (oldRe.IsMatch(e.Leaf) || oldRe.IsMatch(e.Path)) continue;
                res.Add(e.Leaf);
            }
            return res;
        }

        static string Join(List<string> l) { return string.Join(",", l.ToArray()); }

        static void TestWordMatching()
        {
            Console.WriteLine("-- ① 排除口径：只拿叶子名 + 整名/分隔符切词（旧 bug：ear 子串命中 LopEarMine）--");
            var re = new Regex(ShrinkCoverRules.DefaultExcludeRegex, RegexOptions.CultureInvariant);
            string hit;
            Check("① 叶子名 LopEarMine 不被排除（ear 只是子串）",
                !ShrinkCoverRules.ExcludeHit(re, "LopEarMine", out hit), "hit=" + hit);
            Check("① _Outfit/LopEarMine/.../Shoes|Socks|Tops 都不被排除",
                !ShrinkCoverRules.ExcludeHit(re, "Shoes", out hit)
                && !ShrinkCoverRules.ExcludeHit(re, "Socks", out hit)
                && !ShrinkCoverRules.ExcludeHit(re, "Tops", out hit), "hit=" + hit);
            var oldRe = new Regex("(?i)(hair|nail|lash|eye|face|tooth|tongue|head|halo|particle|avatarhight|tail|ear)",
                RegexOptions.CultureInvariant);
            Check("① 请求若传旧无锚点串，新匹配器也不子串命中 LopEarMine",
                !ShrinkCoverRules.ExcludeHit(oldRe, "LopEarMine", out hit), "hit=" + hit);
        }

        static void TestLeafExclude()
        {
            Console.WriteLine("-- ② 叶子名就是排除词的被排除 --");
            var re = new Regex(ShrinkCoverRules.DefaultExcludeRegex, RegexOptions.CultureInvariant);
            string hit;
            Check("② Ear 被排除", ShrinkCoverRules.ExcludeHit(re, "Ear", out hit) && hit == "Ear", "hit=" + hit);
            Check("② Hair_Front 被排除（词 Hair）",
                ShrinkCoverRules.ExcludeHit(re, "Hair_Front", out hit) && hit == "Hair", "hit=" + hit);
            Check("② Jacket_Ear 被排除（词 Ear）",
                ShrinkCoverRules.ExcludeHit(re, "Jacket_Ear", out hit) && hit == "Ear", "hit=" + hit);
            Check("② Shoes 不排除", !ShrinkCoverRules.ExcludeHit(re, "Shoes", out hit), "hit=" + hit);
            Check("② HeadDress 不排除（整词不是 head；宁可少排，换不误伤整套衣服）",
                !ShrinkCoverRules.ExcludeHit(re, "HeadDress", out hit), "hit=" + hit);
        }

        static void TestBodyFamily()
        {
            Console.WriteLine("-- ③ 身体网格（body 自己 + 同素体其它片）被排除 --");
            Check("③ BodyFamilyRoot(Body_base)=Body", ShrinkCoverRules.BodyFamilyRoot("Body_base") == "Body");
            Check("③ BodyFamilyRoot(Body_b12)=Body", ShrinkCoverRules.BodyFamilyRoot("Body_b12") == "Body");
            Check("③ BodyFamilyRoot(Body)=Body", ShrinkCoverRules.BodyFamilyRoot("Body") == "Body");
            Check("③ body 自己 → 排除", ShrinkCoverRules.IsBodyLike("Body_base", true, true, "Body_base"));
            Check("③ Body 与 Body_base 同父 → 排除", ShrinkCoverRules.IsBodyLike("Body", false, true, "Body_base"));
            Check("③ Body_b2 词根相同 → 排除", ShrinkCoverRules.IsBodyLike("Body_b2", false, false, "Body_base"));
            Check("③ Bra 不排除", !ShrinkCoverRules.IsBodyLike("Bra", false, true, "Body_base"));
            Check("③ Body_Stocking_breasts_big（身体贴图袜，不同父不同词根）不排除",
                !ShrinkCoverRules.IsBodyLike("Body_Stocking_breasts_big", false, false, "Body_base"));
        }

        static void TestSelfCheck()
        {
            Console.WriteLine("-- ④ 自检：used==0 / keys 空 / 全 uncovered / used:considered<0.2 → undecidable --");
            string reason;
            Check("④ garments_used==0 → suspicious 且有中文原因",
                ShrinkCoverRules.SelfCheckSuspicious(5, 0, 3, 3, out reason) && !string.IsNullOrEmpty(reason), reason);
            Check("④ suspicious 时 uncovered→undecidable",
                ShrinkCoverRules.VerdictAfterSelfCheck(true, "uncovered") == "undecidable");
            Check("④ suspicious 时 ok→undecidable",
                ShrinkCoverRules.VerdictAfterSelfCheck(true, "ok") == "undecidable");
            Check("④ 不可疑时 verdict 原样", ShrinkCoverRules.VerdictAfterSelfCheck(false, "uncovered") == "uncovered");
            Check("④ keys 为空 → suspicious", ShrinkCoverRules.SelfCheckSuspicious(10, 8, 0, 0, out reason));
            Check("④ 所有键 uncovered → suspicious", ShrinkCoverRules.SelfCheckSuspicious(10, 8, 3, 3, out reason));
            Check("④ used:considered=5/100 < 0.2 → suspicious", ShrinkCoverRules.SelfCheckSuspicious(100, 5, 3, 1, out reason));
            Check("④ 正常（10 件用 8、3 键只 1 uncovered）→ 不可疑",
                !ShrinkCoverRules.SelfCheckSuspicious(10, 8, 3, 1, out reason), reason);

            // 数据结构级：0 件可见服装时，整批键的 verdict 必须全 undecidable。
            var sim = RunRules(new List<Entry>(), "Body_base", 3, 3);
            var verdicts = new List<string>();
            verdicts.Add(ShrinkCoverRules.VerdictAfterSelfCheck(sim.Suspicious, "uncovered"));
            verdicts.Add(ShrinkCoverRules.VerdictAfterSelfCheck(sim.Suspicious, "ok"));
            verdicts.Add(ShrinkCoverRules.VerdictAfterSelfCheck(sim.Suspicious, "too_few_verts"));
            Check("④ garments_used==0 的模拟：suspicious 且三行 verdict 全 undecidable",
                sim.Used == 0 && sim.Suspicious
                && verdicts[0] == "undecidable" && verdicts[1] == "undecidable" && verdicts[2] == "undecidable",
                "verdicts=" + Join(verdicts) + " reason=" + sim.Reason);
        }

        static void TestMinFixture()
        {
            Console.WriteLine("-- ⑤ 最小数据结构夹具（List<Entry>，模拟生产可见 SMR 名单）--");
            var fixture = new List<Entry>
            {
                new Entry("_Outfit/LopEarMine/08_WhitePink_Milfy_MA/Shoes", "Shoes", false, false),
                new Entry("_Outfit/LopEarMine/08_WhitePink_Milfy_MA/Socks", "Socks", false, false),
                new Entry("_Outfit/LopEarMine/08_WhitePink_Milfy_MA/Tops", "Tops", false, false),
                new Entry("_Outfit/LopEarMine/08_WhitePink_Hood_Off/Jacket", "Jacket", false, false),
                new Entry("Body_base", "Body_base", true, true),
                new Entry("Body", "Body", false, true),
                new Entry("Bra", "Bra", false, true),
                new Entry("Hair_Front", "Hair_Front", false, true),
                new Entry("Ear", "Ear", false, true),
            };
            var sim = RunRules(fixture, "Body_base", 12, 1);
            Check("⑤ LopEar 整套（Shoes/Socks/Tops/Jacket）进遮挡集合",
                sim.UsedLeaves.Contains("Shoes") && sim.UsedLeaves.Contains("Socks")
                && sim.UsedLeaves.Contains("Tops") && sim.UsedLeaves.Contains("Jacket"),
                "used=" + Join(sim.UsedLeaves));
            Check("⑤ 身体家族（Body_base/Body）被排除",
                !sim.UsedLeaves.Contains("Body_base") && !sim.UsedLeaves.Contains("Body"),
                "excluded=" + Join(sim.ExcludedLeaves));
            Check("⑤ Hair_Front/Ear 被排除", !sim.UsedLeaves.Contains("Hair_Front") && !sim.UsedLeaves.Contains("Ear"),
                "used=" + Join(sim.UsedLeaves));
            Check("⑤ 夹具不可疑（used=4/9 ≥ 0.2 且非全 uncovered）", !sim.Suspicious, sim.Reason);
        }

        static void TestProdFixture()
        {
            Console.WriteLine("-- ⑤b 生产 43% 快照夹具：旧口径复现误报，新口径收回 LopEar --");
__PROD_NOTE__
            var entries = ProdEntries();
            if (entries.Count == 0) return;
            var oldUsed = OldUsed(entries);
            Console.WriteLine("  旧口径 used=" + oldUsed.Count + " [" + Join(oldUsed) + "]");
            Check("⑤b 旧口径只剩 " + oldUsed.Count + " 件（复现生产 garments=[Body,Bra,Crown]）",
                oldUsed.Count == 3 && oldUsed.Contains("Body") && oldUsed.Contains("Bra") && oldUsed.Contains("Crown"),
                "old=" + Join(oldUsed));
            var sim = RunRules(entries, PROD_BODY, 12, 0);
            Console.WriteLine("  新口径 used=" + sim.Used + "/" + sim.Considered + "，排除 " + sim.Excluded + " 件");
            Console.WriteLine("  新口径进集合：" + Join(sim.UsedLeaves));
            Check("⑤b 新口径把 LopEar 的 Shoes/Socks/Tops/Jacket 收回集合",
                sim.UsedLeaves.Contains("Shoes") && sim.UsedLeaves.Contains("Socks")
                && sim.UsedLeaves.Contains("Tops") && sim.UsedLeaves.Contains("Jacket"),
                "used=" + Join(sim.UsedLeaves));
            Check("⑤b 新口径不再含身体片 Body（假阴性来源）", !sim.UsedLeaves.Contains("Body"),
                "used=" + Join(sim.UsedLeaves));
            Check("⑤b 新口径 used/considered=" + sim.Used + "/" + sim.Considered + " ≥ 0.2 且不可疑",
                sim.Used * 5 >= sim.Considered && !sim.Suspicious, sim.Reason);
        }

__PROD_METHOD__        // ── 任务 CU：几何级用例（自造三角形 + 顶点法线，不需要 Unity）─────────────────
        // 布片 = 水平矩形（y = cy），法线方向 +Y；顶点在原点。锥向射线绕两个切轴 ±20°，
        // 在 y=20mm 平面上的横向偏移 ≈ 20*tan20° ≈ 7.3mm —— 用布的宽窄控制命中票数。
        static void AddQuad(List<float> flat, List<int> tris, float cx, float cy, float cz, float hx, float hz)
        {
            int b = flat.Count / 3;
            flat.Add(cx - hx); flat.Add(cy); flat.Add(cz - hz);
            flat.Add(cx + hx); flat.Add(cy); flat.Add(cz - hz);
            flat.Add(cx + hx); flat.Add(cy); flat.Add(cz + hz);
            flat.Add(cx - hx); flat.Add(cy); flat.Add(cz + hz);
            tris.Add(b); tris.Add(b + 1); tris.Add(b + 2);
            tris.Add(b); tris.Add(b + 2); tris.Add(b + 3);
        }

        static void TestGeometry()
        {
            Console.WriteLine("-- ⑥ 几何级：外向射线判据（自造三角形 + 顶点法线）--");
            var pos = new ScVec(0f, 0f, 0f);
            var n = new ScVec(0f, 1f, 0f);
            var flat = new List<float>();
            var tris = new List<int>();
            int v;

            // ① 顶点外侧 20 mm 一片大布：中轴 + 4 条锥向全命中 → 判遮住
            AddQuad(flat, tris, 0f, 0.020f, 0f, 0.100f, 0.100f);
            v = ShrinkCoverRayRules.RayVotesOnTriangles(pos, n, flat.ToArray(), tris.ToArray(), 0f, 0.050f, 20f);
            Check("⑥① 顶点外侧 20mm 有布 → 命中 " + v + "/5 → any 判遮住",
                v == 5 && ShrinkCoverRayRules.RuleSatisfied("any", v, 5), "votes=" + v);

            // ② 布在顶点旁边（+X 60mm），法线 +Y 方向没有 → 判没遮住
            flat.Clear(); tris.Clear();
            AddQuad(flat, tris, 0.060f, 0.020f, 0f, 0.020f, 0.020f);
            v = ShrinkCoverRayRules.RayVotesOnTriangles(pos, n, flat.ToArray(), tris.ToArray(), 0f, 0.050f, 20f);
            Check("⑥② 布在顶点旁边（法线方向没有）→ 命中 " + v + " → 判没遮住",
                v == 0 && !ShrinkCoverRayRules.RuleSatisfied("any", v, 5), "votes=" + v);

            // ③a 只有中轴射线打到（极小布片 ±1mm）→ votes=1：any 遮住、majority 不遮（差别之一）
            flat.Clear(); tris.Clear();
            AddQuad(flat, tris, 0f, 0.020f, 0f, 0.001f, 0.001f);
            v = ShrinkCoverRayRules.RayVotesOnTriangles(pos, n, flat.ToArray(), tris.ToArray(), 0f, 0.050f, 20f);
            Check("⑥③a 只有中轴射线命中（votes=" + v + "）→ any 判遮住",
                v == 1 && ShrinkCoverRayRules.RuleSatisfied("any", v, 5), "votes=" + v);
            Check("⑥③a 同一例 majority 判没遮住（any/majority 差别）",
                !ShrinkCoverRayRules.RuleSatisfied("majority", v, 5), "votes=" + v);

            // ③b 沿切线宽、法向窄的布（±50mm × ±2mm）→ 中轴 + 2 条锥向 = 3 票：majority 边界，两者都遮
            flat.Clear(); tris.Clear();
            AddQuad(flat, tris, 0f, 0.020f, 0f, 0.050f, 0.002f);
            v = ShrinkCoverRayRules.RayVotesOnTriangles(pos, n, flat.ToArray(), tris.ToArray(), 0f, 0.050f, 20f);
            Check("⑥③b votes=3 → any 与 majority 都判遮住（majority 边界）",
                v == 3 && ShrinkCoverRayRules.RuleSatisfied("any", v, 5) && ShrinkCoverRayRules.RuleSatisfied("majority", v, 5),
                "votes=" + v);

            // ④ 布在 55mm、射线长 50mm → 够不着，判没遮住（确认 cover_ray_mm 真的参与）
            flat.Clear(); tris.Clear();
            AddQuad(flat, tris, 0f, 0.055f, 0f, 0.100f, 0.100f);
            v = ShrinkCoverRayRules.RayVotesOnTriangles(pos, n, flat.ToArray(), tris.ToArray(), 0f, 0.050f, 20f);
            Check("⑥④ 布在 55mm、射线长 50mm → 命中 " + v + " → 判没遮住", v == 0, "votes=" + v);

            // ⑤ 同一片布、射线长 60mm → 命中 5/5（长度参数生效）
            v = ShrinkCoverRayRules.RayVotesOnTriangles(pos, n, flat.ToArray(), tris.ToArray(), 0f, 0.060f, 20f);
            Check("⑥⑤ 同一片布、射线长 60mm → 命中 " + v + "/5 → 判遮住", v == 5, "votes=" + v);
        }

        // ── 任务 CX（B-T33b）：verdict 判据形状 + verdict_by ─────────────────
        static void TestVerdictRule()
        {
            Console.WriteLine("-- ⑦ 任务 CX：verdict_rule 四种取值 + verdict_by（ratio 不过但 area 过）--");
            // 正样本 A(Ankle) 实测形态：uncovered_ratio=9.5% < 0.6（ratio 不过），uncovered_area=6.86 cm² ≥ 1.0（area 过）。
            bool ratioOk = false, areaOk = true;
            Check("⑦ or（默认）：ratio 不过但 area 过 → uncovered",
                ShrinkCoverRules.UncoveredByRule("or", ratioOk, areaOk));
            Check("⑦ and（旧行为）：ratio 不过但 area 过 → 不是 uncovered",
                !ShrinkCoverRules.UncoveredByRule("and", ratioOk, areaOk));
            Check("⑦ ratio_only：ratio 不过 → 不是 uncovered",
                !ShrinkCoverRules.UncoveredByRule("ratio_only", ratioOk, areaOk));
            Check("⑦ area_only：area 过 → uncovered",
                ShrinkCoverRules.UncoveredByRule("area_only", ratioOk, areaOk));
            Check("⑦ or/and 两条件都过 → uncovered",
                ShrinkCoverRules.UncoveredByRule("or", true, true) && ShrinkCoverRules.UncoveredByRule("and", true, true));
            Check("⑦ or/and 两条件都不过 → 不是 uncovered",
                !ShrinkCoverRules.UncoveredByRule("or", false, false) && !ShrinkCoverRules.UncoveredByRule("and", false, false));
            Check("⑦ verdict_by：both", ShrinkCoverRules.VerdictBy(true, true) == "both");
            Check("⑦ verdict_by：ratio", ShrinkCoverRules.VerdictBy(true, false) == "ratio");
            Check("⑦ verdict_by：area", ShrinkCoverRules.VerdictBy(false, true) == "area");
            Check("⑦ verdict_by：none", ShrinkCoverRules.VerdictBy(false, false) == "none");
            Check("⑦ verdict_rule 空/未知 → 归一化为 or",
                ShrinkCoverRules.NormalizeVerdictRule(null) == "or"
                && ShrinkCoverRules.NormalizeVerdictRule("bogus") == "or");
            Check("⑦ verdict_rule 大小写不敏感：AND → and",
                ShrinkCoverRules.NormalizeVerdictRule("AND") == "and");
            Check("⑦ default area_thr 有推导且为 1.0（待 B-T33b 标定）",
                Math.Abs(ShrinkCoverRules.DefaultAreaThrCm2 - 1.0) < 1e-9);
        }

        public static int Main(string[] args)
        {
            Console.WriteLine("== shrink_cover 名单/自检 + 外向射线几何 纯离线自检（perception/selftest_shrink_cover.py）==");
            TestWordMatching();
            TestLeafExclude();
            TestBodyFamily();
            TestSelfCheck();
            TestMinFixture();
            TestProdFixture();
            TestGeometry();
            TestVerdictRule();
            Console.WriteLine(string.Format("== {0} PASS / {1} FAIL ==", pass, fail));
            return fail == 0 ? 0 : 1;
        }
    }
}
'''
    prog = template.replace("__RULES__", rules_region)
    prog = prog.replace("__PROD_PATH__", cs_escape(str(PROD_STATE)))
    prog = prog.replace("__PROD_BODY__", "Body_base" if prod is None else cs_escape(prod[0]))
    prog = prog.replace("__PROD_NOTE__", prod_note)
    prog = prog.replace("__PROD_METHOD__", prod_method)
    return prog


def main():
    if not MONO.exists() or not MCS.exists():
        raise SystemExit("找不到 mono/mcs：%s / %s（在 kit.env 设 UNITY_DATA）" % (MONO, MCS))
    text = PROBE.read_text(encoding="utf-8")
    rules = extract_rules(text)
    prod = load_prod_fixture()
    prog = build_program(rules, prod)

    OUT.mkdir(parents=True, exist_ok=True)
    cs = OUT / "ShrinkCoverOfflineSelfCheck.cs"
    exe = OUT / "shrink_cover_selfcheck.exe"
    log = OUT / "shrink_cover_selfcheck.log"
    cs.write_text(prog, encoding="utf-8")

    print("抽取规则层：%d 行，来自 %s" % (len(rules.splitlines()), PROBE.relative_to(ROOT)))
    print("生成：%s" % cs.relative_to(ROOT))
    compile_cmd = [str(MONO), str(MCS), "-nologo", "-out:" + str(exe), str(cs)]
    cp = subprocess.run(compile_cmd, capture_output=True, text=True)
    if cp.returncode != 0:
        print(cp.stdout)
        print(cp.stderr, file=sys.stderr)
        raise SystemExit("mcs 编译失败 EXIT=%d" % cp.returncode)
    run = subprocess.run([str(MONO), str(exe)], capture_output=True, text=True)
    out = run.stdout + run.stderr
    print(out)
    log.write_text(out, encoding="utf-8")
    print("（日志：%s）" % log.relative_to(ROOT))
    return run.returncode


if __name__ == "__main__":
    sys.exit(main())
