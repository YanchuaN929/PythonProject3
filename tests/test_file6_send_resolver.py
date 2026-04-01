#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Focused coverage for file6 SEND-side rule metadata."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from core.sql.file6_send_resolver import get_file6_send_type_rule
from scripts.db_tools.sql_explorer.file6_type_regression_report import build_report


def test_file6_rulebook_contains_validated_object_actor_augments():
    review_rule = get_file6_send_type_rule("审查意见单")
    assert review_rule.actor_strategy == "workflow_union_plus_object_fields"
    assert review_rule.object_actor_fields == {
        "DESIGNREVIEWOPNION": ("MODIFIED_BY_ID",),
        "FILETRANSMISSION": ("MODIFIED_BY_ID",),
    }
    assert review_rule.status_hint == "semantic_gap"

    telefax_rule = get_file6_send_type_rule("图文传真")
    assert telefax_rule.actor_strategy == "workflow_union_plus_object_fields"
    assert telefax_rule.object_actor_fields == {"TELEFAX": ("CREATED_BY_ID", "MODIFIED_BY_ID")}
    assert telefax_rule.status_hint == "semantic_gap"

    memo_rule = get_file6_send_type_rule("备忘录")
    assert memo_rule.actor_strategy == "workflow_union_plus_object_fields"
    assert memo_rule.object_actor_fields == {"MEMORANDUM": ("CREATED_BY_ID", "MODIFIED_BY_ID")}
    assert memo_rule.status_hint == "chain_and_semantics"

    transmission_rule = get_file6_send_type_rule("文件传递单")
    assert transmission_rule.actor_strategy == "workflow_union_plus_object_fields"
    assert transmission_rule.object_actor_fields == {"FILETRANSMISSION": ("MODIFIED_BY_ID",)}
    assert transmission_rule.status_hint == "chain_and_semantics"


def test_file6_unknown_type_uses_default_rule():
    rule = get_file6_send_type_rule("未知文函")
    assert rule.doc_type == "未知文函"
    assert rule.actor_strategy == "workflow_union"
    assert rule.object_actor_fields == {}
    assert rule.status_hint == "unclassified"


def test_file6_regression_report_embeds_rule_metadata():
    payload = {
        "workflow_metrics": {
            "by_type": {
                "图文传真": {
                    "row_count": 10,
                    "rows_with_workflow_hits": 10,
                    "X_all": {"total": 5, "hit": 2, "rate": 0.4},
                    "V_all": {"total": 5, "hit": 4, "rate": 0.8},
                    "W_all": {"total": 2, "hit": 1, "rate": 0.5},
                }
            }
        }
    }
    tmp_dir = Path("tmp") / f"test_file6_send_resolver_{uuid4().hex}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    input_path = tmp_dir / "file6_probe.json"
    input_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    report = build_report(input_path, include_closed=True)
    entry = report["all_types"]["图文传真"]

    assert entry["status"] == "semantic_gap"
    assert entry["next_step"] == "对象桥已通，优先拆责任人口径"
    assert entry["rule"]["actor_strategy"] == "workflow_union_plus_object_fields"
    assert entry["rule"]["object_actor_fields"] == {"TELEFAX": ["CREATED_BY_ID", "MODIFIED_BY_ID"]}
