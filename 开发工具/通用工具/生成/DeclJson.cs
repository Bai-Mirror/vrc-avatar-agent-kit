// ══════════════════════════════════════════════════════════════════
// 【项目沉淀】decl.json 的只读数据模型（T-06 依赖编译器输入）
//
// 适用素体：无关（从 <工程>/_感知/decl.json 读，schema=perception/0.2）。
// 用途：把 decl_validate.py 产出的声明 JSON 读成类型化对象，供 DepPlan 用。
// 依赖：AuditIO.cs 的 AuditJson.Parse（T-09 后在 AvatarAudit.Editor 程序集里）。
//   ⚠ 本文件与 DepPlan.cs 不 using UnityEditor / UnityEngine，
//     所以能用 Mono csc 单独编出来跑计划（见 _长程任务_20260918/派工/tmp/aj/）。
// 取舍：不引第三方 JSON 库；字段缺失一律降级为默认值并在 DepPlan 里报 warning，
//   不抛异常 —— 声明是别的工具产出的，编译器宁可少做一条也不能整批跑不动。
// ══════════════════════════════════════════════════════════════════
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using AvatarAudit;

namespace AvatarGen
{
    public sealed class DeclDoc
    {
        public string Schema = "";
        public string SourcePath = "";
        public DeclAvatar Avatar = new DeclAvatar();
        public DeclMenu Menu = new DeclMenu();
        public List<DeclPart> Parts = new List<DeclPart>();
        public List<DeclDep> Deps = new List<DeclDep>();

        public DeclPart Part(string id)
        {
            if (string.IsNullOrEmpty(id)) return null;
            for (int i = 0; i < Parts.Count; i++) if (Parts[i].Id == id) return Parts[i];
            return null;
        }

        public DeclControl Control(string key)
        {
            DeclControl c;
            return (key != null && Menu.Controls.TryGetValue(key, out c)) ? c : null;
        }

        public DeclSlot Slot(string key)
        {
            DeclSlot s;
            return (key != null && Menu.Slots.TryGetValue(key, out s)) ? s : null;
        }

        public static DeclDoc LoadFile(string path)
        {
            var d = Parse(File.ReadAllText(path));
            d.SourcePath = path;
            return d;
        }

        public static DeclDoc Parse(string text)
        {
            var root = AuditJson.Parse(text) as JsonObject;
            if (root == null) throw new InvalidDataException("decl.json 顶层不是 JSON 对象");
            var d = new DeclDoc();
            d.Schema = AuditJson.Str(root, "schema", "");

            var av = AuditJson.Obj(root, "avatar");
            if (av != null)
            {
                d.Avatar.Body = AuditJson.Str(av, "body", "");
                d.Avatar.Profile = AuditJson.Str(av, "profile", "");
                d.Avatar.Project = AuditJson.Str(av, "project", "");
                d.Avatar.Root = AuditJson.Str(av, "root", "");
                d.Avatar.Scene = AuditJson.Str(av, "scene", "");
            }

            var menu = AuditJson.Obj(root, "menu");
            if (menu != null)
            {
                var ctrls = AuditJson.Obj(menu, "controls");
                if (ctrls != null)
                    foreach (var kv in ctrls.Items)
                    {
                        var c = new DeclControl { Key = kv.Key };
                        var o = kv.Value as JsonObject;
                        if (o != null) ParseControl(o, c);
                        d.Menu.Controls[kv.Key] = c;
                    }
                var slots = AuditJson.Obj(menu, "slots");
                if (slots != null)
                    foreach (var kv in slots.Items)
                    {
                        var s = new DeclSlot { Key = kv.Key };
                        var o = kv.Value as JsonObject;
                        if (o != null)
                        {
                            s.Param = AuditJson.Str(o, "param", "");
                            s.Label = AuditJson.Str(o, "label", "");
                            s.Default = (float)AuditJson.Num(o, "default", 0);
                        }
                        d.Menu.Slots[kv.Key] = s;
                    }
                var outfit = AuditJson.Obj(menu, "outfit");
                if (outfit != null)
                {
                    d.Menu.Outfit.Param = AuditJson.Str(outfit, "param", "");
                    d.Menu.Outfit.Label = AuditJson.Str(outfit, "label", "");
                    d.Menu.Outfit.Default = (float)AuditJson.Num(outfit, "default", 0);
                    ReadStringList(outfit.Get("labels"), d.Menu.Outfit.Labels);
                }
            }

            var parts = AuditJson.Arr(root, "parts");
            if (parts != null)
                foreach (var pv in parts)
                {
                    var po = pv as JsonObject;
                    if (po == null) continue;
                    d.Parts.Add(ParsePart(po));
                }

            var deps = AuditJson.Arr(root, "deps");
            if (deps != null)
                foreach (var dv in deps)
                {
                    var dobj = dv as JsonObject;
                    if (dobj == null) continue;
                    d.Deps.Add(ParseDep(dobj));
                }
            return d;
        }

