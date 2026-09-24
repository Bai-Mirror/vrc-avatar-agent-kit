// ══════════════════════════════════════════════════════════════════
// 【项目沉淀】依赖编译器 · 计划层（T-06 离线可跑的部分）
//
// 适用素体：无关（输入 <工程>/_感知/decl.json + out/inventory.json）。
// 用途：把声明里的 `writer: gen|ours_legacy` 条目编译成「写者计划」：
//   · sc   后端：在「覆盖件物体」上挂 MA ShapeChanger（条件 = 该物体可见）
//   · clip 后端：在我方 FX 控制器里生成 `Decl: <dep_id>` 层（两态显式写值）
//   本文件只产出计划与指纹，不碰 Unity；Unity 侧由 DepCompiler.cs 执行。
//
// 为什么单独抽出来：引用 MA 程序集的执行代码离线编不了，而「选哪个后端、
//   条件怎么变成 Animator 条件、两态写什么值」这些逻辑必须能离线验证。
//   本文件 + DeclJson.cs 不 using UnityEditor / UnityEngine。
//
// 后端判定（按 04 清单 T-06 一节）：
//   sc   仅用于 kind ∈ {D1,D3}、动作是形态键 Set、条件化简后是
//        「若干 vis(部件) 的或」、且这些部件按 inventory.json 是 activeSelf 切换；
//   clip 用于其余（D4a/D4b/D6/D7，以及条件含否定/与/整套档位/m_Enabled 的件）。
// ══════════════════════════════════════════════════════════════════
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using AvatarAudit;

namespace AvatarGen
{
    // ───────────────────────── 条件 / DNF ─────────────────────────

    public enum CondMode { If, IfNot, Greater, Less }

    public struct Cond
    {
        public CondMode Mode;
        public float Threshold;
        public string Param;

        public Cond(CondMode m, float t, string p) { Mode = m; Threshold = t; Param = p; }

        public Cond Negate()
        {
            switch (Mode)
            {
                case CondMode.If: return new Cond(CondMode.IfNot, 0f, Param);
                case CondMode.IfNot: return new Cond(CondMode.If, 0f, Param);
                case CondMode.Greater: return new Cond(CondMode.Less, Threshold, Param);
                default: return new Cond(CondMode.Greater, Threshold, Param);
            }
        }

        public string Key
        {
            get { return ((int)Mode).ToString(CultureInfo.InvariantCulture) + "|" + Param + "|" + Threshold.ToString("0.######", CultureInfo.InvariantCulture); }
        }

        public override string ToString()
        {
            switch (Mode)
            {
                case CondMode.If: return Param + "==1";
                case CondMode.IfNot: return Param + "==0";
                case CondMode.Greater: return Param + ">" + Fmt(Threshold);
                default: return Param + "<" + Fmt(Threshold);
            }
        }

        internal static string Fmt(float f)
        {
            return f.ToString("0.######", CultureInfo.InvariantCulture);
        }
    }

    /// <summary>析取范式：Clauses 的每一项是一个「与」子句；空表 = 永假，含一个空子句 = 永真。</summary>
    public sealed class Dnf
    {
        public List<List<Cond>> Clauses = new List<List<Cond>>();

        public static Dnf True() { var d = new Dnf(); d.Clauses.Add(new List<Cond>()); return d; }
        public static Dnf False() { return new Dnf(); }
        public static Dnf Single(Cond c) { var d = new Dnf(); d.Clauses.Add(new List<Cond> { c }); return d; }

        public static Dnf Or(Dnf a, Dnf b)
        {
            var d = new Dnf();
            d.Clauses.AddRange(a.Clauses);
            d.Clauses.AddRange(b.Clauses);
            return d;
        }

        public static Dnf And(Dnf a, Dnf b)
        {
            var d = new Dnf();
            for (int i = 0; i < a.Clauses.Count; i++)
                for (int j = 0; j < b.Clauses.Count; j++)
                {
                    var c = new List<Cond>(a.Clauses[i]);
                    c.AddRange(b.Clauses[j]);
                    d.Clauses.Add(c);
                }
            return d;
        }

        public static Dnf Not(Dnf a)
        {
            var r = True();
            for (int i = 0; i < a.Clauses.Count; i++)
            {
                var clNot = False();
                var cl = a.Clauses[i];
                for (int j = 0; j < cl.Count; j++) clNot = Or(clNot, Single(cl[j].Negate()));
                r = And(r, clNot);
            }
            return r;
        }

        /// <summary>排序 + 去重，保证两次编译的层/条件字节一致。</summary>
        public Dnf Normalized()
        {
            var d = new Dnf();
            var seen = new HashSet<string>();
            for (int i = 0; i < Clauses.Count; i++)
            {
                var cl = new List<Cond>(Clauses[i]);
                cl.Sort(delegate (Cond a, Cond b) { return string.CompareOrdinal(a.Key, b.Key); });
                var uniq = new List<Cond>();
                for (int j = 0; j < cl.Count; j++)
                    if (j == 0 || cl[j].Key != cl[j - 1].Key) uniq.Add(cl[j]);
                var key = ClauseKey(uniq);
                if (!seen.Add(key)) continue;
                d.Clauses.Add(uniq);
            }
            d.Clauses.Sort(delegate (List<Cond> a, List<Cond> b) { return string.CompareOrdinal(ClauseKey(a), ClauseKey(b)); });
            return d;
        }

        public static string ClauseKey(List<Cond> cl)
        {
            var sb = new StringBuilder();
            for (int i = 0; i < cl.Count; i++) { if (i > 0) sb.Append("&"); sb.Append(cl[i].Key); }
            return sb.ToString();
        }

        public string Text
        {
            get
            {
                var d = Normalized();
                if (d.Clauses.Count == 0) return "false";
                var parts = new List<string>();
                for (int i = 0; i < d.Clauses.Count; i++)
                {
                    var cl = d.Clauses[i];
                    if (cl.Count == 0) return "true";
                    var terms = new List<string>();
                    for (int j = 0; j < cl.Count; j++) terms.Add(cl[j].ToString());
                    parts.Add(string.Join(" & ", terms.ToArray()));
                }
                return string.Join(" | ", parts.ToArray());
            }
        }

        /// <summary>用参数默认值求值：决定层的默认状态（On 还是 Off）。</summary>
        public bool Evaluate(Dictionary<string, float> defs)
        {
            var d = Normalized();
            for (int i = 0; i < d.Clauses.Count; i++)
            {
                bool all = true;
                var cl = d.Clauses[i];
                for (int j = 0; j < cl.Count; j++)
                {
                    float v;
                    if (!defs.TryGetValue(cl[j].Param, out v)) { all = false; break; }
                    switch (cl[j].Mode)
                    {
                        case CondMode.If: if (v < 0.5f) all = false; break;
                        case CondMode.IfNot: if (v >= 0.5f) all = false; break;
                        case CondMode.Greater: if (!(v > cl[j].Threshold)) all = false; break;
                        case CondMode.Less: if (!(v < cl[j].Threshold)) all = false; break;
                    }
                    if (!all) break;
                }
                if (all) return true;
            }
            return false;
        }
    }

    // ───────────────────────── when 表达式 AST / 解析 ─────────────────────────

    public abstract class PExpr { }
    public sealed class PTrue : PExpr { }
    public sealed class PFalse : PExpr { }
    public sealed class PNot : PExpr { public PExpr Inner; }
    public sealed class PAnd : PExpr { public List<PExpr> Items = new List<PExpr>(); }
    public sealed class POr : PExpr { public List<PExpr> Items = new List<PExpr>(); }
    public sealed class PVis : PExpr { public string Name; }
    public sealed class PParam : PExpr { public string Kind; public string Name; public string Value; }
    public sealed class PRange : PExpr { public string Param; public List<float[]> Ranges = new List<float[]>(); }
    public sealed class PUnsupported : PExpr
    {
        public string Reason;
        public PUnsupported(string reason) { Reason = reason; }
    }

