import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST_ROOT = ROOT / "dist" / "pyinstaller"
BUILD_ROOT = ROOT / "build" / "pyinstaller"
APP_NAME = "SignSignIn"
WORKFLOW_NAME = "PyInstaller Cross Build"
RESOURCE_SUBDIRS = [
    Path("config"),
    Path("cert"),
    Path("img"),
    Path("journals"),
    Path("logs"),
    Path("mitm") / "addons",
    Path("mitm") / "conf",
    Path("software"),
]


def data_separator():
    return ";" if platform.system() == "Windows" else ":"


def python_executable():
    candidates = []
    if platform.system() == "Windows":
        candidates.append(ROOT / ".venv" / "Scripts" / "python.exe")
    else:
        candidates.append(ROOT / ".venv" / "bin" / "python")
    candidates.append(Path(sys.executable))

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return sys.executable


def current_target():
    system = platform.system()
    if system == "Windows":
        return "windows"
    if system == "Darwin":
        return "macos"
    return system.lower()


def prepare_bundle_data(target: str):
    stage_root = BUILD_ROOT / target / "_bundle_data"
    if stage_root.exists():
        shutil.rmtree(stage_root)

    assets_stage = stage_root / "app" / "assets"
    assets_stage.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / "app" / "assets", assets_stage, dirs_exist_ok=True)

    resources_stage = stage_root / "resources"
    for relative_path in RESOURCE_SUBDIRS:
        source = ROOT / "resources" / relative_path
        destination = resources_stage / relative_path
        destination.mkdir(parents=True, exist_ok=True)
        if not source.exists():
            continue

        if source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

    return assets_stage, resources_stage


def build_local(target: str):
    sep = data_separator()
    dist_dir = DIST_ROOT / target
    work_dir = BUILD_ROOT / target
    spec_dir = BUILD_ROOT / "spec"
    assets_dir, resources_dir = prepare_bundle_data(target)
    dist_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    spec_dir.mkdir(parents=True, exist_ok=True)

    command = [
        python_executable(),
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onefile",
        "--name",
        APP_NAME,
        "--distpath",
        str(dist_dir),
        "--workpath",
        str(work_dir),
        "--specpath",
        str(spec_dir),
        "--paths",
        str(ROOT),
        "--collect-all",
        "mitmproxy",
        "--hidden-import",
        "app.mitm.embedded_runner",
        "--add-data",
        f"{assets_dir}{sep}app/assets",
        "--add-data",
        f"{resources_dir}{sep}resources",
        str(ROOT / "main.py"),
    ]

    print("[build] local target:", target)
    print("[build] command:", " ".join(command))
    subprocess.run(command, cwd=ROOT, check=True)


def ensure_clean_git():
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    dirty = [line for line in result.stdout.splitlines() if line.strip()]
    if dirty:
        raise RuntimeError("远程 macOS 打包要求工作区干净，请先提交或暂存改动后再运行。")


def run_gh(*args, capture_output=False):
    command = ["gh", *args]
    return subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        capture_output=capture_output,
        text=True,
    )


def trigger_macos_build(git_ref: str | None):
    if shutil.which("gh") is None:
        raise RuntimeError("未检测到 GitHub CLI(gh)，无法自动触发 macOS 打包。")

    ensure_clean_git()
    run_gh("auth", "status")

    ref = git_ref
    if not ref:
        ref = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    print(f"[build] trigger remote macOS build on ref: {ref}")
    run_gh("workflow", "run", WORKFLOW_NAME, "--ref", ref, "-f", f"git_ref={ref}")
    run_info = run_gh(
        "run",
        "list",
        "--workflow",
        WORKFLOW_NAME,
        "--branch",
        ref,
        "--limit",
        "1",
        "--json",
        "databaseId",
        capture_output=True,
    )
    runs = json.loads(run_info.stdout or "[]")
    if not runs:
        raise RuntimeError("已触发 macOS 工作流，但未查询到对应运行记录。")

    run_id = str(runs[0]["databaseId"])
    run_gh("run", "watch", run_id)
    download_dir = DIST_ROOT / "downloads"
    download_dir.mkdir(parents=True, exist_ok=True)
    run_gh("run", "download", run_id, "--name", f"pyinstaller-macos-{ref}", "--dir", str(download_dir))
    print(f"[build] macOS artifact downloaded to: {download_dir}")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Build SignSignIn with PyInstaller")
    parser.add_argument("--local-only", action="store_true", help="只构建当前系统的本地版本")
    parser.add_argument("--skip-local", action="store_true", help="跳过本地构建")
    parser.add_argument("--git-ref", help="远程 macOS 构建使用的 git ref")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    target = current_target()

    if target not in {"windows", "macos"} and not args.local_only:
        raise RuntimeError("仅支持在 Windows 或 macOS 上执行本地 PyInstaller 打包。")

    if not args.skip_local:
        build_local(target)

    if not args.local_only and target == "windows":
        trigger_macos_build(args.git_ref)
    elif not args.local_only and target == "macos":
        print("[build] 当前已在 macOS，本脚本未自动反向触发 Windows 远程构建。")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
