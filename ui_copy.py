from __future__ import annotations

import re
from typing import Iterable, List, Sequence


_ROLE_SUFFIX_RE = re.compile(r"\([^)]*\)$")


def normalize_interface_id(value: str) -> str:
    """
    标准化接口号：去除角色后缀，例如：
    - "S-XXX(...设计人员)" -> "S-XXX"
    """
    s = "" if value is None else str(value).strip()
    if not s:
        return ""
    return _ROLE_SUFFIX_RE.sub("", s).strip()


def format_tsv(headers: Sequence[str], rows: Iterable[Sequence[str]]) -> str:
    """
    将表格数据格式化为“制表符分隔 + 换行”文本，便于粘贴到Excel/聊天工具。
    """
    safe_headers = [str(h) for h in headers]
    out_lines: List[str] = []
    if safe_headers:
        out_lines.append("\t".join(safe_headers))
    for row in rows:
        out_lines.append("\t".join("" if v is None else str(v) for v in row))
    return "\n".join(out_lines).strip()


def copy_text(widget, text: str) -> bool:
    """
    复制文本到剪贴板（基于tk widget的clipboard接口）。
    """
    try:
        if not text:
            return False
        widget.clipboard_clear()
        widget.clipboard_append(text)
        try:
            widget.update_idletasks()
        except Exception:
            pass
        return True
    except Exception:
        return False


