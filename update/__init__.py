# -*- coding: utf-8 -*-
"""
自动更新模块入口。

该包包含：
- versioning: 版本文件读取与比较
- manager: 供主程序调用的版本检测/更新触发逻辑
- updater_cli: update.exe 的脚本入口
"""

from .manager import UpdateManager, UpdateReason  # noqa: F401

