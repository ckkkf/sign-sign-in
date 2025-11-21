import json
import logging
import mimetypes
import os
import shutil
from datetime import datetime
from typing import Dict, List

from app.config.common import IMAGE_DIR, JOURNAL_DIR, JOURNAL_HISTORY_FILE

IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp'}


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


def validate_config(data: dict):
    if "input" not in data or not isinstance(data["input"], dict):
        return "缺少 input 字段"
    input_data = data["input"]

    # location
    loc = input_data.get("location")
    if not isinstance(loc, dict):
        return "缺少 input.location"

    required_loc = ["longitude", "latitude"]
    for key in required_loc:
        val = loc.get(key)
        if not val or str(val).strip() == "":
            return f"input.location.{key} 不能为空"

    # device
    dev = input_data.get("device")
    if not isinstance(dev, dict):
        return "缺少 input.device"

    required_dev = ["brand", "model", "system", "platform"]
    for key in required_dev:
        val = dev.get(key)
        if not val or str(val).strip() == "":
            return f"input.device.{key} 不能为空"

    # userAgent
    ua = input_data.get("userAgent")
    if not ua or str(ua).strip() == "":
        return "input.userAgent 不能为空"

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
