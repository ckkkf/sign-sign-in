import os
import sys


def get_base_dir():
    # 打包后的 EXE
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)

    # 源码模式：paths.py 位于 openSource/core/，所以 dirname 两次回到 openSource 根目录
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))