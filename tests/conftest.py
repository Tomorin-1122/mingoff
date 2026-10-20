# -*- coding: utf-8 -*-
"""让 `pytest` 无需先 `pip install -e .` 也能找到 src/ 下的包。

临时目录 fixture 与父项目同源：DSH 沙箱拒绝在工作区内**新建目录**的嵌套写入，
pytest 内置 `tmp_path` 会在清理时 `iterdir()` 报 PermissionError。那是沙箱边界
不是代码 bug，**不要去修文件权限**。这里自己建目录、不扫描不清理。
"""
from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

#: 必须**预先存在**（见上文）：运行期新建的目录拿不到沙箱的嵌套写权限
_TMP_BASE = Path(__file__).resolve().parents[1] / ".test-tmp"


@pytest.fixture
def tmp_path(request: pytest.FixtureRequest) -> Path:
    """覆盖 pytest 内置 `tmp_path`：返回一个预先存在的测试目录。"""
    cached = getattr(request.node, "_mingoff_tmp", None)
    if cached is not None:
        return cached

    _TMP_BASE.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(request.node.nodeid.encode("utf-8")).hexdigest()[:12]
    base = _TMP_BASE / f"{os.getpid()}-{digest}"
    if base.exists():
        for child in base.iterdir():
            if child.is_dir():
                import shutil

                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)
    base.mkdir(parents=True, exist_ok=True)
    request.node._mingoff_tmp = base  # type: ignore[attr-defined]
    return base


@pytest.fixture(autouse=True)
def _disable_basetemp_symlink_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    """屏蔽 pytest 对 basetemp 的死链扫描（沙箱下必抛 PermissionError）。"""
    try:
        from _pytest import pathlib as _pytest_pathlib
    except ImportError:  # pragma: no cover
        return
    monkeypatch.setattr(
        _pytest_pathlib, "cleanup_dead_symlinks", lambda *a, **k: None, raising=False
    )
