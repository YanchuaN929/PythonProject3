#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Create a Windows 7 compatibility package from the current PyInstaller dist."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import zipfile
import stat
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME_SOURCE = Path(r"E:\program\PythonProject1\dist\ZHJG\_internal")
DEFAULT_VC_REDIST_CANDIDATES = [
    Path(r"C:\Autodesk\AutoCAD_2019_Simplified_Chinese_Win_64bit_dlm\3rdParty\x64\VCRedist\2017\vcredist_x64.exe"),
    Path(r"C:\NVIDIA\536.40\MSVCRT\vc_redist.x64.exe"),
]

RUNTIME_PATTERNS = [
    "ucrtbase.dll",
    "api-ms-win-crt-*.dll",
    "api-ms-win-core-*.dll",
    "VCRUNTIME140*.dll",
    "MSVCP140*.dll",
]


def read_version() -> str:
    with open(ROOT / "version.json", "r", encoding="utf-8") as file_obj:
        return json.load(file_obj)["version"]


def clean_copy(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def copy_runtime(runtime_source: Path, package_dir: Path) -> list[str]:
    if not runtime_source.exists():
        raise FileNotFoundError(f"runtime source not found: {runtime_source}")

    internal_dir = package_dir / "_internal"
    copied: list[str] = []
    for pattern in RUNTIME_PATTERNS:
        for source_file in runtime_source.glob(pattern):
            if source_file.is_file():
                target_file = internal_dir / source_file.name
                if target_file.exists():
                    target_file.chmod(target_file.stat().st_mode | stat.S_IWRITE)
                    target_file.unlink()
                shutil.copy2(source_file, target_file)
                copied.append(source_file.name)
    if "ucrtbase.dll" not in copied:
        raise FileNotFoundError(f"ucrtbase.dll not found in runtime source: {runtime_source}")
    return sorted(set(copied))


def copy_toolkit(toolkit_dir: Path, vc_redist: Path | None) -> Path:
    source_dir = ROOT / "tools" / "win7_runtime"
    target_dir = toolkit_dir / "Win7离线运行环境工具包"
    if target_dir.exists():
        shutil.rmtree(target_dir)
    shutil.copytree(source_dir, target_dir, ignore=shutil.ignore_patterns("redist"))

    redist_dir = target_dir / "redist"
    redist_dir.mkdir(parents=True, exist_ok=True)
    if vc_redist and vc_redist.exists():
        shutil.copy2(vc_redist, redist_dir / "vc_redist.x64.exe")
    return target_dir


def make_zip(source_dir: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in source_dir.rglob("*"):
            if file_path.is_file():
                archive.write(file_path, file_path.relative_to(source_dir))


def remove_stale_package_archives(dist_dir: Path, keep_paths: set[Path]) -> None:
    """Remove versioned application archives left by earlier builds."""
    keep_resolved = {path.resolve() for path in keep_paths}
    for archive_path in dist_dir.glob("接口筛选_*.zip"):
        if archive_path.resolve() not in keep_resolved:
            archive_path.unlink()


def find_vc_redist(explicit_path: str | None) -> Path | None:
    if explicit_path:
        path = Path(explicit_path)
        return path if path.exists() else None
    for candidate in DEFAULT_VC_REDIST_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def assert_win7_ucrt(package_dir: Path) -> None:
    ucrt_path = package_dir / "_internal" / "ucrtbase.dll"
    data = ucrt_path.read_bytes()
    if b"api-ms-win-core-sysinfo-l1-2-0.dll" in data:
        raise RuntimeError(
            f"{ucrt_path} still references api-ms-win-core-sysinfo-l1-2-0.dll"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-source", default=str(DEFAULT_RUNTIME_SOURCE))
    parser.add_argument("--vc-redist", default=None)
    args = parser.parse_args()

    version = read_version()
    dist_dir = ROOT / "dist"
    normal_package = dist_dir / "接口筛选"
    normal_zip = dist_dir / f"接口筛选_{version}.zip"
    compat_package = dist_dir / "接口筛选_win7_compat"
    compat_zip = dist_dir / f"接口筛选_{version}_win7_compat.zip"
    toolkit_zip = dist_dir / "Win7离线运行环境工具包.zip"

    remove_stale_package_archives(dist_dir, {normal_zip, compat_zip})
    make_zip(normal_package, normal_zip)
    clean_copy(normal_package, compat_package)
    copied_runtime = copy_runtime(Path(args.runtime_source), compat_package)
    assert_win7_ucrt(compat_package)

    vc_redist = find_vc_redist(args.vc_redist)
    toolkit_dir = copy_toolkit(dist_dir, vc_redist)
    shutil.copytree(toolkit_dir, compat_package / "Win7离线运行环境工具包")

    make_zip(compat_package, compat_zip)
    make_zip(toolkit_dir, toolkit_zip)

    print(f"compat_package={compat_package}")
    print(f"normal_zip={normal_zip}")
    print(f"compat_zip={compat_zip}")
    print(f"toolkit_zip={toolkit_zip}")
    print(f"runtime_source={Path(args.runtime_source)}")
    print(f"runtime_files={len(copied_runtime)}")
    print(f"vc_redist={vc_redist or '<not included>'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
