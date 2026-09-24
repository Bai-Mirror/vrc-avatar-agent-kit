#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 用途：离线验证菜单行为与覆盖判据，包含必须拒绝的假放行反例。
"""menu_expect_check.py 的离线独立自测（纯标准库，不开 Unity、不跑工程测试）。

覆盖派工 P02 / P02b 的正反例：
  * 零断言拒绝（所有模式）
  * Bool 只有开态：研究模式记录未覆盖、交付模式严格不通过
  * 有开关两态 + 断言：交付模式通过（成功标题「约定覆盖」，不称可交付）
  * 多档（Int / radial）漏一档失败；连续参数交付必须显式 coverage + 出处
  * 显式连续边界 / gears 覆盖完整且来源有效才通过；边界数值保持不被改写
  * coverage 声明解析错误（小数 gears、混入非法值、NaN/Infinity、未知字段/参数、多重约定）非零
  * params.json 重名 / 名单冲突 / 类型错误：干净非零，不静默覆盖、不吐 Python 栈
  * 非法取值 / 参数缺失 / 歧义匹配 / 无法确定覆盖 / 空检查结果：非零
  * slot: 形式与 gen-request 归一化一致，且用同一份有效约定
  * 真实现有研究样例保留预期诊断，且不宣称完整覆盖

直接运行：
  python3 开发工具/通用工具/审查/menu_expect_check_selftest.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(HERE, "menu_expect_check.py")
REPO = os.path.abspath(os.path.join(HERE, os.pardir, os.pardir, os.pardir))

SAMPLE_EXPECT = os.path.join(
    REPO, "_长程任务_20260918", "派工", "tmp", "w5", "期望_工程A_样例.json")
SAMPLE_T1 = os.path.join(
    REPO, "_长程任务_20260918", "审查产出", "工程A", "seq_CL_verify_v3")
SAMPLE_PARAMS = os.path.join(SAMPLE_T1, "09_t4_menu", "params.json")


def bool_param(name="Coat"):
    return {
        "name": name, "declared_in_expression": True, "value_type_name": "Bool",
        "menu_values": [1], "menu_value_kinds": ["toggle"], "suggested_values": [0, 1],
        "radial_labels": [], "radial_label_derived": [], "referenced_by": ["顶层/%s" % name],
    }


def int_param(name="Gear", values=(1, 2, 3)):
    return {
        "name": name, "declared_in_expression": True, "value_type_name": "Int",
        "menu_values": list(values), "menu_value_kinds": ["button"],
        "suggested_values": list(values), "radial_labels": [], "radial_label_derived": [],
        "referenced_by": ["顶层/%s" % name],
    }


def radial_param(name="Hue", labels=("红", "黄", "蓝", "绿")):
    return {
        "name": name, "declared_in_expression": True, "value_type_name": "Float",
        "menu_values": [], "menu_value_kinds": ["radial"],
        "suggested_values": [0, 0.25, 0.5, 0.75, 1],
        "radial_labels": list(labels),
        "radial_label_derived": [0, 0.125, 0.375, 0.625, 0.875, 1],
        "referenced_by": ["顶层/%s" % name],
    }


def params_obj(params):
    return {
        "tool": "menu", "avatar": "A",
        "declared_param_names": [p["name"] for p in params],
        "menu_param_names": [p["name"] for p in params],
        "parameters": params,
    }


class ToolCase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="mec_selftest_")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.t1 = os.path.join(self.dir, "t1")
        os.makedirs(self.t1)

    def write(self, name, obj):
        path = os.path.join(self.dir, name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False)
        return path

    def t1_state(self, sid, params, renderers):
        return self.t1_write(sid, {"id": sid, "params_applied": params, "renderers": renderers})

    def t1_write(self, sid, obj):
        path = os.path.join(self.t1, "state_%s.json" % sid)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False)
        return path

    def run_tool(self, *args):
        return subprocess.run([sys.executable, TOOL] + list(args),
                              capture_output=True, text=True)

    def run_check(self, expect_path, params_path=None, delivery=False, json_out=None):
        if json_out is None:
            json_out = os.path.join(self.dir, "rep.json")
        out_md = os.path.join(self.dir, "rep.md")
        argv = ["check", "--expect", expect_path, "--t1", self.t1,
                "--out", out_md, "--json", json_out]
        if params_path:
            argv += ["--params", params_path]
        if delivery:
            argv.append("--delivery")
        proc = self.run_tool(*argv)
        report = None
        if os.path.exists(json_out):
            with open(json_out, encoding="utf-8") as f:
                report = json.load(f)
        md = ""
        if os.path.exists(out_md):
            with open(out_md, encoding="utf-8") as f:
                md = f.read()
        return proc, report, md

    def expectation(self, states, source="交付说明.md:1", coverage=None, avatar="A"):
        obj = {"avatar": avatar, "source": source, "states": states}
        if coverage is not None:
            obj["coverage"] = coverage
        return self.write("expect.json", obj)


class TestZeroAssertion(ToolCase):
    def test_state_without_assertions_rejected_all_modes(self):
        p = self.write("params.json", params_obj([bool_param()]))
        exp = self.expectation([{"name": "Coat 开", "set": {"Coat": 1}, "note": "d:1"}])
        proc, _, _ = self.run_check(exp, p)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("没有任何行为断言", proc.stderr)
        proc2, _, _ = self.run_check(exp, p, delivery=True)
        self.assertEqual(proc2.returncode, 2, proc2.stderr)

    def test_whole_expectation_without_assertions_rejected(self):
        exp = self.expectation([
            {"name": "S1", "set": {"Coat": 1}, "note": "d:1"},
            {"name": "S2", "set": {"Coat": 0}, "note": "d:2"},
        ])
        proc, _, _ = self.run_check(exp)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("没有任何行为断言", proc.stderr)


class TestBoolCoverage(ToolCase):
    def setUp(self):
        super().setUp()
        self.params = self.write("params.json", params_obj([bool_param()]))
        self.t1_state("coat_on", {"Coat": 1}, [{"path": "CoatMesh", "visible": True}])
        self.t1_state("coat_off", {"Coat": 0}, [{"path": "CoatMesh", "visible": False}])

    def test_only_on_state_research_records_but_delivery_fails(self):
        exp = self.expectation([{
            "name": "Coat 开", "set": {"Coat": 1},
            "visible": ["CoatMesh"], "note": "交付说明.md:1",
        }])
        proc, rep, _ = self.run_check(exp, self.params)
        self.assertEqual(proc.returncode, 0, proc.stderr)  # 研究模式：只记录
        self.assertEqual(rep["uncovered_count"], 1)
        self.assertEqual(rep["uncovered_units"][0]["unit"], "0")
        self.assertEqual(rep["uncovered_units"][0]["param"], "Coat")

        proc2, rep2, md2 = self.run_check(exp, self.params, delivery=True)
        self.assertNotEqual(proc2.returncode, 0)
        self.assertEqual(proc2.returncode, 1)
        self.assertEqual(rep2["uncovered_count"], 1)
        self.assertEqual(rep2["business_fail_count"], 0)
        self.assertIn("不通过", md2)
        self.assertNotIn("菜单行为断言通过", md2)

    def test_both_switch_states_with_assertions_delivery_passes(self):
        exp = self.expectation([
            {"name": "Coat 开", "set": {"Coat": 1}, "visible": ["CoatMesh"], "note": "d:1"},
            {"name": "Coat 关", "set": {"Coat": 0}, "hidden": ["CoatMesh"], "note": "d:2"},
        ])
        proc, rep, md = self.run_check(exp, self.params, delivery=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(rep["uncovered_count"], 0)
        self.assertEqual(rep["exit_code"], 0)
        # 成功标题只写「约定覆盖」，不再直接称「可交付」
        self.assertIn("菜单行为断言通过（约定覆盖）", md)
        self.assertNotIn("**可交付**", md)

    def test_adding_one_visible_assertion_is_not_full_coverage(self):
        # 派工反例：只有开态 + 一条可见断言，仍不能被当成「全参数覆盖」。
        exp = self.expectation([{
            "name": "Coat 开", "set": {"Coat": 1},
            "visible": ["CoatMesh"], "note": "d:1",
        }])
        _, rep, _ = self.run_check(exp, self.params, delivery=True)
        self.assertGreater(rep["uncovered_count"], 0)
        self.assertEqual([u["unit"] for u in rep["uncovered_units"]], ["0"])


class TestMultiGear(ToolCase):
    def test_int_missing_one_gear_fails_delivery(self):
        p = self.write("params.json", params_obj([int_param()]))
        for i, v in enumerate((1, 2, 3)):
            self.t1_state("g%d" % v, {"Gear": v},
                          [{"path": "P%d" % v, "visible": True}])
        exp = self.expectation([
            {"name": "G1", "set": {"Gear": 1}, "visible": ["P1"], "note": "d:1"},
            {"name": "G2", "set": {"Gear": 2}, "visible": ["P2"], "note": "d:2"},
        ])
        proc, rep, _ = self.run_check(exp, p, delivery=True)
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertEqual([u["unit"] for u in rep["uncovered_units"]], ["3"])

    def test_int_all_gears_passes_delivery(self):
        p = self.write("params.json", params_obj([int_param()]))
        for v in (1, 2, 3):
            self.t1_state("g%d" % v, {"Gear": v}, [{"path": "P%d" % v, "visible": True}])
        exp = self.expectation([
            {"name": "G%d" % v, "set": {"Gear": v}, "visible": ["P%d" % v], "note": "d:%d" % v}
            for v in (1, 2, 3)
        ])
        proc, rep, _ = self.run_check(exp, p, delivery=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(rep["uncovered_count"], 0)

    def test_radial_known_gears_missing_one_fails(self):
        p = self.write("params.json", params_obj([radial_param()]))
        mids = [0.125, 0.375, 0.625, 0.875]
        for i, m in enumerate(mids):
            self.t1_state("h%d" % i, {"Hue": m},
                          [{"path": "C%d" % i, "visible": True}])
        exp = self.expectation([
            {"name": "档%d" % i, "set": {"Hue": "slot:%d" % i},
             "visible": ["C%d" % i], "note": "d:%d" % i}
            for i in range(3)  # 漏第 4 档
        ], coverage={"Hue": {"gears": 4, "note": "档位表.md:1"}})
        proc, rep, _ = self.run_check(exp, p, delivery=True)
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertEqual(rep["uncovered_count"], 1)
        self.assertEqual(rep["uncovered_units"][0]["unit"], "档4/4")

    def test_radial_labels_only_delivery_requires_explicit_contract(self):
        # 交付模式不拿 radial_labels 当档数依据：有 labels 但无 coverage 约定仍须非零。
        p = self.write("params.json", params_obj([radial_param()]))
        mids = [0.125, 0.375, 0.625, 0.875]
        for i, m in enumerate(mids):
            self.t1_state("h%d" % i, {"Hue": m}, [{"path": "C%d" % i, "visible": True}])
        exp = self.expectation([
            {"name": "档%d" % i, "set": {"Hue": "slot:%d" % i},
             "visible": ["C%d" % i], "note": "d:%d" % i}
            for i in range(4)
        ])
        proc, rep, _ = self.run_check(exp, p, delivery=True)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertEqual(rep["undetermined_count"], 1)
        self.assertTrue(any("显式 coverage" in e for e in rep["check_failures"]))

    def test_radial_unknown_gears_without_contract_delivery_fails(self):
        # 主理反例 unknown_radial：档数未知、无约定、只有 0/1 两态，交付必须非零。
        p = self.write("params.json", params_obj([radial_param(labels=())]))
        self.t1_state("o0", {"Hue": 0.0}, [{"path": "Lo", "visible": True}])
        self.t1_state("o1", {"Hue": 1.0}, [{"path": "Hi", "visible": True}])
        exp = self.expectation([
            {"name": "Out0", "set": {"Hue": 0}, "visible": ["Lo"], "note": "d:1"},
            {"name": "Out1", "set": {"Hue": 1}, "visible": ["Hi"], "note": "d:2"},
        ])
        proc, rep, md = self.run_check(exp, p, delivery=True)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertEqual(rep["undetermined_count"], 1)
        self.assertNotIn("菜单行为断言通过", md)

    def test_radial_explicit_boundary_contract_with_source_passes(self):
        # 显式连续边界约定 + 出处，覆盖 0/1 才可通过。
        p = self.write("params.json", params_obj([radial_param(labels=())]))
        self.t1_state("o0", {"Hue": 0.0}, [{"path": "Lo", "visible": True}])
        self.t1_state("o1", {"Hue": 1.0}, [{"path": "Hi", "visible": True}])
        exp = self.expectation(
            [{"name": "Out0", "set": {"Hue": 0}, "visible": ["Lo"], "note": "d:1"},
             {"name": "Out1", "set": {"Hue": 1}, "visible": ["Hi"], "note": "d:2"}],
            coverage={"Hue": {"boundaries": [0, 1], "note": "边界约定：文档.md:7"}},
        )
        proc, rep, md = self.run_check(exp, p, delivery=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("期望显式声明 boundaries", rep["coverage_requirements"][0]["convention"])
        self.assertIn("菜单行为断言通过（约定覆盖）", md)

    def test_radial_contract_without_source_delivery_fails(self):
        p = self.write("params.json", params_obj([radial_param(labels=())]))
        self.t1_state("o0", {"Hue": 0.0}, [{"path": "Lo", "visible": True}])
        self.t1_state("o1", {"Hue": 1.0}, [{"path": "Hi", "visible": True}])
        exp = self.expectation(
            [{"name": "Out0", "set": {"Hue": 0}, "visible": ["Lo"], "note": "d:1"},
             {"name": "Out1", "set": {"Hue": 1}, "visible": ["Hi"], "note": "d:2"}],
            coverage={"Hue": {"boundaries": [0, 1]}},
        )
        proc, rep, _ = self.run_check(exp, p, delivery=True)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertTrue(any("出处" in e for e in rep["check_failures"]))

    def test_radial_research_mode_may_infer_labels(self):
        p = self.write("params.json", params_obj([radial_param()]))
        mids = [0.125, 0.375, 0.625, 0.875]
        for i, m in enumerate(mids):
            self.t1_state("h%d" % i, {"Hue": m}, [{"path": "C%d" % i, "visible": True}])
        exp = self.expectation([
            {"name": "档%d" % i, "set": {"Hue": "slot:%d" % i},
             "visible": ["C%d" % i], "note": "d:%d" % i}
            for i in range(4)
        ])
        proc, rep, _ = self.run_check(exp, p)  # 研究模式
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("推测", rep["coverage_requirements"][0]["convention"])

    def test_float_with_discrete_menu_values_is_evidence(self):
        # 只有离散控件的Float可按真实菜单值处理；混有轮盘则另须连续约定。
        rp = radial_param(labels=())
        rp["menu_value_kinds"] = ["button"]
        rp["menu_values"] = [0, 0.5, 1]
        p = self.write("params.json", params_obj([rp]))
        for i, v in enumerate([0.0, 0.5, 1.0]):
            self.t1_state("m%d" % i, {"Hue": v}, [{"path": "M%d" % i, "visible": True}])
        exp = self.expectation([
            {"name": "M%d" % i, "set": {"Hue": v}, "visible": ["M%d" % i], "note": "d:%d" % i}
            for i, v in enumerate([0, 0.5, 1])
        ])
        proc, rep, _ = self.run_check(exp, p, delivery=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("menu_values", rep["coverage_requirements"][0]["convention"])

    def test_mixed_radial_button_needs_contract_and_all_button_values(self):
        rp = radial_param(labels=())
        rp["menu_value_kinds"] = ["radial", "button"]
        rp["menu_values"] = [0.5]
        p = self.write("params.json", params_obj([rp]))
        states = []
        for i, value in enumerate([0.0, 1.0, 0.5]):
            self.t1_state("m%d" % i, {"Hue": value}, [{"path": "Mesh", "visible": True}])
            states.append({"name": "m%d" % i, "set": {"Hue": value},
                           "visible": ["Mesh"], "note": "spec:1"})
        exp = self.expectation(states)
        proc, _, _ = self.run_check(exp, p, delivery=True)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        contract = {"Hue": {"boundaries": [0, 1], "note": "spec:2"}}
        exp = self.expectation(states[:2], coverage=contract)
        proc, _, _ = self.run_check(exp, p, delivery=True)
        self.assertEqual(proc.returncode, 1, proc.stderr)  # 约定之外的真实按钮值也不能丢
        exp = self.expectation(states, coverage=contract)
        proc, _, _ = self.run_check(exp, p, delivery=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_explicit_coverage_gears_upgrades_strictness(self):
        p = self.write("params.json", params_obj([radial_param(labels=())]))
        self.t1_state("o0", {"Hue": 0.0}, [{"path": "Lo", "visible": True}])
        self.t1_state("o1", {"Hue": 1.0}, [{"path": "Hi", "visible": True}])
        exp = self.expectation(
            [{"name": "Out0", "set": {"Hue": 0}, "visible": ["Lo"], "note": "d:1"},
             {"name": "Out1", "set": {"Hue": 1}, "visible": ["Hi"], "note": "d:2"}],
            coverage={"Hue": {"gears": 5, "note": "文档写明 5 档：档位表.md:14"}},
        )
        proc, rep, _ = self.run_check(exp, p, delivery=True)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(rep["uncovered_count"], 3)


class TestSlotConsistency(ToolCase):
    def test_slot_form_normalized_like_gen_request(self):
        p = self.write("params.json", params_obj([radial_param()]))
        mids = [0.125, 0.375, 0.625, 0.875]
        for i, m in enumerate(mids):
            self.t1_state("h%d" % i, {"Hue": m}, [{"path": "C%d" % i, "visible": True}])
        exp = self.expectation([
            {"name": "档%d" % i, "set": {"Hue": "slot:%d" % i},
             "visible": ["C%d" % i], "note": "d:%d" % i}
            for i in range(4)
        ], coverage={"Hue": {"gears": 4, "note": "档位表.md:1"}})
        proc, rep, _ = self.run_check(exp, p, delivery=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(rep["missing_count"], 0)
        self.assertEqual(rep["uncovered_count"], 0)

        # gen-request 必须写出同一组档中点，否则 check 与请求会分叉
        req_path = os.path.join(self.dir, "req.json")
        gen = self.run_tool("gen-request", "--delivery", "--expect", exp, "--params", p,
                            "--out", req_path)
        self.assertEqual(gen.returncode, 0, gen.stderr)
        with open(req_path, encoding="utf-8") as f:
            req = json.load(f)
        got = [s["params"]["Hue"] for s in req["states"]]
        for a, b in zip(got, mids):
            self.assertAlmostEqual(a, b, places=6)

    def test_float_values_are_not_rewritten(self):
        # 边界数值保持：要测 0.25 就发 0.25，不被吸附到 0.375。
        p = self.write("params.json", params_obj([radial_param()]))
        self.t1_state("exact", {"Hue": 0.25}, [{"path": "Q", "visible": True}])
        exp = self.expectation(
            [{"name": "quarter", "set": {"Hue": 0.25}, "visible": ["Q"], "note": "d:1"}],
            coverage={"Hue": {"gears": 4, "note": "档位表.md:1"}},
        )
        req_path = os.path.join(self.dir, "req.json")
        gen = self.run_tool("gen-request", "--delivery", "--expect", exp, "--params", p,
                            "--out", req_path)
        self.assertEqual(gen.returncode, 0, gen.stderr)
        with open(req_path, encoding="utf-8") as f:
            req = json.load(f)
        self.assertAlmostEqual(req["states"][0]["params"]["Hue"], 0.25, places=6)

        # check 用同一原值匹配 T1 的 0.25，不报缺失
        proc, rep, _ = self.run_check(exp, p, delivery=True)
        self.assertEqual(rep["missing_count"], 0, proc.stderr)
        self.assertEqual(rep["input_anomaly_states"], [])

    def test_integer_zero_one_are_endpoints_not_slots(self):
        p = self.write("params.json", params_obj([radial_param()]))
        self.t1_state("p0", {"Hue": 0.0}, [{"path": "P0", "visible": True}])
        self.t1_state("p1", {"Hue": 1.0}, [{"path": "P1", "visible": True}])
        exp = self.expectation(
            [{"name": "Min", "set": {"Hue": 0}, "visible": ["P0"], "note": "d:1"},
             {"name": "Max", "set": {"Hue": 1}, "visible": ["P1"], "note": "d:2"}],
            coverage={"Hue": {"gears": 4, "note": "档位表.md:1"}},
        )
        req_path = os.path.join(self.dir, "req.json")
        gen = self.run_tool("gen-request", "--delivery", "--expect", exp, "--params", p,
                            "--out", req_path)
        self.assertEqual(gen.returncode, 0, gen.stderr)
        with open(req_path, encoding="utf-8") as f:
            req = json.load(f)
        vals = [s["params"]["Hue"] for s in req["states"]]
        self.assertEqual(vals, [0.0, 1.0])  # 端点原值，不是第 1/4 档中点 0.125/0.875

    def test_bare_integer_slot_range_reports_error(self):
        p = self.write("params.json", params_obj([radial_param()]))
        self.t1_state("x", {"Hue": 0.625}, [{"path": "X", "visible": True}])
        exp = self.expectation(
            [{"name": "bad", "set": {"Hue": 2}, "visible": ["X"], "note": "d:1"}],
            coverage={"Hue": {"gears": 4, "note": "档位表.md:1"}},
        )
        proc, rep, _ = self.run_check(exp, p)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertTrue(any("slot:2" in e for e in rep["check_failures"]))


class TestStrictInputs(ToolCase):
    def test_delivery_requires_params(self):
        self.t1_state("coat_on", {"Coat": 1}, [{"path": "CoatMesh", "visible": True}])
        exp = self.expectation([{"name": "Coat 开", "set": {"Coat": 1},
                                 "visible": ["CoatMesh"], "note": "d:1"}])
        proc, rep, _ = self.run_check(exp, None, delivery=True)
        self.assertEqual(proc.returncode, 2)
        self.assertTrue(any("--params" in e for e in rep["check_failures"]))

    def test_delivery_requires_source_and_each_note(self):
        p = self.write("params.json", params_obj([bool_param()]))
        self.t1_state("coat_on", {"Coat": 1}, [{"path": "CoatMesh", "visible": True}])
        exp = self.write("expect.json", {
            "avatar": "A", "source": "",
            "states": [{"name": "Coat 开", "set": {"Coat": 1},
                        "visible": ["CoatMesh"], "note": ""}],
        })
        proc, rep, _ = self.run_check(exp, p, delivery=True)
        self.assertEqual(proc.returncode, 2)
        joined = " ".join(rep["check_failures"])
        self.assertIn("source", joined)
        self.assertIn("note", joined)

    def test_ambiguous_match_delivery_check_failure(self):
        p = self.write("params.json", params_obj([bool_param()]))
        self.t1_state("coat_on_a", {"Coat": 1}, [{"path": "CoatMesh", "visible": True}])
        self.t1_state("coat_on_b", {"Coat": 1}, [{"path": "CoatMesh", "visible": True}])
        exp = self.expectation([{"name": "Coat 开", "set": {"Coat": 1},
                                 "visible": ["CoatMesh"], "note": "d:1"}])
        proc, rep, _ = self.run_check(exp, p, delivery=True)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(rep["ambiguous_count"], 1)
        self.assertTrue(any("无法唯一判定" in e for e in rep["check_failures"]))

    def test_wrong_value_is_input_error_both_modes(self):
        p = self.write("params.json", params_obj([bool_param()]))
        self.t1_state("coat_on", {"Coat": 1}, [{"path": "CoatMesh", "visible": True}])
        exp = self.expectation([{"name": "Coat bad", "set": {"Coat": "maybe"},
                                 "visible": ["CoatMesh"], "note": "d:1"}])
        for delivery in (False, True):
            proc, rep, _ = self.run_check(exp, p, delivery=delivery)
            self.assertEqual(proc.returncode, 2, proc.stderr)
            self.assertTrue(any("只接受 0/1" in e for e in rep["check_failures"]))

    def test_unknown_param_research_warns_delivery_fails(self):
        p = self.write("params.json", params_obj([bool_param("Coat")]))
        self.t1_state("mystery", {"Mystery": 1}, [{"path": "X", "visible": True}])
        exp = self.expectation([{"name": "Mystery", "set": {"Mystery": 1},
                                 "visible": ["X"], "note": "d:1"}])
        proc, rep, _ = self.run_check(exp, p)
        self.assertEqual(proc.returncode, 0, proc.stderr)  # 研究模式降级为 warning
        self.assertTrue(any("不在 params.json" in w for w in rep["warnings"]))
        proc2, rep2, _ = self.run_check(exp, p, delivery=True)
        self.assertEqual(proc2.returncode, 2)
        self.assertTrue(any("不在 params.json" in e for e in rep2["check_failures"]))

    def test_empty_check_rows_delivery_fails(self):
        p = self.write("params.json", params_obj([bool_param()]))
        self.t1_state("other", {"Other": 1}, [{"path": "X", "visible": True}])
        exp = self.expectation([{"name": "Coat 开", "set": {"Coat": 1},
                                 "visible": ["CoatMesh"], "note": "d:1"}])
        proc, rep, _ = self.run_check(exp, p, delivery=True)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(rep["missing_count"], 1)
        self.assertTrue(any("检查结果为空" in e for e in rep["check_failures"]))

    def test_undetermined_coverage_delivery_fails(self):
        ip = int_param("X", values=())
        ip["suggested_values"] = []
        p = self.write("params.json", params_obj([ip]))
        self.t1_state("x7", {"X": 7}, [{"path": "X7", "visible": True}])
        exp = self.expectation([{"name": "X7", "set": {"X": 7},
                                 "visible": ["X7"], "note": "d:1"}])
        proc, rep, _ = self.run_check(exp, p, delivery=True)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(rep["undetermined_count"], 1)
        self.assertTrue(any("无法确定覆盖" in e for e in rep["check_failures"]))


class TestInvalidContract(ToolCase):
    """coverage 声明解析错误：必须报输入错误，不得因基础覆盖可推导就吞掉。"""

    def _bool_setup(self, spec):
        p = self.write("params.json", params_obj([bool_param("X")]))
        self.t1_state("x0", {"X": 0}, [{"path": "Xmesh", "visible": False}])
        self.t1_state("x1", {"X": 1}, [{"path": "Xmesh", "visible": True}])
        exp = self.expectation(
            [{"name": "X on", "set": {"X": 1}, "visible": ["Xmesh"], "note": "d:1"},
             {"name": "X off", "set": {"X": 0}, "hidden": ["Xmesh"], "note": "d:2"}],
            coverage={"X": spec},
        )
        return p, exp

    def test_bad_gears_ignored_before_now_errors(self):
        # 主理反例 invalid_contract：Bool 两态齐 + gears="oops"，修前 exit 0。
        p, exp = self._bool_setup({"gears": "oops"})
        proc, rep, _ = self.run_check(exp, p, delivery=True)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertTrue(any("gears 必须是整数" in e for e in rep["check_failures"]),
                        rep["check_failures"])

    def test_fractional_gears_not_truncated(self):
        p, exp = self._bool_setup({"gears": 3.5, "note": "文档:1"})
        proc, rep, _ = self.run_check(exp, p, delivery=True)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertTrue(any("gears 必须是整数" in e for e in rep["check_failures"]))

    def test_absurd_gears_rejected(self):
        p, exp = self._bool_setup({"gears": 10 ** 12, "note": "文档:1"})
        proc, rep, _ = self.run_check(exp, p, delivery=True)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertTrue(any("过大" in e for e in rep["check_failures"]))

    def test_mixed_invalid_units_not_silently_filtered(self):
        p, exp = self._bool_setup({"units": [0, "bad", 1], "note": "文档:1"})
        proc, rep, _ = self.run_check(exp, p, delivery=True)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertTrue(any("不是有限数值" in e for e in rep["check_failures"]))

    def test_nan_units_rejected(self):
        p, exp = self._bool_setup({"units": [0.0, float("nan")], "note": "文档:1"})
        proc, rep, _ = self.run_check(exp, p, delivery=True)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertTrue(any("不是有限数值" in e for e in rep["check_failures"]))

    def test_infinity_boundary_rejected(self):
        p, exp = self._bool_setup({"boundaries": [0.0, float("inf")], "note": "文档:1"})
        proc, rep, _ = self.run_check(exp, p, delivery=True)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertTrue(any("不是有限数值" in e for e in rep["check_failures"]))

    def test_unknown_field_rejected(self):
        p, exp = self._bool_setup({"gears": 3, "note": "文档:1", "oops": 1})
        proc, rep, _ = self.run_check(exp, p, delivery=True)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertTrue(any("无法识别的字段" in e for e in rep["check_failures"]))

    def test_multiple_conventions_rejected(self):
        p, exp = self._bool_setup({"gears": 3, "units": [0, 1], "note": "文档:1"})
        proc, rep, _ = self.run_check(exp, p, delivery=True)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertTrue(any("歧义" in e for e in rep["check_failures"]))

    def test_unknown_param_contract_rejected(self):
        p = self.write("params.json", params_obj([bool_param("X")]))
        self.t1_state("x0", {"X": 0}, [{"path": "Xmesh", "visible": False}])
        self.t1_state("x1", {"X": 1}, [{"path": "Xmesh", "visible": True}])
        exp = self.expectation(
            [{"name": "X on", "set": {"X": 1}, "visible": ["Xmesh"], "note": "d:1"},
             {"name": "X off", "set": {"X": 0}, "hidden": ["Xmesh"], "note": "d:2"}],
            coverage={"Ghost": {"gears": 3, "note": "文档:1"}},
        )
        proc, rep, _ = self.run_check(exp, p, delivery=True)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertTrue(any("未知参数约定" in e for e in rep["check_failures"]))

    def test_bad_contract_does_not_fall_back_to_lenient_default(self):
        # 坏约定不得退成宽松默认（研究模式同样报输入错误）。
        p, exp = self._bool_setup({"gears": "oops"})
        proc, rep, _ = self.run_check(exp, p)  # 研究模式
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertTrue(any("gears 必须是整数" in e for e in rep["check_failures"]))

    def test_source_key_counts_as_provenance(self):
        p, exp = self._bool_setup({"gears": 2, "source": "档位表.md:3"})
        proc, rep, _ = self.run_check(exp, p, delivery=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)


class TestDuplicateParams(ToolCase):
    """params.json schema 与唯一性：重名/名单冲突必须非零，不得静默覆盖。"""

    def _coat_expect(self):
        return self.expectation(
            [{"name": "Coat 开", "set": {"Coat": 1}, "visible": ["CoatMesh"], "note": "d:1"},
             {"name": "Coat 关", "set": {"Coat": 0}, "hidden": ["CoatMesh"], "note": "d:2"}])

    def setUp(self):
        super().setUp()
        self.t1_state("c0", {"Coat": 0}, [{"path": "CoatMesh", "visible": False}])
        self.t1_state("c1", {"Coat": 1}, [{"path": "CoatMesh", "visible": True}])

    def test_duplicate_parameter_name_rejected(self):
        # 主理反例 duplicate_parameter：同名两条，修前 by_name 静默覆盖 → exit 0。
        p = self.write("params.json", params_obj([bool_param("Dup"), bool_param("Dup")]))
        exp = self.expectation(
            [{"name": "Dup on", "set": {"Dup": 1}, "visible": ["CoatMesh"], "note": "d:1"},
             {"name": "Dup off", "set": {"Dup": 0}, "hidden": ["CoatMesh"], "note": "d:2"}])
        proc, rep, _ = self.run_check(exp, p, delivery=True)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("重复", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertIsNone(rep)  # 错误结构：干净的非零，不写假报告

    def test_duplicate_menu_param_names_rejected(self):
        pr = params_obj([bool_param("Coat")])
        pr["menu_param_names"] = ["Coat", "Coat"]
        p = self.write("params.json", pr)
        proc, rep, _ = self.run_check(self._coat_expect(), p, delivery=True)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("重复", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)

    def test_menu_param_names_undefined_conflict_rejected(self):
        pr = params_obj([bool_param("Coat")])
        pr["menu_param_names"] = ["Coat", "Ghost"]
        p = self.write("params.json", pr)
        proc, rep, _ = self.run_check(self._coat_expect(), p, delivery=True)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("冲突", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)

    def test_menu_param_names_vs_references_conflict_rejected(self):
        pr = params_obj([bool_param("Coat")])
        pr["parameters"][0]["menu_value_kinds"] = []
        pr["parameters"][0]["referenced_by"] = []
        p = self.write("params.json", pr)
        proc, rep, _ = self.run_check(self._coat_expect(), p, delivery=True)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("口径冲突", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)

    def test_parameters_wrong_type_rejected(self):
        pr = {"tool": "menu", "avatar": "A", "parameters": {"Coat": {}}}
        p = self.write("params.json", pr)
        proc, rep, _ = self.run_check(self._coat_expect(), p, delivery=True)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("parameters", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)

    def test_parameter_missing_name_rejected(self):
        pr = {"tool": "menu", "avatar": "A", "parameters": [{"value_type_name": "Bool"}]}
        p = self.write("params.json", pr)
        proc, rep, _ = self.run_check(self._coat_expect(), p, delivery=True)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("name", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)


class TestGenRequest(ToolCase):
    def test_gen_request_rejects_zero_assertion(self):
        p = self.write("params.json", params_obj([bool_param()]))
        exp = self.expectation([{"name": "Coat 开", "set": {"Coat": 1}, "note": "d:1"}])
        out = os.path.join(self.dir, "req.json")
        proc = self.run_tool("gen-request", "--expect", exp, "--params", p, "--out", out)
        self.assertEqual(proc.returncode, 2)
        self.assertFalse(os.path.exists(out))

    def test_gen_request_delivery_requires_provenance(self):
        p = self.write("params.json", params_obj([bool_param()]))
        exp = self.write("expect.json", {
            "avatar": "A", "source": "",
            "states": [{"name": "Coat 开", "set": {"Coat": 1},
                        "visible": ["CoatMesh"], "note": ""}],
        })
        out = os.path.join(self.dir, "req.json")
        proc = self.run_tool("gen-request", "--delivery", "--expect", exp,
                             "--params", p, "--out", out)
        self.assertEqual(proc.returncode, 2)
        self.assertFalse(os.path.exists(out))
        proc2 = self.run_tool("gen-request", "--expect", exp, "--params", p, "--out", out)
        self.assertEqual(proc2.returncode, 0, proc2.stderr)  # 研究模式不强制出处

    def test_gen_request_delivery_requires_explicit_continuous_contract(self):
        # gen-request 与 check 使用同一有效约定：连续参数无显式 coverage 时请求也不生成。
        p = self.write("params.json", params_obj([radial_param(labels=())]))
        exp = self.expectation(
            [{"name": "Out0", "set": {"Hue": 0}, "visible": ["Lo"], "note": "d:1"},
             {"name": "Out1", "set": {"Hue": 1}, "visible": ["Hi"], "note": "d:2"}])
        out = os.path.join(self.dir, "req.json")
        proc = self.run_tool("gen-request", "--delivery", "--expect", exp,
                             "--params", p, "--out", out)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertFalse(os.path.exists(out))

        exp2 = self.expectation(
            [{"name": "Out0", "set": {"Hue": 0}, "visible": ["Lo"], "note": "d:1"},
             {"name": "Out1", "set": {"Hue": 1}, "visible": ["Hi"], "note": "d:2"}],
            coverage={"Hue": {"boundaries": [0, 1], "note": "边界:文档.md:7"}})
        proc2 = self.run_tool("gen-request", "--delivery", "--expect", exp2,
                              "--params", p, "--out", out)
        self.assertEqual(proc2.returncode, 0, proc2.stderr)
        self.assertTrue(os.path.exists(out))


class TestRealResearchSample(ToolCase):
    """真实现有研究样例：保留预期诊断，不假装完整。"""

    def setUp(self):
        super().setUp()
        for path in (SAMPLE_EXPECT, SAMPLE_T1, SAMPLE_PARAMS):
            self.assertTrue(os.path.exists(path), "样例缺失：%s" % path)

    def run_sample(self, delivery):
        out_md = os.path.join(self.dir, "sample.md")
        out_json = os.path.join(self.dir, "sample.json")
        argv = ["check", "--expect", SAMPLE_EXPECT, "--t1", SAMPLE_T1,
                "--params", SAMPLE_PARAMS, "--out", out_md, "--json", out_json]
        if delivery:
            argv.append("--delivery")
        proc = self.run_tool(*argv)
        with open(out_json, encoding="utf-8") as f:
            rep = json.load(f)
        with open(out_md, encoding="utf-8") as f:
            md = f.read()
        return proc, rep, md

    def test_research_mode_preserves_diagnostics(self):
        proc, rep, md = self.run_sample(delivery=False)
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertEqual(rep["mode"], "research")
        self.assertEqual(len(rep["rows"]), 29)
        self.assertEqual(rep["business_fail_count"], 1)
        self.assertEqual(rep["missing_count"], 2)
        self.assertGreater(rep["uncovered_count"], 0)
        # 真实不一致必须如实报出，且不得宣称完整/可交付
        fails = [r for r in rep["rows"] if not r["ok"]]
        self.assertEqual(len(fails), 1)
        self.assertIn("Foot_heel_OFF", fails[0]["item"])
        self.assertNotIn("**可交付**", md)
        self.assertIn("局部", md)
        self.assertIn("不代表参数全组合", md)

    def test_delivery_mode_on_sample_is_nonzero(self):
        proc, rep, md = self.run_sample(delivery=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(rep["mode"], "delivery")
        # 连续参数没有显式 coverage 约定 → 无法确定覆盖（exit 2），不是假 PASS
        self.assertGreater(rep["undetermined_count"], 0)
        self.assertGreater(rep["uncovered_count"], 0)
        self.assertIn("不通过", md)
        self.assertNotIn("菜单行为断言通过", md)


if __name__ == "__main__":
    unittest.main(verbosity=2)
