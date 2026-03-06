import json
import logging
import mimetypes
import os
import shutil
from datetime import datetime
from typing import Dict, List

from app.config.common import IMAGE_DIR, JOURNAL_DIR, JOURNAL_HISTORY_FILE, SESSION_CACHE_FILE

IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp'}

# 统一 UA 模板，设备字段仅替换 system/model/platform
UA_TEMPLATE = (
    "Mozilla/5.0 (Linux; {system}; {model} Build/AP3A.240617.008; wv) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/138.0.7204.180 "
    "Mobile Safari/537.36 XWEB/1380243 MMWEBSDK/20230805 MMWEBID/9843 "
    "MicroMessenger/8.0.42.2460(0x28002A35) WeChat/arm64 Weixin NetType/4G "
    "Language/zh_CN ABI/arm64 MiniProgramEnv/{platform}"
)


def ensure_dir(directory: str) -> None:
    if directory:
        os.makedirs(directory, exist_ok=True)


def save_json_file(file_path: str, params: dict) -> None:
    try:
        ensure_dir(os.path.dirname(file_path))
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(params, file, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.info(f"保存配置失败: {e}")


def read_config(file_path: str) -> dict:
    # 判断文件是否存在
    if not os.path.exists(file_path):
        raise RuntimeError(f"{file_path}文件不存在")
    # 读取文件
    with open(file_path, 'r', encoding='utf-8') as file:
        config = json.load(file)
    # 返回数据
    return config


def build_user_agent(device: dict) -> str:
    system = str(device.get("system", "")).strip()
    model = str(device.get("model", "")).strip()
    platform = str(device.get("platform", "")).strip().lower()
    return UA_TEMPLATE.format(system=system, model=model, platform=platform)


def validate_user_agent_matches_device(device: dict, ua: str):
    if not ua:
        return "未检测到 User-Agent。请在【配置】里点击“生成UA”后再保存。"

    system = str(device.get("system", "")).strip()
    model = str(device.get("model", "")).strip()
    platform = str(device.get("platform", "")).strip().lower()

    if system and f"; {system};" not in ua:
        return f"设备系统与UA不一致：UA中缺少“{system}”。请在【配置】点击“生成UA”自动修复。"
    if model and model not in ua:
        return f"设备型号与UA不一致：UA中缺少“{model}”。请在【配置】点击“生成UA”自动修复。"
    if platform and f"MiniProgramEnv/{platform}" not in ua:
        return (
            f"设备平台与UA不一致：UA中缺少“MiniProgramEnv/{platform}”。"
            "请在【配置】点击“生成UA”自动修复。"
        )
    return None


def validate_config(data: dict):
    if "input" not in data or not isinstance(data["input"], dict):
        return "配置格式不完整：缺少 input。建议重新打开配置页后点击“保存并应用”。"
    input_data = data["input"]

    # location
    loc = input_data.get("location")
    if not isinstance(loc, dict):
        return "缺少位置信息。请填写经纬度（可用“获取坐标”按钮）。"

    required_loc = ["longitude", "latitude"]
    for key in required_loc:
        val = loc.get(key)
        if not val or str(val).strip() == "":
            if key == "longitude":
                return "经度不能为空。示例：116.397128"
            return "纬度不能为空。示例：39.916527"

    try:
        lng = float(str(loc.get("longitude")).strip())
        lat = float(str(loc.get("latitude")).strip())
    except ValueError:
        return "经纬度格式错误：只能填写数字。示例：经度 116.397128，纬度 39.916527"
    if not (-180 <= lng <= 180):
        return "经度超出范围：应在 -180 到 180 之间。"
    if not (-90 <= lat <= 90):
        return "纬度超出范围：应在 -90 到 90 之间。"

    # device
    dev = input_data.get("device")
    if not isinstance(dev, dict):
        return "缺少设备信息。请填写品牌、型号、系统、平台。"

    required_dev = ["brand", "model", "system", "platform"]
    for key in required_dev:
        val = dev.get(key)
        if not val or str(val).strip() == "":
            name_map = {
                "brand": "品牌",
                "model": "型号",
                "system": "系统版本（如 15）",
                "platform": "平台（如 android）",
            }
            return f"{name_map.get(key, key)}不能为空。请在【配置】里补全后保存。"

    # userAgent
    ua = input_data.get("userAgent")
    if not ua or str(ua).strip() == "":
        return "User-Agent 为空。请在【配置】点击“生成UA”后再保存。"

    ua_err = validate_user_agent_matches_device(dev, str(ua))
    if ua_err:
        return ua_err

    # 校验通过
    return None


def _is_allowed_image(path: str) -> bool:
    ext = os.path.splitext(path)[1].lower()
    return ext in IMAGE_EXTS


def ensure_image_dir() -> str:
    ensure_dir(IMAGE_DIR)
    return IMAGE_DIR


def list_images() -> List[str]:
    directory = ensure_image_dir()
    if not os.path.exists(directory):
        return []
    files = []
    for fname in os.listdir(directory):
        fpath = os.path.join(directory, fname)
        if os.path.isfile(fpath) and _is_allowed_image(fpath):
            files.append(fpath)
    return sorted(files)


def import_image(src_path: str) -> str:
    if not src_path or not os.path.exists(src_path):
        raise RuntimeError("请选择要导入的图片")
    if not _is_allowed_image(src_path):
        raise RuntimeError("仅支持导入 PNG/JPG/JPEG/BMP/GIF/WEBP 图片")
    ensure_image_dir()
    base = os.path.basename(src_path)
    name, ext = os.path.splitext(base)
    counter = 1
    dest_name = base
    while os.path.exists(os.path.join(IMAGE_DIR, dest_name)):
        dest_name = f"{name}_{counter}{ext}"
        counter += 1
    dest_path = os.path.join(IMAGE_DIR, dest_name)
    shutil.copy2(src_path, dest_path)
    return dest_path


def delete_image(image_path: str) -> None:
    if not image_path:
        raise RuntimeError("请选择要删除的图片")
    abs_path = os.path.abspath(image_path)
    ensure_image_dir()
    image_dir_abs = os.path.abspath(IMAGE_DIR)
    if os.path.commonpath([abs_path, image_dir_abs]) != image_dir_abs:
        raise RuntimeError("只能删除图片目录中的文件")
    if os.path.exists(abs_path):
        os.remove(abs_path)


def check_img(img_path: str):
    if not img_path:
        raise RuntimeError("请先为拍照签到选择图片")
    ensure_image_dir()
    abs_path = os.path.abspath(img_path)
    if not os.path.exists(abs_path):
        raise RuntimeError(f"图片文件 {abs_path} 不存在")
    if not _is_allowed_image(abs_path):
        raise RuntimeError("请选择支持的图片格式")
    return abs_path


def get_img_file(timestamp, img_path: str):
    target = check_img(img_path)
    mime, _ = mimetypes.guess_type(target)
    if not mime:
        mime = "image/jpeg"
    ext = os.path.splitext(target)[1] or ".jpg"
    return {
        "file": (f"{timestamp}{ext}", open(target, "rb"), mime)
    }


def load_journal_history() -> Dict[str, List[dict]]:
    if not os.path.exists(JOURNAL_HISTORY_FILE):
        return {"generated": [], "submitted": []}
    with open(JOURNAL_HISTORY_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    data.setdefault("generated", [])
    data.setdefault("submitted", [])
    return data


def append_journal_entry(section: str, content: str) -> dict:
    if section not in {"generated", "submitted"}:
        raise ValueError("section must be generated or submitted")
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "content": content
    }
    data = load_journal_history()
    data.setdefault(section, [])
    data[section].insert(0, entry)
    data[section] = data[section][:50]
    ensure_dir(JOURNAL_DIR)
    save_json_file(JOURNAL_HISTORY_FILE, data)
    return entry


def clear_journal_history(section: str = None) -> None:
    """清空历史记录"""
    data = load_journal_history()
    if section:
        if section in data:
            data[section] = []
    else:
        data["generated"] = []
        data["submitted"] = []
    save_json_file(JOURNAL_HISTORY_FILE, data)


def load_session_cache() -> dict:
    """加载会话缓存"""
    if not os.path.exists(SESSION_CACHE_FILE):
        return {}
    try:
        with open(SESSION_CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def save_session_cache(session_id: str, encrypt_value: str, open_id: str, union_id: str, trainee_id: str = None):
    """保存会话缓存，默认过期时间为24小时"""
    import time
    cache = {
        "sessionId": session_id,
        "encryptValue": encrypt_value,
        "openId": open_id,
        "unionId": union_id,
        "traineeId": trainee_id,
        "timestamp": int(time.time()),
        "expire_seconds": 24 * 3600  # 24小时
    }
    ensure_dir(os.path.dirname(SESSION_CACHE_FILE))
    save_json_file(SESSION_CACHE_FILE, cache)


def get_valid_session_cache() -> dict:
    """获取有效的会话缓存，如果过期则返回None"""
    import time
    cache = load_session_cache()
    if not cache:
        return None
    
    timestamp = cache.get("timestamp", 0)
    expire_seconds = cache.get("expire_seconds", 24 * 3600)
    
    if time.time() - timestamp > expire_seconds:
        # 缓存已过期
        return None
    
    return {
        "sessionId": cache.get("sessionId"),
        "encryptValue": cache.get("encryptValue"),
        "openId": cache.get("openId"),
        "unionId": cache.get("unionId"),
        "traineeId": cache.get("traineeId")
    }


def clear_session_cache():
    """清除会话缓存"""
    if os.path.exists(SESSION_CACHE_FILE):
        os.remove(SESSION_CACHE_FILE)
