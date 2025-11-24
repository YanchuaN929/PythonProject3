from pathlib import Path


def test_excel_processor_spec_contains_required_entries():
    spec_path = Path("excel_processor.spec")
    assert spec_path.exists(), "excel_processor.spec 不存在"

    text = spec_path.read_text(encoding="utf-8")

    required_snippets = [
        "('version.json', '.')",
        "'registry.hooks'",
        "'registry.config'",
        "'update.manager'",
        "'update.versioning'",
        "'update.updater_cli'",
        "update_analysis = Analysis",
        "update_exe = EXE",
    ]

    missing = [snippet for snippet in required_snippets if snippet not in text]
    assert not missing, f"spec 缺少以下打包内容: {missing}"

