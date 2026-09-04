"""Standalone PowerShell probe: isolation, physical rows, secrets and diagnostics."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import zipfile

import pytest


PROBE = Path(__file__).resolve().parents[1] / 'tools' / 'diagnose_fu.ps1'
POWERSHELL = shutil.which('powershell.exe')
pytestmark = pytest.mark.skipif(not POWERSHELL, reason='Windows PowerShell required')


def _book(path, body, strings=None, dimension='A1:A1', second_sheet=False):
    """Minimal OOXML fixture, deliberately not saved by an Excel library."""
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    sheets = '<sheet name="FU" sheetId="1" r:id="rId1"/>'
    if second_sheet:
        sheets += '<sheet name="Other" sheetId="2" r:id="rId2"/>'
    with zipfile.ZipFile(str(path), 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('xl/workbook.xml', '<workbook xmlns="{}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>{}</sheets></workbook>'.format(ns, sheets))
        z.writestr('xl/_rels/workbook.xml.rels', '<Relationships><Relationship Id="rId1" Target="/xl/worksheets/custom.xml"/><Relationship Id="rId2" Target="worksheets/other.xml"/><Relationship Id="rId3" Type="x/sharedStrings" Target="sharedStrings.xml"/></Relationships>')
        z.writestr('xl/worksheets/custom.xml', '<worksheet xmlns="{}"><dimension ref="{}"/><sheetData>{}</sheetData></worksheet>'.format(ns, dimension, body))
        if strings is not None:
            z.writestr('xl/sharedStrings.xml', '<sst xmlns="{}">{}</sst>'.format(ns, ''.join('<si><t>{}</t></si>'.format(s) for s in strings)))


def _inline(address, text):
    return '<c r="{}" t="inlineStr"><is><t>{}</t></is></c>'.format(address, text)


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope='module')
def probe_run(tmp_path_factory):
    root = tmp_path_factory.mktemp('FU 探针 中文 空格')
    app = root / 'app'
    runtime = app / '_internal'
    roles = runtime / 'excel_bin'
    roles.mkdir(parents=True)
    data = root / 'data'
    data.mkdir()
    profile = root / 'profile'
    profile.mkdir()
    private_marker = 'DO_NOT_EXPORT_PASSWORD_SENTINEL'
    (runtime / 'config.json').write_text(json.dumps({
        'folder_path_lock_enabled': False,
        'password': private_marker,
        'department_profile': '测试所',
        'department_profiles': {'测试所': {'role_table_file': 'excel_bin/role.xlsx'}},
    }, ensure_ascii=False), encoding='utf-8')
    (profile / 'config.json').write_text(json.dumps({'user_name': '测试用户', 'folder_path': str(data), 'password': private_marker}, ensure_ascii=False), encoding='utf-8')
    (profile / 'crash.log').write_text('FU render failed\nTclError: sample failure\npassword=' + private_marker + '\n', encoding='utf-8')
    (runtime / 'version.json').write_text('{"version":"2026.09.02.2"}', encoding='utf-8')
    # C references a nonexistent shared string. The probe MUST NOT resolve it.
    _book(roles / 'role.xlsx', '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c><c r="C1" t="s"><v>99999</v></c></row>', ['测试用户', '管理员', private_marker])
    body = '<row r="1">' + _inline('B1', '内部编码') + _inline('E1', 'FU计划') + '</row>'
    body += '<row r="2"><c r="B2" t="s"><v>0</v></c>' + _inline('C2', 'TITLE_SENTINEL_𠮷') + '<c r="E2"><v>46000</v></c>' + _inline('F2', '测试用户') + '</row>'
    body += '<row r="57">' + _inline('B57', 'CODE_SECRET') + '<c r="D57"><v>45000</v></c><c r="E57"><f>TODAY()</f></c></row>'
    _book(data / '1818项目标准表格.xlsx', body, ['CODE_SECRET'], second_sheet=True)
    _book(data / '2026项目标准表格.xlsx', '<row r="8">' + _inline('B8', 'HUGE_DIM_CODE') + '<c r="E8"><v>46000</v></c></row>', dimension='A1:XFD1048576')
    (data / '1916项目标准表格.xlsx').write_bytes(b'not-a-zip')
    (data / '1907项目标准表格.xls').write_bytes(b'legacy-probe-fixture')
    (data / '1818项目标准表格 (副本).xlsx').write_bytes(b'near match')
    (data / '~$2016项目标准表格.xlsx').write_bytes(b'lock owner')
    (data / '.registry').mkdir()
    db = data / '.registry' / 'registry.db'
    with sqlite3.connect(str(db)) as c:
        c.execute('CREATE TABLE tasks(file_type INTEGER, project_id TEXT, status TEXT, display_status TEXT, ignored INTEGER, confirmed_at TEXT, responsible_person TEXT)')
        c.executemany('INSERT INTO tasks VALUES(?,?,?,?,?,?,?)', [
            (7, '1818', 'open', '待设计人员完成', 0, None, '测试用户'),
            (7, '1818', 'archived', '已审查', 0, '2026-09-01', '测试用户'),
            (1, '2026', 'open', '请指派', 0, None, ''),
        ])
    native = Path(sys.base_prefix) / 'DLLs' / 'sqlite3.dll'
    if not native.is_file():
        pytest.skip('Packaged-compatible sqlite3.dll unavailable')
    shutil.copy2(str(native), str(runtime / 'sqlite3.dll'))
    originals = {p: _sha(p) for parent in (runtime, data, profile) for p in parent.rglob('*') if p.is_file()}
    env = os.environ.copy()
    env['TEMP'] = str(root)
    env['TMP'] = str(root)
    completed = subprocess.run([
        POWERSHELL, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(PROBE),
        '-ExeDir', str(app), '-DataFolder', str(data), '-ProfileDir', str(profile), '-TimeoutSeconds', '90',
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=110, env=env)
    outputs = list(app.glob('FU_Diagnostic_*'))
    assert len(outputs) == 1, (completed.stdout, completed.stderr)
    output = outputs[0]
    assert not (output / 'fatal.txt').exists(), (output / 'fatal.txt').read_text(encoding='utf-8-sig') if (output / 'fatal.txt').exists() else ''
    report = json.loads((output / 'report.json').read_text(encoding='utf-8-sig'))
    assert report['complete'], (report, completed.stdout, completed.stderr)
    return root, output, report, originals, private_marker


def test_probe_preserves_all_source_files_and_cleans_private_database(probe_run):
    root, output, report, originals, _ = probe_run
    assert all(_sha(p) == checksum for p, checksum in originals.items())
    assert not list(root.glob('FU_Probe_Private_*'))
    assert not list(output.rglob('*.db*'))
    assert report['registry']['source_stable_during_copy'] is True
    assert 'query_error' not in report['registry'], report['registry']


def test_probe_does_not_export_passwords_or_business_cell_contents(probe_run):
    _, output, report, _, sentinel = probe_run
    for file in output.iterdir():
        text = file.read_text(encoding='utf-8-sig')
        for secret in (sentinel, 'TITLE_SENTINEL', 'CODE_SECRET', 'HUGE_DIM_CODE'):
            assert secret not in text
    assert report['role']['current_roles'] == ['管理员']
    assert report['role']['account_matches'] == 1
    assert '[sensitive line omitted]' in str(report['logs'])


def test_probe_uses_real_cells_and_first_sheet_relationship(probe_run):
    _, _, report, _, _ = probe_run
    files = {Path(item['path']).name: item for item in report['fu_files']}
    first = files['1818项目标准表格.xlsx']
    assert first['declared_dimension'] == 'A1:A1'
    assert first['max_physical_row'] == 57
    assert first['rows_with_internal_code'] == 2
    assert first['rows_with_plan_and_blank_actual'] == 1
    assert first['duplicate_code_groups'] == 1
    assert first['formula_without_cached_value'] == 1
    assert first['xml_member'] == 'xl/worksheets/custom.xml'
    assert first['non_bmp_cells'] == ['C2']
    sparse = files['2026项目标准表格.xlsx']
    assert sparse['physical_rows'] == 1
    assert sparse['max_physical_row'] == 8
    assert sparse['rows_with_internal_code'] == 1
    assert report['fu_matched_count'] == 4
    assert '1818项目标准表格 (副本).xlsx' in report['fu_near_matches']


def test_probe_keeps_partial_results_for_bad_and_legacy_workbooks(probe_run):
    _, _, report, _, _ = probe_run
    files = {Path(item['path']).name: item for item in report['fu_files']}
    assert 'error' in files['1916项目标准表格.xlsx']
    assert 'Legacy XLS' in files['1907项目标准表格.xls']['error']
    assert report['registry']['fu_status_counts']


def test_probe_source_is_bom_encoded_and_uses_only_private_sqlite_copy():
    assert PROBE.read_bytes().startswith(b'\xef\xbb\xbf')
    text = PROBE.read_text(encoding='utf-8-sig')
    assert '[FuProbe]::Query($registryPath' not in text
    assert 'Set-ExecutionPolicy' not in text
    assert 'CreateNoWindow = $true' in text


def _run_variant(tmp_path, script_text=None, timeout=60):
    app = tmp_path / 'app'
    runtime = app / '_internal'
    runtime.mkdir(parents=True, exist_ok=True)
    data = tmp_path / 'data'
    data.mkdir(exist_ok=True)
    profile = tmp_path / 'profile'
    profile.mkdir(exist_ok=True)
    (profile / 'crash.log').write_text('TclError: retain even if helpers fail\n', encoding='utf-8')
    native = Path(sys.base_prefix) / 'DLLs' / 'sqlite3.dll'
    if not native.is_file():
        pytest.skip('sqlite3.dll unavailable')
    shutil.copy2(str(native), str(runtime / 'sqlite3.dll'))
    script = PROBE
    if script_text is not None:
        script = tmp_path / 'probe variant.ps1'
        script.write_text(script_text, encoding='utf-8-sig')
    env = os.environ.copy()
    env.update(TEMP=str(tmp_path), TMP=str(tmp_path))
    result = subprocess.run([
        POWERSHELL, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script),
        '-ExeDir', str(app), '-DataFolder', str(data), '-ProfileDir', str(profile),
        '-TimeoutSeconds', str(timeout),
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout + 20, env=env)
    outputs = list(app.glob('FU_Diagnostic_*'))
    assert len(outputs) == 1, (result.stdout, result.stderr)
    report = json.loads((outputs[0] / 'report.json').read_text(encoding='utf-8-sig'))
    return outputs[0], report


@pytest.mark.parametrize('mode', ['wal', 'journal'])
def test_registry_sidecar_safety(tmp_path, mode):
    data = tmp_path / 'data' / '.registry'
    data.mkdir(parents=True)
    db = data / 'registry.db'
    conn = sqlite3.connect(str(db))
    try:
        if mode == 'wal':
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA wal_autocheckpoint=0')
        conn.execute('CREATE TABLE tasks(file_type INTEGER, status TEXT)')
        conn.execute("INSERT INTO tasks VALUES (7, 'open')")
        conn.commit()
        if mode == 'journal':
            (data / 'registry.db-journal').write_bytes(b'journal present')
        before = {p: _sha(p) for p in data.iterdir()}
        output, report = _run_variant(tmp_path)
        assert report['complete']
        if mode == 'wal':
            assert 'query_error' not in report['registry'], report['registry']
            assert report['registry']['counts_by_file_type'] == [{'file_type': '7', 'count': '1'}]
        else:
            assert 'journal' in report['registry']['query_error']
        assert all(_sha(p) == value for p, value in before.items())
        assert not list(tmp_path.glob('FU_Probe_Private_*'))
        assert not list(output.rglob('*.db*'))
    finally:
        conn.close()


def test_helper_compilation_failure_still_collects_logs_and_environment(tmp_path):
    source = PROBE.read_text(encoding='utf-8-sig').replace('using System.Xml;', '#error simulated helper unavailable')
    _, report = _run_variant(tmp_path, source)
    assert report['complete']
    assert report['environment']['powershell']
    assert any('helpers unavailable' in s for s in report['warnings'])
    assert any('TclError' in str(log.get('tail', '')) for log in report['logs'])


def test_timeout_preserves_checkpoint_and_deletes_only_private_copy(tmp_path):
    source = PROBE.read_text(encoding='utf-8-sig').replace(
        "Save-Report '1/7 Environment and package'",
        "Save-Report '1/7 Environment and package'\n"
        "    [IO.File]::WriteAllText((Join-Path $PrivateDir 'registry.db'), 'private test copy')\n"
        "    Start-Sleep -Seconds 45",
    )
    output, report = _run_variant(tmp_path, source, timeout=15)
    assert not report['complete']
    assert (output / 'TIMEOUT.txt').exists()
    assert not list(tmp_path.glob('FU_Probe_Private_*'))


def test_single_file_beside_exe_uses_current_user_configuration(tmp_path):
    app = tmp_path / '部署目录'
    (app / '_internal').mkdir(parents=True)
    data = tmp_path / '业务目录'
    data.mkdir()
    profile = tmp_path / 'user' / '.excel_processor'
    profile.mkdir(parents=True)
    (app / '_internal' / 'config.json').write_text('{"folder_path_lock_enabled":false}', encoding='utf-8')
    (profile / 'config.json').write_text(json.dumps({'folder_path': str(data), 'user_name': '测试用户'}, ensure_ascii=False), encoding='utf-8')
    _book(data / '1818项目标准表格.xlsx', '<row r="2">' + _inline('B2', 'CODE') + '<c r="E2"><v>46000</v></c></row>')
    script = app / 'diagnose_fu.ps1'
    shutil.copy2(str(PROBE), str(script))
    env = os.environ.copy()
    env.update(USERPROFILE=str(profile.parent), TEMP=str(tmp_path), TMP=str(tmp_path))
    run = subprocess.run([
        POWERSHELL, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script),
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=40, env=env, cwd=str(tmp_path))
    reports = list(app.glob('FU_Diagnostic_*/report.json'))
    assert len(reports) == 1, (run.stdout, run.stderr)
    report = json.loads(reports[0].read_text(encoding='utf-8-sig'))
    assert report['complete']
    assert report['data_folder'] == str(data)
    assert report['fu_matched_count'] == 1
    assert report['fu_files'][0]['rows_with_internal_code'] == 1