    /// <summary>条件文法：true/false、!、&amp;、|、括号、vis(part)、slot(x)=1、ctl(x)=1、outfit in {…}。</summary>
    public sealed class ExprParser
    {
        private readonly string _s;
        private int _i;
        private readonly DeclDoc _doc;

        public ExprParser(string s, DeclDoc doc) { _s = s ?? ""; _doc = doc; }

        public static PExpr Parse(string s, DeclDoc doc)
        {
            if (string.IsNullOrEmpty(s)) return new PFalse();
            var p = new ExprParser(s, doc);
            var e = p.ParseOr();
            p.SkipWs();
            if (p._i < p._s.Length) return new PUnsupported("多余字符 @" + p._i);
            return e;
        }

        private void SkipWs() { while (_i < _s.Length && char.IsWhiteSpace(_s[_i])) _i++; }
        private bool Eat(char c) { SkipWs(); if (_i < _s.Length && _s[_i] == c) { _i++; return true; } return false; }
        private bool Peek(string t) { SkipWs(); return _i + t.Length <= _s.Length && _s.Substring(_i, t.Length) == t; }

        private PExpr ParseOr()
        {
            var left = ParseAnd();
            var or = new POr();
            or.Items.Add(left);
            while (Eat('|')) or.Items.Add(ParseAnd());
            return or.Items.Count == 1 ? or.Items[0] : or;
        }

        private PExpr ParseAnd()
        {
            var left = ParseFactor();
            var and = new PAnd();
            and.Items.Add(left);
            while (Eat('&')) and.Items.Add(ParseFactor());
            return and.Items.Count == 1 ? and.Items[0] : and;
        }

        private PExpr ParseFactor()
        {
            SkipWs();
            if (_i < _s.Length && _s[_i] == '!') { _i++; var n = new PNot(); n.Inner = ParseFactor(); return n; }
            if (_i < _s.Length && _s[_i] == '(')
            {
                _i++;
                var e = ParseOr();
                if (!Eat(')')) return new PUnsupported("括号未闭合");
                return e;
            }
            return ParsePredicate();
        }

        private string ReadIdent()
        {
            SkipWs();
            int start = _i;
            while (_i < _s.Length && (char.IsLetterOrDigit(_s[_i]) || _s[_i] == '_' || _s[_i] == '.' || _s[_i] == '-')) _i++;
            return _s.Substring(start, _i - start);
        }

        private string ReadParenArg()
        {
            if (!Eat('(')) return null;
            int start = _i;
            int depth = 1;
            while (_i < _s.Length && depth > 0)
            {
                if (_s[_i] == '(') depth++;
                else if (_s[_i] == ')') depth--;
                if (depth == 0) break;
                _i++;
            }
            var arg = _s.Substring(start, _i - start);
            if (_i < _s.Length && _s[_i] == ')') _i++;
            return arg.Trim();
        }

        // {A, B} 名字集合（名字里可含空格，逗号分隔）
        private List<string> ReadBraceList()
        {
            var res = new List<string>();
            SkipWs();
            if (_i >= _s.Length || _s[_i] != '{') return res;
            _i++;
            int start = _i;
            int depth = 1;
            while (_i < _s.Length && depth > 0)
            {
                if (_s[_i] == '{') depth++;
                else if (_s[_i] == '}') { depth--; if (depth == 0) break; }
                _i++;
            }
            var inner = _s.Substring(start, _i - start);
            if (_i < _s.Length && _s[_i] == '}') _i++;
            foreach (var raw in inner.Split(','))
            {
                var t = raw.Trim();
                if (t.Length > 0) res.Add(t);
            }
            return res;
        }

        private PExpr ParsePredicate()
        {
            var id = ReadIdent();
            if (id.Length == 0) return new PUnsupported("位置 " + _i + " 处没有谓词");
            if (id == "true") return new PTrue();
            if (id == "false") return new PFalse();
            if (id == "outfit" || id == "pose")
            {
                SkipWs();
                if (!Peek("in")) return new PUnsupported(id + " 后缺 in");
                _i += 2;
                var labels = ReadBraceList();
                if (id == "pose") return new PUnsupported("pose in {...}（T-32，一期不编译）");
                return OutfitRange(labels);
            }
            var arg = ReadParenArg();
            if (arg == null) return new PUnsupported("谓词 " + id + " 缺参数");
            if (id == "vis") return new PVis { Name = arg };
            if (id == "chain") return new PUnsupported("chain(...)（取值不同，一期不编译）");
            if (id == "slot" || id == "ctl")
            {
                SkipWs();
                string val = "1";
                if (_i < _s.Length && _s[_i] == '=') { _i++; val = ReadIdent(); }
                return new PParam { Kind = id, Name = arg, Value = val };
            }
            return new PUnsupported("未知谓词 " + id + "()");
        }

        private PExpr OutfitRange(List<string> labels)
        {
            var pr = new PRange { Param = _doc.Menu.Outfit.Param };
            int n = _doc.Menu.Outfit.Labels.Count;
            if (n == 0) return new PUnsupported("menu.outfit 无 labels");
            for (int i = 0; i < labels.Count; i++)
            {
                int idx = _doc.Menu.Outfit.Labels.IndexOf(labels[i]);
                if (idx < 0) return new PUnsupported("outfit 档位未知：" + labels[i]);
                pr.Ranges.Add(SlotRange(idx, n));
            }
            return pr;
        }

        /// <summary>第 idx 档（共 n 档）的取值区间；第 0 档没有下界（默认值就是 0）。</summary>
        public static float[] SlotRange(int idx, int n)
        {
            float lo = idx <= 0 ? float.NegativeInfinity : idx / (float)n;
            float hi = (idx + 1) / (float)n;
            return new float[] { lo, hi };
        }
    }

    // ───────────────────────── 计划模型 ─────────────────────────

    public enum DepBackend { None, Sc, Clip }

    public sealed class WriterTarget
    {
        public string Path = "";       // 相对头像根的物体路径（写曲线的目标 / SC 的 Object）
        public string Property = "";   // "blendShape.<key>" 或 "m_IsActive"/"m_Enabled"
        public string Mesh = "";       // 人看的：目标网格 / 件名
        public float On, Off;
        public bool ActiveSelf;

        public string Canon { get { return Path + "|" + Property + "|" + On.ToString("0.######", CultureInfo.InvariantCulture) + "|" + Off.ToString("0.######", CultureInfo.InvariantCulture); } }
    }

    public sealed class ScWriter
    {
        public string DepId = "", Kind = "", WhenText = "", WriterText = "";
        public bool ReplacesLegacy;
        public List<string> HostParts = new List<string>();
        public List<string> HostPaths = new List<string>();
        public List<WriterTarget> Targets = new List<WriterTarget>();
        public string Fingerprint = "";
    }

    public sealed class ClipWriter
    {
        public string DepId = "", Kind = "", WriterText = "", WhenText = "";
        public string LayerName = "";
        /// <summary>clip 资产文件名主干（不含 _Off/_On.anim），由唯一化后的层名派生。</summary>
        public string FileStem = "";
        public List<WriterTarget> Targets = new List<WriterTarget>();
        public Dnf OnExpr = Dnf.True();
        public string OnExprText = "";
        public bool DefaultOn;
        public int LayerIndexHint = -1;
        public List<string> Notes = new List<string>();
        public string Fingerprint = "";
        /// <summary>Off→On 的转移子句（每个子句 = 一条转移；子句内的条件是与关系）。</summary>
        public List<List<Cond>> OffToOn = new List<List<Cond>>();
        /// <summary>On→Off 的转移子句（= Not(On) 的最小析取，每个子句一条转移）。</summary>
        public List<List<Cond>> OnToOff = new List<List<Cond>>();
        public int ExpectedTransitions { get { return OffToOn.Count + OnToOff.Count; } }
        public bool TransitionsTruncated;
    }

