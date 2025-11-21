import json
import logging
import os


def save_json_file(file_path: str, params: dict) -> None:
    try:
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


def check_img():
    img_path = "img.png"

    if not os.path.exists(img_path):
        raise RuntimeError(f"图片文件{img_path}不存在")

    return img_path


def get_img_file(timestamp):
    img_path = check_img()

    return {
        "file": (f"{timestamp}.png", open(img_path, "rb"), "image/png")
    }