        private static void ParseControl(JsonObject o, DeclControl c)
        {
            c.Param = AuditJson.Str(o, "param", "");
            c.Type = AuditJson.Str(o, "type", "bool");
            c.Label = AuditJson.Str(o, "label", "");
            c.Default = (float)AuditJson.Num(o, "default", 0);
            ReadStringList(o.Get("labels"), c.Labels);
        }

        private static DeclPart ParsePart(JsonObject o)
        {
            var p = new DeclPart();
            p.Id = AuditJson.Str(o, "id", "");
            p.Kind = AuditJson.Str(o, "kind", "");
            p.Fit = AuditJson.Str(o, "fit", "none");
            p.Slot = AuditJson.Str(o, "slot", null);
            p.Origin = AuditJson.Str(o, "origin", "");
            var objs = AuditJson.Arr(o, "objects");
            if (objs != null)
                foreach (var ov in objs)
                {
                    var oo = ov as JsonObject;
                    if (oo == null) continue;
                    p.Objects.Add(new DeclObject
                    {
                        Path = AuditJson.Str(oo, "path", ""),
                        Renderer = AuditJson.Str(oo, "renderer", "smr")
                    });
                }
            ReadStringList(o.Get("outfit"), p.Outfit);
            ReadStringList(o.Get("covers"), p.Covers);
            var tg = AuditJson.Obj(o, "toggle");
            if (tg != null)
            {
                p.Toggle = new DeclToggle { Control = AuditJson.Str(tg, "control", "") };
                ReadStringList(tg.Get("shown_at"), p.Toggle.ShownAt);
            }
            return p;
        }

        private static DeclDep ParseDep(JsonObject o)
        {
            var d = new DeclDep();
            d.Id = AuditJson.Str(o, "id", "");
            d.Kind = AuditJson.Str(o, "kind", "");
            d.When = AuditJson.Str(o, "when", "");
            d.Note = AuditJson.Str(o, "note", null);
            d.Human = AuditJson.Str(o, "human", null);
            d.Expect = AuditJson.Obj(o, "expect");
            d.ElseRaw = o.Get("else");
            ReadStringList(o.Get("writer"), d.Writer);
            ReadStringList(o.Get("supersedes"), d.Supersedes);
            ReadStringList(o.Get("roundtrip"), d.Roundtrip);

            var t = AuditJson.Obj(o, "target");
            if (t != null) d.Target = ParseTarget(t);
            var ts = AuditJson.Arr(o, "targets");
            if (ts != null)
                foreach (var tv in ts)
                {
                    var to = tv as JsonObject;
                    if (to != null) d.Targets.Add(ParseTarget(to));
                }
            var cases = AuditJson.Arr(o, "cases");
            if (cases != null)
                foreach (var cv in cases)
                {
                    var co = cv as JsonObject;
                    if (co == null) continue;
                    d.Cases.Add(new DeclCase
                    {
                        When = AuditJson.Str(co, "when", ""),
                        Expect = AuditJson.Obj(co, "expect"),
                        Note = AuditJson.Str(co, "note", null),
                        ExpectIsString = !(co.Get("expect") is JsonObject)
                    });
                }
            return d;
        }