    public sealed class SkipEntry
    {
        public string DepId = "", Kind = "", Reason = "";
    }

    public sealed class DepPlanResult
    {
        public string DeclPath = "", DeclSha = "", InventoryPath = "", ControllerPath = "";
        public string Project = "", AvatarRoot = "", Scene = "";
        public int PartCount, DepCount;
        public List<ScWriter> Sc = new List<ScWriter>();
        public List<ClipWriter> Clip = new List<ClipWriter>();
        public List<SkipEntry> Skipped = new List<SkipEntry>();
        public List<string> Warnings = new List<string>();
        public int InsertIndex = -1;
        public string InsertAfter = "", InsertBefore = "";

        public int TotalTransitions
        {
            get
            {
                int n = 0;
                for (int i = 0; i < Clip.Count; i++) n += Clip[i].ExpectedTransitions;
                return n;
            }
        }

        public string Render()
        {
            var sb = new StringBuilder();
            sb.AppendLine("DepCompiler plan  (decl schema=" + "perception/0.2" + ")");
            sb.AppendLine("decl       : " + DeclPath);
            sb.AppendLine("  sha256   : " + DeclSha);
            sb.AppendLine("  project  : " + Project + "   avatar_root=" + AvatarRoot);
            sb.AppendLine("  scene    : " + Scene);
            sb.AppendLine("  parts    : " + PartCount + "   deps=" + DepCount);
            sb.AppendLine("inventory  : " + (string.IsNullOrEmpty(InventoryPath) ? "(MISSING — 跳过 activeSelf 校验)" : InventoryPath));
            sb.AppendLine("controller : " + ControllerPath);
            if (InsertIndex >= 0)
                sb.AppendLine("clip anchor: 插在 [" + InsertAfter + "] 之后 / [" + InsertBefore + "] 之前  (index " + InsertIndex + ")");
            else
                sb.AppendLine("clip anchor: (未读取控制器层名，Unity 侧再算；默认 部位层之后)");
            sb.AppendLine("writers    : sc=" + Sc.Count + "  clip=" + Clip.Count + "  skip=" + Skipped.Count + "  warn=" + Warnings.Count);
            sb.AppendLine("transitions: 计划合计 " + TotalTransitions + " 条（判据 ≤ 200；每层见下 off→on / on→off）");
            if (Warnings.Count > 0)
            {
                sb.AppendLine("---- warnings ----");
                for (int i = 0; i < Warnings.Count; i++) sb.AppendLine("  ! " + Warnings[i]);
            }
            sb.AppendLine();

            for (int i = 0; i < Sc.Count; i++)
            {
                var w = Sc[i];
                sb.AppendLine("[SC  ] " + w.DepId + "  kind=" + w.Kind + "  writer=[" + w.WriterText + "]" + (w.ReplacesLegacy ? "  replaces_legacy" : ""));
                sb.AppendLine("       when : " + w.WhenText);
                for (int j = 0; j < w.HostPaths.Count; j++)
                    sb.AppendLine("       host : " + w.HostPaths[j] + "   (" + w.HostParts[j] + ")");
                for (int j = 0; j < w.Targets.Count; j++)
                {
                    var t = w.Targets[j];
                    sb.AppendLine("       set  : " + t.Mesh + " :: " + t.Property + "  on=" + F(t.On) + " off=" + F(t.Off) + "   path=" + t.Path);
                }
                sb.AppendLine("       fp   : " + w.Fingerprint);
            }
            for (int i = 0; i < Clip.Count; i++)
            {
                var w = Clip[i];
                sb.AppendLine("[CLIP] " + w.DepId + "  kind=" + w.Kind + "  writer=[" + w.WriterText + "]");
                sb.AppendLine("       layer: " + w.LayerName);
                sb.AppendLine("       on   : " + w.OnExprText);
                sb.AppendLine("       transitions: off→on=" + w.OffToOn.Count + "  on→off=" + w.OnToOff.Count
                              + "  合计=" + w.ExpectedTransitions + (w.TransitionsTruncated ? "  !! 已截断" : ""));
                for (int j = 0; j < w.OffToOn.Count; j++)
                    sb.AppendLine("         off→on[" + j + "] : " + ClauseText(w.OffToOn[j]));
                for (int j = 0; j < w.OnToOff.Count; j++)
                    sb.AppendLine("         on→off[" + j + "] : " + ClauseText(w.OnToOff[j]));
                sb.AppendLine("       default: " + (w.DefaultOn ? "On（按菜单默认值条件为真）" : "Off"));
                if (w.Notes.Count > 0) sb.AppendLine("       note : " + string.Join("; ", w.Notes.ToArray()));
                for (int j = 0; j < w.Targets.Count; j++)
                {
                    var t = w.Targets[j];
                    sb.AppendLine("       two-state: " + t.Path + " :: " + t.Property + "  on=" + F(t.On) + " off=" + F(t.Off));
                }
                sb.AppendLine("       fp   : " + w.Fingerprint);
            }
            for (int i = 0; i < Skipped.Count; i++)
                sb.AppendLine("[SKIP] " + Skipped[i].DepId + "  kind=" + Skipped[i].Kind + "  — " + Skipped[i].Reason);
            return sb.ToString();
        }

        private static string F(float v) { return v.ToString("0.######", CultureInfo.InvariantCulture); }

        /// <summary>把一个转移子句渲染成 "a &amp; b &amp; c"（空 = true）。</summary>
        internal static string ClauseText(List<Cond> cl)
        {
            if (cl == null || cl.Count == 0) return "true";
            var parts = new List<string>(cl.Count);
            for (int i = 0; i < cl.Count; i++) parts.Add(cl[i].ToString());
            return string.Join(" & ", parts.ToArray());
        }
    }

    // ───────────────────────── inventory 索引 ─────────────────────────

    /// <summary>T-05 导出的 out/inventory.json，只取「每个渲染器怎么切换」。</summary>
    public sealed class InventoryIndex
    {
        public string Path = "";
        public Dictionary<string, string> SwitchByPath = new Dictionary<string, string>();

        public static InventoryIndex Load(string path)
        {
            if (string.IsNullOrEmpty(path) || !File.Exists(path)) return null;
            var idx = new InventoryIndex { Path = path };
            var root = AuditJson.Parse(File.ReadAllText(path)) as JsonObject;
            if (root == null) return idx;
            var avatars = AuditJson.Arr(root, "avatars");
            if (avatars == null) return idx;
            foreach (var av in avatars)
            {
                var ao = av as JsonObject;
                if (ao == null) continue;
                var rs = AuditJson.Arr(ao, "renderers");
                if (rs == null) continue;
                foreach (var rv in rs)
                {
                    var ro = rv as JsonObject;
                    if (ro == null) continue;
                    var p = AuditJson.Str(ro, "path", "");
                    var sw = AuditJson.Obj(ro, "switch");
                    var method = sw != null ? AuditJson.Str(sw, "method", "") : "";
                    if (p.Length > 0 && method.Length > 0) idx.SwitchByPath[p] = method;
                }
            }
            return idx;
        }

