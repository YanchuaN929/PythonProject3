# -*- coding: utf-8 -*-

import datetime
import json

import verify_package


def _write_version(tmp_path, value):
    path = tmp_path / "version.json"
    path.write_text(json.dumps({"version": value}), encoding="utf-8")
    return str(path)


def test_release_version_accepts_today_and_positive_sequence(tmp_path):
    today = datetime.date(2026, 9, 4)
    path = _write_version(tmp_path, "2026.09.04.1")

    assert verify_package.check_release_version(path, today=today) is True


def test_release_version_rejects_stale_release_date(tmp_path):
    today = datetime.date(2026, 9, 4)
    path = _write_version(tmp_path, "2026.09.02.3")

    assert verify_package.check_release_version(path, today=today) is False


def test_release_version_rejects_invalid_format_or_zero_sequence(tmp_path):
    today = datetime.date(2026, 9, 4)

    for value in ("2026.9.4.1", "2026.09.04.0", "2026.02.30.1"):
        path = _write_version(tmp_path, value)
        assert verify_package.check_release_version(path, today=today) is False
