# -*- coding: utf-8 -*-
r"""
【项目沉淀】通用工具
适用素体：无关          相关素材：无
可复用性：★★★ 换个单子直接能用
用途　　：把定妆照送进本机 ComfyUI 做二次创作改绘（img2img + ControlNet lineart）

本机直连 ComfyUI：API 是 http://127.0.0.1:8188，直接用 Python 标准库请求，
不经过任何远程中转。输入图拷到 $COMFYUI_DIR/input/vrc/，生成图从
$COMFYUI_DIR/output/ 拷回 --out 目录。

目录常量可用环境变量 COMFYUI_DIR 覆盖，默认 ~/comfyui。

ComfyUI 随用随起（2026-09-18 起）：8188 由 systemd socket 守着，第一次请求会自动拉起
ComfyUI（冷启动约 5-10 秒），空闲 15 分钟自动停掉。脚本不用、也不该先 systemctl start。
首次探测给 180 秒；超时才说明按需启动本身坏了，打印排查命令并以退出码 2 结束。

用法：
    python comfy_redraw.py --plan plan.json          # plan 里列 [{src, prompt, tag}]
    python comfy_redraw.py --list-models             # 看有哪些模型
输出落在 $COMFYUI_DIR/output/，脚本会拷回本地 --out 目录。
"""
import os, io, json, time, shutil, sys, argparse, urllib.request, urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit_env  # noqa: E402  读 <工作区>/kit.env（环境变量优先）

COMFYUI_DIR = os.path.expanduser(kit_env.get("COMFYUI_DIR", "~/comfyui"))
INPUT_DIR   = os.path.join(COMFYUI_DIR, "input", "vrc")
OUTPUT_DIR  = os.path.join(COMFYUI_DIR, "output")
API = kit_env.get("COMFYUI_API", "http://127.0.0.1:8188")

def copy_to_input(local, filename):
    """把源图拷进 ComfyUI 的输入目录，目录不存在就建。"""
    os.makedirs(INPUT_DIR, exist_ok=True)
    try:
        shutil.copy2(local, os.path.join(INPUT_DIR, filename))
        return True, ""
    except Exception as e:
        return False, str(e)[:300]

def copy_from_output(remote, local):
    """把 ComfyUI 输出目录里的生成图拷回本地。"""
    try:
        shutil.copy2(remote, local)
        return True, ""
    except Exception as e:
        return False, str(e)[:300]

def api_up(timeout=5):
    """探一下 ComfyUI API 是否在跑。"""
    try:
        with urllib.request.urlopen(API + "/system_stats", timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False

def api_get(path, timeout=60):
    try:
        with urllib.request.urlopen(API + path, timeout=timeout) as resp:
            out = resp.read().decode("utf-8")
        return json.loads(out) if out.strip() else None
    except Exception:
        return None

def api_post_prompt(workflow, timeout=90):
    """把 {"prompt": workflow} 作为 JSON POST 给 ComfyUI。"""
    body = json.dumps({"prompt": workflow}).encode("utf-8")
    req = urllib.request.Request(API + "/prompt", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8"))
        except Exception:
            return {"error": str(e)[:500]}
    except Exception as e:
        return {"error": str(e)[:500]}

# ── 工作流：img2img + ControlNet lineart，保结构、换画风 ──────────────
def build(src_name, positive, negative, ckpt, seed, steps=28, cfg=5.5,
          denoise=0.55, cn_strength=0.65):
    return {
      "1":  {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
      "2":  {"class_type": "LoadImage", "inputs": {"image": src_name, "upload": "image"}},
      "3":  {"class_type": "CLIPTextEncode", "inputs": {"text": positive, "clip": ["1", 1]}},
      "4":  {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["1", 1]}},
      "5":  {"class_type": "VAEEncode",      "inputs": {"pixels": ["2", 0], "vae": ["1", 2]}},
      "6":  {"class_type": "AnimeLineArtPreprocessor",
             "inputs": {"image": ["2", 0], "resolution": 1024}},
      "7":  {"class_type": "ControlNetLoader",
             "inputs": {"control_net_name": "controlnet-union-sdxl-1.0-promax.safetensors"}},
      "8":  {"class_type": "ControlNetApplyAdvanced",
             "inputs": {"positive": ["3", 0], "negative": ["4", 0], "control_net": ["7", 0],
                        "image": ["6", 0], "strength": cn_strength,
                        "start_percent": 0.0, "end_percent": 0.85}},
      "9":  {"class_type": "KSampler",
             "inputs": {"model": ["1", 0], "positive": ["8", 0], "negative": ["8", 1],
                        "latent_image": ["5", 0], "seed": seed, "steps": steps, "cfg": cfg,
                        "sampler_name": "dpmpp_2m", "scheduler": "karras", "denoise": denoise}},
      "10": {"class_type": "VAEDecode", "inputs": {"samples": ["9", 0], "vae": ["1", 2]}},
      "11": {"class_type": "SaveImage",  "inputs": {"images": ["10", 0], "filename_prefix": "vrc/redraw"}},
    }

def wait(pid, timeout=900):
    t0 = time.time()
    while time.time() - t0 < timeout:
        h = api_get(f"/history/{pid}")
        if h and pid in h:
            outs = []
            for node in h[pid].get("outputs", {}).values():
                for im in node.get("images", []):
                    outs.append((im.get("subfolder", ""), im["filename"]))
            return outs
        time.sleep(6)
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan"); ap.add_argument("--out", default="redraw_out")
    ap.add_argument("--ckpt", default="waiNSFWIllustrious_v14.safetensors")
    ap.add_argument("--denoise", type=float, default=0.55)
    ap.add_argument("--list-models", action="store_true")
    a = ap.parse_args()

    if not api_up(timeout=180):   # 第一次请求会触发按需启动，要等 ComfyUI 起来
        print("ComfyUI 180 秒内没有响应，按需启动失败。排查："
              "systemctl status comfyui comfyui-proxy.socket comfyui-proxy.service")
        sys.exit(2)

    if a.list_models:
        j = api_get("/object_info/CheckpointLoaderSimple")
        print(j["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0]); return

    plan = json.load(io.open(a.plan, encoding="utf-8"))
    os.makedirs(INPUT_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(a.out, exist_ok=True)
    NEG = ("worst quality, low quality, blurry, jpeg artifacts, watermark, signature, text, "
           "extra limbs, bad hands, bad anatomy, deformed, 3d render, cgi, plastic skin, lowres")
    for i, item in enumerate(plan):
        src = item["src"]; tag = item.get("tag", f"item{i:02d}")
        name = f"vrc/src_{tag}.png"
        ok, err = copy_to_input(src, f"src_{tag}.png")
        if not ok: print(f"  [{tag}] 传图失败: {err}"); continue
        wf = build(name, item["prompt"], item.get("negative", NEG), a.ckpt,
                   seed=item.get("seed", 100000 + i * 7717), denoise=item.get("denoise", a.denoise))
        r = api_post_prompt(wf)
        pid = r.get("prompt_id")
        if not pid: print(f"  [{tag}] 提交失败 {str(r)[:300]}"); continue
        outs = wait(pid)
        if not outs: print(f"  [{tag}] 超时"); continue
        for sub, fn in outs:
            rp = os.path.join(OUTPUT_DIR, sub, fn) if sub else os.path.join(OUTPUT_DIR, fn)
            d = os.path.join(a.out, f"{tag}__{fn}")
            ok, err = copy_from_output(rp, d)
            print(f"  [{tag}] -> {d}" if ok else f"  [{tag}] 取回失败 {rp}: {err}")

if __name__ == "__main__":
    main()