        public string MethodFor(string path)
        {
            if (string.IsNullOrEmpty(path)) return null;
            string m;
            if (SwitchByPath.TryGetValue(path, out m)) return m;
            foreach (var kv in SwitchByPath)
                if (kv.Key.EndsWith("/" + path, StringComparison.Ordinal) || kv.Key == path) return kv.Value;
            return null;
        }
    }

    // ───────────────────────── 两态层的转移计划 ─────────────────────────

    /// <summary>
    /// 两态层 Off/On 的转移计划（纯 C#，离线可跑）。
    ///
    /// 为什么需要它：AJ 版 On→Off 直接对 On 的 DNF 取 `Dnf.Not`，布尔展开是指数级的
    /// （胸前压制层 15 个子句 → 上百万项），一层写出几百条过渡，控制器 4 轮涨到 38 MB。
    /// 这里按「浮点参数切片 × 布尔子句」求值：
    ///   1. 把条件分成布尔部分（==0/==1）与浮点部分（&gt;/&lt;），对每个浮点参数按所有阈值切片；
    ///   2. 每个切片上 On 退化成一个只含布尔条件的 DNF；
    ///   3. Off→On = 各切片布尔 DNF 的合取子句；On→Off = 切片布尔 DNF 取反后的合取子句；
    ///      再把相邻且布尔键相同的切片并成一个区间。
    /// 条数 ≈ 切片数 × 布尔子句数，而不是子句数的乘积。
    ///
    /// 取舍：切片边界（恰好等于阈值）取不到 —— Unity 转移条件只有严格 &gt;/&lt;，并区间时会吞掉
    /// 这一个测度零点；menu 参数由轮盘给出，落在阈值上本就不稳定，且这与 SOP
    /// `60_菜单与动画层/层序与压制.md`「离开区间需要两条转移（低于下界/高于上界）」一致。
    /// </summary>
    public static class TransitionPlan
    {
        const int HardCapPerLayer = 256;

        sealed class Cell
        {
            public float Lo = float.NegativeInfinity, Hi = float.PositiveInfinity;
            public List<Cond> Pred = new List<Cond>();
        }

        sealed class Run
        {
            public List<Cond> Conj;
            public int First, Last;
        }

        public static void Build(ClipWriter w, Dnf on, DepPlanResult r)
        {
            w.OffToOn.Clear();
            w.OnToOff.Clear();
            var clauses = NormalizeClauses(on);

            w.OffToOn = Plan(clauses, false);
            w.OnToOff = Plan(clauses, true);

            int total = w.OffToOn.Count + w.OnToOff.Count;
            if (total > HardCapPerLayer)
            {
                w.TransitionsTruncated = true;
                if (w.OffToOn.Count > HardCapPerLayer / 2) w.OffToOn.RemoveRange(HardCapPerLayer / 2, w.OffToOn.Count - HardCapPerLayer / 2);
                int room = HardCapPerLayer - w.OffToOn.Count;
                if (w.OnToOff.Count > room) w.OnToOff.RemoveRange(room, w.OnToOff.Count - room);
                r.Warnings.Add(w.DepId + "：过渡计划 " + total + " 条超过 " + HardCapPerLayer
                               + " 上限已截断（when 条件过复杂，请人工检查）");
            }
        }

        // ── 主流程 ──

        static List<List<Cond>> Plan(List<List<Cond>> clauses, bool negate)
        {
            var fps = FloatParams(clauses);
            var cellsPerParam = new List<Cell>[fps.Count];
            long combos = 1;
            for (int i = 0; i < fps.Count; i++)
            {
                cellsPerParam[i] = BuildCells(fps[i], Thresholds(clauses, fps[i]));
                combos *= cellsPerParam[i].Count;
                if (combos > 4096) throw new NotSupportedException("浮点条件切片 " + combos + " 超过 4096，拒绝生成过渡（when 条件过复杂）");
            }
            var tuples = Cartesian(cellsPerParam);

            // 每个切片：On 退化成的布尔 DNF（或取反后的）
            var perTuple = new List<List<List<Cond>>>(tuples.Count);
            for (int t = 0; t < tuples.Count; t++)
            {
                var boolDnf = new Dnf();
                for (int i = 0; i < clauses.Count; i++)
                    if (Covered(clauses[i], fps, tuples[t]))
                        boolDnf.Clauses.Add(BoolPart(clauses[i]));
                boolDnf = boolDnf.Normalized();
                var src = negate ? Dnf.Not(boolDnf).Normalized() : boolDnf;
                perTuple.Add(src.Clauses);
            }

            var outList = new List<List<Cond>>();
            if (fps.Count == 0)
            {
                for (int j = 0; j < perTuple[0].Count; j++) AddClause(outList, null, perTuple[0][j]);
            }
            else if (fps.Count == 1)
            {
                // 相邻切片同布尔键 → 并成一个区间
                var active = new Dictionary<string, Run>(StringComparer.Ordinal);
                var done = new List<Run>();
                for (int t = 0; t < tuples.Count; t++)
                {
                    var keys = new HashSet<string>(StringComparer.Ordinal);
                    var conjs = perTuple[t];
                    for (int j = 0; j < conjs.Count; j++) keys.Add(Dnf.ClauseKey(conjs[j]));
                    if (active.Count > 0)
                    {
                        var drop = new List<string>();
                        foreach (var kv in active) if (!keys.Contains(kv.Key)) drop.Add(kv.Key);
                        for (int i = 0; i < drop.Count; i++) { done.Add(active[drop[i]]); active.Remove(drop[i]); }
                    }
                    for (int j = 0; j < conjs.Count; j++)
                    {
                        var key = Dnf.ClauseKey(conjs[j]);
                        Run run;
                        if (active.TryGetValue(key, out run)) run.Last = t;
                        else active[key] = new Run { Conj = conjs[j], First = t, Last = t };
                    }
                }
                done.AddRange(active.Values);
                for (int i = 0; i < done.Count; i++)
                {
                    var run = done[i];
                    var pred = IntervalPred(fps[0], tuples[run.First][0].Lo, tuples[run.Last][0].Hi);
                    AddClause(outList, pred, run.Conj);
                }
            }
            else
            {
                for (int t = 0; t < tuples.Count; t++)
                {
                    var pred = new List<Cond>();
                    for (int i = 0; i < tuples[t].Length; i++) pred.AddRange(tuples[t][i].Pred);
                    for (int j = 0; j < perTuple[t].Count; j++) AddClause(outList, pred, perTuple[t][j]);
                }
            }
            return Dedup(outList);
        }

        // ── 子句整理 ──

        static List<List<Cond>> NormalizeClauses(Dnf d)
        {
            var res = new List<List<Cond>>();
            var norm = d.Normalized();
            for (int i = 0; i < norm.Clauses.Count; i++)
            {
                var cl = norm.Clauses[i];
                var pos = new HashSet<string>(StringComparer.Ordinal);
                var neg = new HashSet<string>(StringComparer.Ordinal);
                var lo = new Dictionary<string, float>(StringComparer.Ordinal);
                var hi = new Dictionary<string, float>(StringComparer.Ordinal);
                bool bad = false;
                for (int j = 0; j < cl.Count; j++)
                {
                    var c = cl[j];
                    if (c.Mode == CondMode.If) pos.Add(c.Param);
                    else if (c.Mode == CondMode.IfNot) neg.Add(c.Param);
                    else if (c.Mode == CondMode.Greater)
                    {
                        float old;
                        if (lo.TryGetValue(c.Param, out old)) lo[c.Param] = Math.Max(old, c.Threshold);
                        else lo[c.Param] = c.Threshold;
                    }
                    else
                    {
                        float old;
                        if (hi.TryGetValue(c.Param, out old)) hi[c.Param] = Math.Min(old, c.Threshold);
                        else hi[c.Param] = c.Threshold;
                    }
                }
                foreach (var p in pos) if (neg.Contains(p)) { bad = true; break; }
                if (!bad)
                    foreach (var kv in lo)
                    {
                        float h;
                        if (hi.TryGetValue(kv.Key, out h) && kv.Value >= h) { bad = true; break; }
                    }
                if (bad) continue;
                res.Add(cl);
            }
            return res;
        }