        private static DeclTarget ParseTarget(JsonObject o)
        {
            var t = new DeclTarget();
            t.Mesh = AuditJson.Str(o, "mesh", null);
            t.Key = AuditJson.Str(o, "key", null);
            t.Part = AuditJson.Str(o, "part", null);
            t.Submesh = (int)AuditJson.Num(o, "submesh", 0);
            ReadStringList(o.Get("keys"), t.Keys);
            return t;
        }

        private static void ReadStringList(object v, List<string> into)
        {
            if (v == null) return;
            var s = v as string;
            if (s != null) { into.Add(s); return; }
            var arr = v as List<object>;
            if (arr == null) return;
            foreach (var x in arr)
            {
                if (x == null) continue;
                into.Add(Convert.ToString(x, CultureInfo.InvariantCulture));
            }
        }
    }

    public sealed class DeclAvatar
    {
        public string Body = "", Profile = "", Project = "", Root = "", Scene = "";
    }

    public sealed class DeclMenu
    {
        public Dictionary<string, DeclControl> Controls = new Dictionary<string, DeclControl>();
        public Dictionary<string, DeclSlot> Slots = new Dictionary<string, DeclSlot>();
        public DeclOutfit Outfit = new DeclOutfit();
    }

    public sealed class DeclControl
    {
        public string Key = "", Param = "", Type = "bool", Label = "";
        public float Default;
        public List<string> Labels = new List<string>();
    }

    public sealed class DeclSlot
    {
        public string Key = "", Param = "", Label = "";
        public float Default;
    }

    public sealed class DeclOutfit
    {
        public string Param = "", Label = "";
        public float Default;
        public List<string> Labels = new List<string>();
    }

    public sealed class DeclObject
    {
        public string Path = "", Renderer = "smr";
    }

    public sealed class DeclToggle
    {
        public string Control = "";
        public List<string> ShownAt = new List<string>();
    }

    public sealed class DeclPart
    {
        public string Id = "", Kind = "", Fit = "none", Slot, Origin = "";
        public List<DeclObject> Objects = new List<DeclObject>();
        public List<string> Outfit = new List<string>();
        public List<string> Covers = new List<string>();
        public DeclToggle Toggle;

        public string FirstObjectPath
        {
            get { return Objects.Count > 0 ? Objects[0].Path : null; }
        }
    }

    public sealed class DeclTarget
    {
        public string Mesh, Key, Part;
        public int Submesh;
        public List<string> Keys = new List<string>();

        public List<string> AllKeys
        {
            get
            {
                var r = new List<string>();
                if (!string.IsNullOrEmpty(Key)) r.Add(Key);
                r.AddRange(Keys);
                return r;
            }
        }
    }

    public sealed class DeclCase
    {
        public string When = "";
        public JsonObject Expect;
        public bool ExpectIsString;
        public string Note;
    }

    public sealed class DeclDep
    {
        public string Id = "", Kind = "", When = "", Note, Human;
        public JsonObject Expect;
        public object ElseRaw;
        public DeclTarget Target;
        public List<DeclTarget> Targets = new List<DeclTarget>();
        public List<DeclCase> Cases = new List<DeclCase>();
        public List<string> Writer = new List<string>();
        public List<string> Supersedes = new List<string>();
        public List<string> Roundtrip = new List<string>();

        public bool HasWriter(string name)
        {
            for (int i = 0; i < Writer.Count; i++)
                if (string.Equals(Writer[i], name, StringComparison.OrdinalIgnoreCase)) return true;
            return false;
        }

        public string WriterText
        {
            get { return Writer.Count == 0 ? "(none)" : string.Join(",", Writer.ToArray()); }
        }

        public List<DeclTarget> AllTargets
        {
            get
            {
                var r = new List<DeclTarget>();
                if (Target != null) r.Add(Target);
                r.AddRange(Targets);
                return r;
            }
        }
    }
}
