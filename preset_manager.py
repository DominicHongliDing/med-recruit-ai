import json
import os

DB_FILE = "job_presets.json"

def load_presets():
    """加载所有保存的岗位配置"""
    if not os.path.exists(DB_FILE):
        return {}
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_preset(name, jd, must_haves, role_type):
    """保存当前配置到文件"""
    presets = load_presets()
    presets[name] = {
        "jd": jd,
        "must_haves": must_haves,
        "role_type": role_type
    }
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(presets, f, ensure_ascii=False, indent=4)

def delete_preset(name):
    """删除某个配置"""
    presets = load_presets()
    if name in presets:
        del presets[name]
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(presets, f, ensure_ascii=False, indent=4)