        static List<Cond> BoolPart(List<Cond> cl)
        {
            var r = new List<Cond>();
            for (int i = 0; i < cl.Count; i++)
                if (cl[i].Mode == CondMode.If || cl[i].Mode == CondMode.IfNot) r.Add(cl[i]);
            return r;
        }

        static List<string> FloatParams(List<List<Cond>> clauses)
        {
            var props = new List<string>();
            for (int i = 0; i < clauses.Count; i++)
                for (int j = 0; j < clauses[i].Count; j++)
                {
                    var c = clauses[i][j];
                    if (c.Mode != CondMode.Greater && c.Mode != CondMode.Less) continue;
                    if (!props.Contains(c.Param)) props.Add(c.Param);
                }
            props.Sort(StringComparer.Ordinal);
            return props;
        }

        static List<float> Thresholds(List<List<Cond>> clauses, string param)
        {
            var ts = new List<float>();
            for (int i = 0; i < clauses.Count; i++)
                for (int j = 0; j < clauses[i].Count; j++)
                {
                    var c = clauses[i][j];
                    if (c.Param != param) continue;
                    if (c.Mode != CondMode.Greater && c.Mode != CondMode.Less) continue;
                    if (!ts.Contains(c.Threshold)) ts.Add(c.Threshold);
                }
            ts.Sort();
            return ts;
        }

        static List<Cell> BuildCells(string param, List<float> ts)
        {
            var res = new List<Cell>();
            if (ts.Count == 0) { res.Add(new Cell()); return res; }
            res.Add(MakeCell(param, float.NegativeInfinity, ts[0]));
            for (int i = 1; i < ts.Count; i++) res.Add(MakeCell(param, ts[i - 1], ts[i]));
            res.Add(MakeCell(param, ts[ts.Count - 1], float.PositiveInfinity));
            return res;
        }

        static Cell MakeCell(string param, float lo, float hi)
        {
            var c = new Cell { Lo = lo, Hi = hi };
            if (!float.IsNegativeInfinity(lo)) c.Pred.Add(new Cond(CondMode.Greater, lo, param));
            if (!float.IsPositiveInfinity(hi)) c.Pred.Add(new Cond(CondMode.Less, hi, param));
            return c;
        }

        static List<Cond> IntervalPred(string param, float lo, float hi)
        {
            var p = new List<Cond>();
            if (!float.IsNegativeInfinity(lo)) p.Add(new Cond(CondMode.Greater, lo, param));
            if (!float.IsPositiveInfinity(hi)) p.Add(new Cond(CondMode.Less, hi, param));
            return p;
        }

        static List<Cell[]> Cartesian(List<Cell>[] perParam)
        {
            var res = new List<Cell[]>();
            if (perParam.Length == 0) { res.Add(new Cell[0]); return res; }
            var idx = new int[perParam.Length];
            while (true)
            {
                var t = new Cell[perParam.Length];
                for (int i = 0; i < perParam.Length; i++) t[i] = perParam[i][idx[i]];
                res.Add(t);
                int k = perParam.Length - 1;
                while (k >= 0)
                {
                    idx[k]++;
                    if (idx[k] < perParam[k].Count) break;
                    idx[k] = 0; k--;
                }
                if (k < 0) break;
            }
            return res;
        }

        static bool Covered(List<Cond> clause, List<string> fps, Cell[] tuple)
        {
            for (int i = 0; i < fps.Count; i++)
            {
                float lo = float.NegativeInfinity, hi = float.PositiveInfinity;
                for (int j = 0; j < clause.Count; j++)
                {
                    var c = clause[j];
                    if (c.Param != fps[i]) continue;
                    if (c.Mode == CondMode.Greater) lo = Math.Max(lo, c.Threshold);
                    else if (c.Mode == CondMode.Less) hi = Math.Min(hi, c.Threshold);
                }
                if (!(tuple[i].Lo >= lo && tuple[i].Hi <= hi)) return false;
            }
            return true;
        }

        static void AddClause(List<List<Cond>> outList, List<Cond> pred, List<Cond> conj)
        {
            var cl = new List<Cond>();
            if (pred != null) cl.AddRange(pred);
            if (conj != null) cl.AddRange(conj);
            var d = new Dnf();
            d.Clauses.Add(cl);
            var n = d.Normalized();
            if (n.Clauses.Count == 0) return;
            var c = n.Clauses[0];
            if (c.Count == 0) return; // 永真：不建转移（由默认状态承担）
            outList.Add(c);
        }

        static List<List<Cond>> Dedup(List<List<Cond>> clauses)
        {
            var res = new List<List<Cond>>();
            var seen = new HashSet<string>(StringComparer.Ordinal);
            for (int i = 0; i < clauses.Count; i++)
                if (seen.Add(Dnf.ClauseKey(clauses[i]))) res.Add(clauses[i]);
            return res;
        }
    }

    // ───────────────────────── 计划编译 ─────────────────────────

    public static class DepPlan
    {
        public const string LayerPrefix = "Decl: ";

        // 层名 / 资产名只允许字母数字、下划线、连字符 —— Unity 的 AddLayer/AddState
        // 不接受 `.`（2026-09-19 事故：`Decl: kaguya.sailor_under_outer` 被 Unity 改写成
        // `Decl: kaguya_sailor_under_outer`，而 gen_writers.json 记的是原名，对账找不到旧层，
        // 每轮 Apply 都新增一整套）。这里统一在计划层就规范化，并对账只认规范化后的名字。
        public static string SafeLayerName(string depId)
        {
            return LayerPrefix + SafeBody(depId);
        }

        public static string SafeBody(string s)
        {
            var sb = new StringBuilder();
            var t = s ?? "";
            for (int i = 0; i < t.Length; i++)
            {
                var c = t[i];
                sb.Append((char.IsLetterOrDigit(c) || c == '_' || c == '-') ? c : '_');
            }
            return sb.ToString();
        }

        /// <summary>层/资产名去重：同名时补 dep_id 的 6 位短哈希（同一次计划内确定）。</summary>
        public static string UniqueName(string baseName, HashSet<string> seen, string depId)
        {
            if (seen.Add(baseName)) return baseName;
            var suffix = "_" + Sha256(depId).Substring(0, 6);
            var cand = baseName + suffix;
            int k = 1;
            while (!seen.Add(cand)) { cand = baseName + suffix + "_" + k.ToString(CultureInfo.InvariantCulture); k++; }
            return cand;
        }

        public static string Sha256(string text)
        {
            using (var sha = SHA256.Create())
            {
                var b = sha.ComputeHash(Encoding.UTF8.GetBytes(text ?? ""));
                var sb = new StringBuilder(b.Length * 2);
                for (int i = 0; i < b.Length; i++) sb.Append(b[i].ToString("x2", CultureInfo.InvariantCulture));
                return sb.ToString();
            }
        }

        public static DepPlanResult Build(DeclDoc doc, string declPath, string declSha, InventoryIndex inv,
                                          string[] existingLayerNames, string controllerPath)
        {
            var r = new DepPlanResult
            {
                DeclPath = declPath,
                DeclSha = declSha,
                InventoryPath = inv != null ? inv.Path : "",
                ControllerPath = controllerPath,
                Project = doc.Avatar.Project,
                AvatarRoot = doc.Avatar.Root,
                Scene = doc.Avatar.Scene,
                PartCount = doc.Parts.Count,
                DepCount = doc.Deps.Count
            };

            ComputeAnchor(r, existingLayerNames);
            if (inv == null)
                r.Warnings.Add("out/inventory.json 不存在：sc 后端的 activeSelf 校验被跳过（按 activeSelf 处理）");

            for (int i = 0; i < doc.Deps.Count; i++)
            {
                var dep = doc.Deps[i];
                try
                {
                    CompileDep(doc, dep, inv, r);
                }
                catch (Exception e)
                {
                    r.Skipped.Add(new SkipEntry { DepId = dep.Id, Kind = dep.Kind, Reason = "编译异常：" + e.Message });
                    r.Warnings.Add(dep.Id + " 编译异常：" + e.Message);
                }
            }

            // clip 层按 Dep 顺序插在锚点之后，层序稳定（先编译的在先）
            if (r.InsertIndex >= 0)
                for (int i = 0; i < r.Clip.Count; i++) r.Clip[i].LayerIndexHint = r.InsertIndex + i;

            // 层名/文件名唯一化（规范化后再去重，保证两次编译字节一致）
            var seenLayers = new HashSet<string>(StringComparer.Ordinal);
            for (int i = 0; i < r.Clip.Count; i++)
            {
                var w = r.Clip[i];
                w.LayerName = UniqueName(SafeLayerName(w.DepId), seenLayers, w.DepId);
                w.FileStem = "Decl_" + w.LayerName.Substring(LayerPrefix.Length);
            }
            return r;
        }

        private static void ComputeAnchor(DepPlanResult r, string[] names)
        {
            if (names == null || names.Length == 0) return;
            int lastPart = -1;
            for (int i = 0; i < names.Length; i++)
            {
                var n = names[i] ?? "";
                if (n.StartsWith("部位_", StringComparison.Ordinal) || n.StartsWith("配件_", StringComparison.Ordinal)
                    || n.StartsWith("头件_", StringComparison.Ordinal)) lastPart = i;
            }
            r.InsertIndex = lastPart + 1;
            if (lastPart >= 0) r.InsertAfter = names[lastPart];
            if (r.InsertIndex < names.Length) r.InsertBefore = names[r.InsertIndex];
        }

        private static void CompileDep(DeclDoc doc, DeclDep dep, InventoryIndex inv, DepPlanResult r)
        {
            if (!dep.HasWriter("gen") && !dep.HasWriter("ours_legacy"))
            {
                r.Skipped.Add(new SkipEntry { DepId = dep.Id, Kind = dep.Kind, Reason = "writer=" + dep.WriterText + "（非我方）" });
                return;
            }
            if (!InScope(dep.Kind))
            {
                r.Skipped.Add(new SkipEntry { DepId = dep.Id, Kind = dep.Kind, Reason = "kind=" + dep.Kind + " 不在 T-06 范围（D1/D2/D3/D4a/D4b/D6/D7）" });
                return;
            }

            bool activeSelf;
            float on, off;
            if (!ResolveAction(dep, out activeSelf, out on, out off, r))
            {
                r.Skipped.Add(new SkipEntry { DepId = dep.Id, Kind = dep.Kind, Reason = "无具体动作（geo/variant/sync/not_written 等，仅作校验期望）" });
                return;
            }

            PExpr ast;
            if (!ResolveOnAst(doc, dep, on, off, r, out ast))
            {
                r.Skipped.Add(new SkipEntry { DepId = dep.Id, Kind = dep.Kind, Reason = "on 条件不可解析" });
                return;
            }

            Dnf onDnf;
            try
            {
                onDnf = ToDnf(doc, ast).Normalized();
            }
            catch (Exception e)
            {
                r.Skipped.Add(new SkipEntry { DepId = dep.Id, Kind = dep.Kind, Reason = "条件含一期不支持的谓词：" + e.Message });
                r.Warnings.Add(dep.Id + " 条件未编译：" + e.Message);
                return;
            }

            bool pureVisOr = IsPureVisOr(ast) && onDnf.Clauses.Count > 0;
            bool scKind = dep.Kind == "D1" || dep.Kind == "D3";
            bool sc = scKind && !activeSelf && pureVisOr && SwitchAllActiveSelf(doc, ast, inv, r, dep.Id);

            var targets = BuildTargets(doc, dep, activeSelf, on, off, inv, r);
            if (targets.Count == 0)
            {
                r.Skipped.Add(new SkipEntry { DepId = dep.Id, Kind = dep.Kind, Reason = "目标解析为空（part/mesh 对不上）" });
                return;
            }

            if (sc)
            {
                var w = new ScWriter
                {
                    DepId = dep.Id,
                    Kind = dep.Kind,
                    WriterText = dep.WriterText,
                    WhenText = onDnf.Text,
                    ReplacesLegacy = dep.HasWriter("ours_legacy"),
                    Targets = targets
                };
                var hosts = new List<string>();
                CollectVisParts(doc, ast, hosts);
                for (int i = 0; i < hosts.Count; i++)
                {
                    var part = doc.Part(hosts[i]);
                    if (part == null) continue;
                    for (int j = 0; j < part.Objects.Count; j++)
                    {
                        w.HostParts.Add(part.Id);
                        w.HostPaths.Add(part.Objects[j].Path);
                    }
                }
                if (w.HostPaths.Count == 0) { r.Skipped.Add(new SkipEntry { DepId = dep.Id, Kind = dep.Kind, Reason = "sc 无宿主物体" }); return; }
                w.Fingerprint = FingerprintSc(w);
                r.Sc.Add(w);
            }
            else
            {
                var w = new ClipWriter
                {
                    DepId = dep.Id,
                    Kind = dep.Kind,
                    WriterText = dep.WriterText,
                    LayerName = SafeLayerName(dep.Id),
                    Targets = targets,
                    OnExpr = onDnf,
                    OnExprText = onDnf.Text
                };
                w.DefaultOn = onDnf.Evaluate(MenuDefaults(doc));
                if (activeSelf && inv != null) w.Notes.Add("显隐件按 inventory 的 switch.method 写属性");
                if (dep.HasWriter("ours_legacy")) w.Notes.Add("声明含 ours_legacy（T-07 后改 gen）");
                if (!pureVisOr && scKind) w.Notes.Add("条件不是纯 vis 或，落 clip 后端");
                TransitionPlan.Build(w, onDnf, r);
                w.Fingerprint = FingerprintClip(w);
                r.Clip.Add(w);
            }
        }

        private static bool InScope(string kind)
        {
            return kind == "D1" || kind == "D2" || kind == "D3" || kind == "D4a" || kind == "D4b" || kind == "D6" || kind == "D7";
        }

        /// <summary>菜单参数的默认值（决定 clip 层的默认状态，避免入场闪一帧）。</summary>
        public static Dictionary<string, float> MenuDefaults(DeclDoc doc)
        {
            var d = new Dictionary<string, float>();
            foreach (var kv in doc.Menu.Controls) if (!d.ContainsKey(kv.Value.Param)) d[kv.Value.Param] = kv.Value.Default;
            foreach (var kv in doc.Menu.Slots) if (!d.ContainsKey(kv.Value.Param)) d[kv.Value.Param] = kv.Value.Default;
            if (!string.IsNullOrEmpty(doc.Menu.Outfit.Param)) d[doc.Menu.Outfit.Param] = doc.Menu.Outfit.Default;
            return d;
        }

        // ── 动作（on/off 值）──

        private static bool ResolveAction(DeclDep dep, out bool activeSelf, out float on, out float off, DepPlanResult r)
        {
            activeSelf = false; on = 0; off = 0;
            bool gotOn = ExtractValue(dep.Expect, out on, out activeSelf);
            bool offDefined = ExtractElse(dep.ElseRaw, activeSelf, out off);

            // cases 里的具体值：与 off 不同者才算 on
            float caseOn = 0; bool hasCaseOn = false; bool multiple = false;
            for (int i = 0; i < dep.Cases.Count; i++)
            {
                var c = dep.Cases[i];
                if (c.ExpectIsString) continue;
                bool cas; float cv;
                if (!ExtractValue(c.Expect, out cv, out cas)) continue;
                if (!activeSelf && cas) activeSelf = true;
                if (offDefined && Math.Abs(cv - off) < 0.0001f) continue;
                if (hasCaseOn && Math.Abs(cv - caseOn) > 0.0001f) multiple = true;
                caseOn = cv; hasCaseOn = true;
            }
            if (multiple)
            {
                r.Warnings.Add(dep.Id + " cases 里有多个不同取值，一期只支持两态，跳过");
                return false;
            }
            if (hasCaseOn) on = caseOn;
            else if (!gotOn)
            {
                if (!activeSelf) return false;
                // expect 只给了 hidden/shown 的顶层未给：由 ExtractValue 已处理；
                // 这里兜底：activeSelf 但没有具体值 → 视为 hidden=0
                on = 0;
            }
            if (!offDefined) off = activeSelf ? 1f : 0f;
            return true;
        }

        private static bool ExtractValue(JsonObject exp, out float v, out bool activeSelf)
        {
            v = 0; activeSelf = false;
            if (exp == null) return false;
            if (exp.Has("hidden")) { v = AuditJson.Bool(exp, "hidden", false) ? 0f : 1f; activeSelf = true; return true; }
            if (exp.Has("shown")) { v = AuditJson.Bool(exp, "shown", false) ? 1f : 0f; activeSelf = true; return true; }
            if (exp.Has("value")) { v = (float)AuditJson.Num(exp, "value", 0); return true; }
            return false;
        }

        private static bool ExtractElse(object els, bool activeSelf, out float v)
        {
            v = activeSelf ? 1f : 0f;
            var eo = els as JsonObject;
            if (eo != null)
            {
                bool a;
                float x;
                if (ExtractValue(eo, out x, out a)) { v = x; return true; }
                return false;
            }
            var s = els as string;
            if (s == "baseline" || s == "dont_care") return true;
            return false;
        }

        // ── on 条件表达式 ──

        private static bool ResolveOnAst(DeclDoc doc, DeclDep dep, float on, float off, DepPlanResult r, out PExpr ast)
        {
            ast = null;
            if (dep.Cases.Count > 0)
            {
                PExpr acc = null;
                for (int i = 0; i < dep.Cases.Count; i++)
                {
                    var c = dep.Cases[i];
                    if (c.ExpectIsString) continue;
                    bool cas; float cv;
                    if (!ExtractValue(c.Expect, out cv, out cas)) continue;
                    if (Math.Abs(cv - off) < 0.0001f) continue; // 与 off 同值 = 非激活态
                    var e = ExprParser.Parse(c.When, doc);
                    acc = acc == null ? e : OrNode(acc, e);
                }
                if (acc != null) { ast = acc; return true; }
                if (!string.IsNullOrEmpty(dep.When))
                {
                    ast = ExprParser.Parse(dep.When, doc);
                    return true;
                }
                return false;
            }
            if (string.IsNullOrEmpty(dep.When)) return false;
            ast = ExprParser.Parse(dep.When, doc);
            return true;
        }

        private static PExpr OrNode(PExpr a, PExpr b) { var o = new POr(); o.Items.Add(a); o.Items.Add(b); return o; }

        private static bool IsPureVisOr(PExpr e)
        {
            if (e is PVis) return true;
            if (e is POr)
            {
                var o = (POr)e;
                for (int i = 0; i < o.Items.Count; i++) if (!IsPureVisOr(o.Items[i])) return false;
                return true;
            }
            return false;
        }

        private static void CollectVisParts(DeclDoc doc, PExpr e, List<string> into)
        {
            var v = e as PVis;
            if (v != null)
            {
                if (v.Name.StartsWith("any.", StringComparison.Ordinal))
                {
                    var key = v.Name.Substring(4);
                    for (int i = 0; i < doc.Parts.Count; i++)
                        if ((doc.Parts[i].Slot == key || doc.Parts[i].Kind == key) && !into.Contains(doc.Parts[i].Id))
                            into.Add(doc.Parts[i].Id);
                }
                else if (!into.Contains(v.Name)) into.Add(v.Name);
                return;
            }
            var o = e as POr;
            if (o != null) { for (int i = 0; i < o.Items.Count; i++) CollectVisParts(doc, o.Items[i], into); return; }
            var a = e as PAnd;
            if (a != null) { for (int i = 0; i < a.Items.Count; i++) CollectVisParts(doc, a.Items[i], into); }
        }

        private static bool SwitchAllActiveSelf(DeclDoc doc, PExpr ast, InventoryIndex inv, DepPlanResult r, string depId)
        {
            if (inv == null) return true;
            var parts = new List<string>();
            CollectVisParts(doc, ast, parts);
            bool ok = true;
            for (int i = 0; i < parts.Count; i++)
            {
                var p = doc.Part(parts[i]);
                if (p == null) { ok = false; continue; }
                for (int j = 0; j < p.Objects.Count; j++)
                {
                    var m = inv.MethodFor(p.Objects[j].Path);
                    if (m == "m_Enabled")
                    {
                        r.Warnings.Add(depId + "：" + p.Objects[j].Path + " 按 inventory 是 m_Enabled 切换 → 落 clip 后端");
                        ok = false;
                    }
                }
            }
            return ok;
        }

        // ── AST → DNF ──

        public static Dnf ToDnf(DeclDoc doc, PExpr e)
        {
            if (e is PTrue) return Dnf.True();
            if (e is PFalse) return Dnf.False();
            if (e is PNot) return Dnf.Not(ToDnf(doc, ((PNot)e).Inner));
            if (e is PAnd)
            {
                var a = (PAnd)e; var acc = Dnf.True();
                for (int i = 0; i < a.Items.Count; i++) acc = Dnf.And(acc, ToDnf(doc, a.Items[i]));
                return acc;
            }
            if (e is POr)
            {
                var o = (POr)e; var acc = Dnf.False();
                for (int i = 0; i < o.Items.Count; i++) acc = Dnf.Or(acc, ToDnf(doc, o.Items[i]));
                return acc;
            }
            if (e is PVis) return VisDnf(doc, ((PVis)e).Name);
            if (e is PParam) return ParamDnf(doc, (PParam)e);
            if (e is PRange)
            {
                var pr = (PRange)e; var acc = Dnf.False();
                for (int i = 0; i < pr.Ranges.Count; i++) acc = Dnf.Or(acc, RangeDnf(pr.Param, pr.Ranges[i][0], pr.Ranges[i][1]));
                return acc;
            }
            var un = e as PUnsupported;
            throw new NotSupportedException(un != null ? un.Reason : "未知表达式节点");
        }

        private static Dnf BoolDnf(string param, bool value)
        {
            return Dnf.Single(new Cond(value ? CondMode.If : CondMode.IfNot, 0f, param));
        }

        private static Dnf RangeDnf(string param, float lo, float hi)
        {
            var d = Dnf.True();
            if (!float.IsNegativeInfinity(lo)) d = Dnf.And(d, Dnf.Single(new Cond(CondMode.Greater, lo, param)));
            d = Dnf.And(d, Dnf.Single(new Cond(CondMode.Less, hi, param)));
            return d;
        }

        private static Dnf ParamDnf(DeclDoc doc, PParam p)
        {
            if (p.Kind == "slot")
            {
                var s = doc.Slot(p.Name);
                if (s == null) throw new NotSupportedException("slot 未定义：" + p.Name);
                bool v = p.Value == "1" || p.Value == "true";
                return BoolDnf(s.Param, v);
            }
            var c = doc.Control(p.Name);
            if (c == null) throw new NotSupportedException("control 未定义：" + p.Name);
            if (c.Type == "bool" || p.Value == "1" || p.Value == "true" || p.Value == "0" || p.Value == "false")
            {
                bool v = p.Value == "1" || p.Value == "true";
                return BoolDnf(c.Param, v);
            }
            int idx = c.Labels.IndexOf(p.Value);
            if (idx < 0) throw new NotSupportedException("control " + p.Name + " 档位未知：" + p.Value);
            return RangeDnf(c.Param, ExprParser.SlotRange(idx, c.Labels.Count)[0], ExprParser.SlotRange(idx, c.Labels.Count)[1]);
        }

        private static Dnf VisDnf(DeclDoc doc, string name)
        {
            if (name.StartsWith("any.", StringComparison.Ordinal))
            {
                var key = name.Substring(4);
                var acc = Dnf.False();
                for (int i = 0; i < doc.Parts.Count; i++)
                    if (doc.Parts[i].Slot == key || doc.Parts[i].Kind == key) acc = Dnf.Or(acc, VisSingle(doc, doc.Parts[i]));
                if (acc.Clauses.Count == 0) throw new NotSupportedException("any." + key + " 没有对应部件（slot 或 kind）");
                return acc;
            }
            var part = doc.Part(name);
            if (part == null) throw new NotSupportedException("部件未定义：" + name);
            return VisSingle(doc, part);
        }

        private static Dnf VisSingle(DeclDoc doc, DeclPart part)
        {
            var d = Dnf.True();
            if (part.Outfit.Count > 0)
            {
                var acc = Dnf.False();
                int n = doc.Menu.Outfit.Labels.Count;
                if (n == 0) throw new NotSupportedException("menu.outfit 无 labels");
                for (int i = 0; i < part.Outfit.Count; i++)
                {
                    int idx = doc.Menu.Outfit.Labels.IndexOf(part.Outfit[i]);
                    if (idx < 0) throw new NotSupportedException("部件 " + part.Id + " 的 outfit 档未知：" + part.Outfit[i]);
                    var r = ExprParser.SlotRange(idx, n);
                    acc = Dnf.Or(acc, RangeDnf(doc.Menu.Outfit.Param, r[0], r[1]));
                }
                d = Dnf.And(d, acc);
            }
            if (!string.IsNullOrEmpty(part.Slot))
            {
                var s = doc.Slot(part.Slot);
                if (s == null) throw new NotSupportedException("部件 " + part.Id + " 的 slot 未知：" + part.Slot);
                d = Dnf.And(d, BoolDnf(s.Param, true));
            }
            if (part.Toggle != null && !string.IsNullOrEmpty(part.Toggle.Control))
            {
                var c = doc.Control(part.Toggle.Control);
                if (c == null) throw new NotSupportedException("部件 " + part.Id + " 的 control 未知：" + part.Toggle.Control);
                var acc = Dnf.False();
                if (part.Toggle.ShownAt.Count == 0) acc = Dnf.Or(acc, BoolDnf(c.Param, true));
                for (int i = 0; i < part.Toggle.ShownAt.Count; i++)
                {
                    var lbl = part.Toggle.ShownAt[i];
                    if (c.Type == "bool" || lbl == "1" || lbl == "true")
                        acc = Dnf.Or(acc, BoolDnf(c.Param, true));
                    else if (lbl == "0" || lbl == "false")
                        acc = Dnf.Or(acc, BoolDnf(c.Param, false));
                    else
                    {
                        int idx = c.Labels.IndexOf(lbl);
                        if (idx < 0) throw new NotSupportedException("部件 " + part.Id + " 的 control 档未知：" + lbl);
                        var rr = ExprParser.SlotRange(idx, c.Labels.Count);
                        acc = Dnf.Or(acc, RangeDnf(c.Param, rr[0], rr[1]));
                    }
                }
                d = Dnf.And(d, acc);
            }
            return d;
        }

        // ── 目标 ──

        private static List<WriterTarget> BuildTargets(DeclDoc doc, DeclDep dep, bool activeSelf, float on, float off,
                                                       InventoryIndex inv, DepPlanResult r)
        {
            var res = new List<WriterTarget>();
            var tgs = dep.AllTargets;
            for (int ti = 0; ti < tgs.Count; ti++)
            {
                var t = tgs[ti];
                if (activeSelf)
                {
                    var part = doc.Part(t.Part);
                    if (part == null)
                    {
                        r.Warnings.Add(dep.Id + "：显隐目标部件未定义 " + t.Part);
                        continue;
                    }
                    for (int j = 0; j < part.Objects.Count; j++)
                    {
                        var path = part.Objects[j].Path;
                        var method = inv != null ? inv.MethodFor(path) : null;
                        var prop = method == "m_Enabled" ? "m_Enabled" : "m_IsActive";
                        res.Add(new WriterTarget { Path = path, Property = prop, Mesh = part.Id, On = on, Off = off, ActiveSelf = true });
                    }
                    continue;
                }
                var keys = t.AllKeys;
                if (keys.Count == 0) continue;
                string path2 = null; string meshLabel = null;
                if (!string.IsNullOrEmpty(t.Part))
                {
                    var part = doc.Part(t.Part);
                    if (part == null) { r.Warnings.Add(dep.Id + "：目标部件未定义 " + t.Part); continue; }
                    path2 = part.FirstObjectPath; meshLabel = t.Part;
                }
                else if (!string.IsNullOrEmpty(t.Mesh))
                {
                    path2 = t.Mesh; meshLabel = t.Mesh;
                }
                if (string.IsNullOrEmpty(path2)) { r.Warnings.Add(dep.Id + "：target 既无 part 也无 mesh"); continue; }
                for (int k = 0; k < keys.Count; k++)
                    res.Add(new WriterTarget { Path = path2, Property = "blendShape." + keys[k], Mesh = meshLabel, On = on, Off = off, ActiveSelf = false });
            }
            // 目标排序保证字节一致
            res.Sort(delegate (WriterTarget a, WriterTarget b) { return string.CompareOrdinal(a.Canon, b.Canon); });
            return res;
        }

        // ── 指纹 ──

        public static string FingerprintSc(ScWriter w)
        {
            var sb = new StringBuilder();
            sb.Append("sc\n").Append(w.DepId).Append('\n');
            var hosts = new List<string>(w.HostPaths); hosts.Sort(StringComparer.Ordinal);
            for (int i = 0; i < hosts.Count; i++) sb.Append("H ").Append(hosts[i]).Append('\n');
            for (int i = 0; i < w.Targets.Count; i++) sb.Append("T ").Append(w.Targets[i].Canon).Append('\n');
            return Sha256(sb.ToString());
        }

        public static string FingerprintClip(ClipWriter w)
        {
            var sb = new StringBuilder();
            sb.Append("clip\n").Append(w.DepId).Append('\n').Append(w.LayerName).Append('\n');
            sb.Append("D ").Append(w.DefaultOn ? "1" : "0").Append('\n');
            sb.Append("E ").Append(w.OnExpr.Normalized().Text).Append('\n');
            for (int i = 0; i < w.Targets.Count; i++) sb.Append("T ").Append(w.Targets[i].Canon).Append('\n');
            return Sha256(sb.ToString());
        }
    }
}
