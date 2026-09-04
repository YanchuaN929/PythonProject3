# AGENTS.md

## Scope

This file applies to the entire repository. It is the operational contract for coding agents and future maintainers working on the interface-filtering desktop application.

The project is a Windows/Tkinter application that reads seven families of engineering Excel workbooks, applies role-aware business rules, writes responses, assignments and FU completion dates back to Excel, and tracks lifecycle state in a shared SQLite Registry.

## Instruction priority and sources of truth

Follow explicit user instructions first. Within the repository, use these sources in descending order when information conflicts:

1. Current executable code and tests.
2. `version.json`, `config.json` and the selected department profile.
3. `core/main.py` file-discovery functions and `STREAM_FILE_SPECS` for workbook mappings.
4. `utils/role_table.py`, `services/account_service.py` and the selected `excel_bin/姓名角色表*.xlsx` for identity and role behaviour.
5. Documentation under `document/`.

Some documents describe historical states, measurements or future CIMS work. Do not restore old behaviour merely because a document is stale. Update affected documentation minimally when user-visible behaviour changes.

## Non-negotiable business invariants

- The actual Excel write is the primary business outcome. Registry state must reflect the Excel result, not replace it.
- If Excel is committed and Registry synchronization fails, enqueue or retain a Registry-only compensation. Never repeat the Excel write as Registry retry logic.
- Files 1-6 are completed by writing a response number through the existing column-mapping logic. File 7 is completed by writing the actual FU date.
- One response number may be intentionally used for multiple different interface IDs. Do not enforce global response-number uniqueness.
- Never silently overwrite a non-empty response number or FU actual date with a different value.
- Treat an identical existing value as idempotent success only after the row and interface identity are validated.
- A stored row number is not sufficient proof of identity. Validate the interface ID and use the existing unique relocation rules when rows move.
- Duplicate interface IDs must retain deterministic sequence handling. If a target cannot be uniquely determined, reject the write instead of guessing.
- Role filtering affects what a user sees. Registry ingestion must receive the unfiltered business rows unless the established Registry contract explicitly says otherwise.
- A designer's successful response or FU completion moves the item into the upper-level review path. It must disappear from the designer's pending list without disappearing from authorized reviewers.
- A confirmed and archived cycle must not be recreated by an unchanged source workbook. A genuine new cycle must still be able to reset state under the existing time/content rules.
- Assignment, reassignment, confirmation, ignore and history behaviour must survive source-file row movement and application restart.
- File type numbering and tab order are stable: 1 internal-open, 2 internal-reply, 3 external-open, 4 external-reply, 5 3D handover, 6 correspondence, 7 FU.

## Architecture ownership

- `base.py`: application orchestration, refresh/processing lifecycle, role-aware aggregation, cache reuse and UI coordination. Keep it focused on orchestration; prefer extracting substantial new logic into the owning package.
- `core/main.py`: file discovery, selected-column reading, workbook schema resolution and business filtering for file types 1-7.
- `core/main2.py`: result export and summary generation.
- `ui/window.py`: tabs, tables, row actions, batch entry points and visible status rendering.
- `ui/input_handler.py`: single response/FU write validation and execution.
- `ui/batch_response_dialog.py`: batch selection and preview UI.
- `services/batch_response.py`: grouped, all-or-nothing-per-workbook batch writes.
- `services/distribution.py`: assignment UI, workbook assignment writes and Registry handoff.
- `services/account_service.py`: account/password operations against role workbooks.
- `services/file_manager.py`: file discovery metadata and processing-result caches.
- `registry/`: Registry schema, lifecycle state, events, recovery, migration and query APIs.
- `write_tasks/`: asynchronous write queue, executors, local persistence, shared task log and Registry compensation.
- `utils/excel_io.py`: shared workbook locks, atomic saves, targeted OOXML patches and read-back helpers.
- `utils/dept_config.py` and `utils/role_table.py`: department profiles and role-table selection.
- `update/`: version comparison, update discovery and the standalone updater.
- `tests/`: executable regression contract. Add a regression test for each fixed defect.

Avoid duplicating column maps or status-transition logic in a new module. Reuse the existing owner and update all call sites that depend on a shared rule.

## Supported environment

- Preserve Python 3.8.5 compatibility.
- Preserve Windows 7, Windows 10 and Windows 11 support.
- Do not introduce Python 3.9+ or 3.10+ syntax such as unguarded built-in generic annotations or `X | None` unions.
- Use APIs available in the pinned dependency versions in `requirements.txt`.
- Do not upgrade pandas, NumPy, openpyxl, Pillow, xlrd, pystray or PyInstaller without explicit compatibility testing and user approval.
- Treat Tkinter, Windows paths, UNC paths, Office lock files and legacy `.xls` support as production requirements.

## Workbook recognition and parsing

- File recognition belongs in the `find_all_target_files*` functions in `core/main.py`.
- Selected-column schemas and header aliases belong in `STREAM_FILE_SPECS` and the related schema-resolution helpers.
- Keep file types 1-7 semantically aligned with the UI, distribution mappings, Registry and tests.
- Do not introduce artificial ranges such as `A1:A1` that exclude real business rows or columns.
- Prefer reading physical cells and required columns over materializing entire worksheets.
- Preserve Excel row numbers and openpyxl-compatible scalar types, especially dates, booleans, formulas with cached values, shared strings and inline strings.
- FU workbooks can contain a small number of real cells while declaring more than one million rows. Preserve the sparse OOXML reader and its compatibility fallback.
- If a producer-specific workbook cannot be parsed safely by the optimized path, fall back to the proven compatible reader rather than returning altered business data.
- Do not invent file-5 workbook assumptions when no representative sample is available. Format-changing work needs a real sample or explicit acceptance criteria.

## Excel write safety

All Excel changes are high risk.

- Use the existing `SharedWorkbookLock` and Excel lock-owner checks. Do not add a second unrelated locking mechanism.
- Validate file existence, writability, row identity, current target value and target column before saving.
- For OOXML, prefer targeted worksheet-cell XML updates through `utils/excel_io.py`.
- Build the replacement in the target directory, verify the temporary workbook, atomically replace the original and reopen it for final value verification.
- Preserve all non-target archive members. Do not reconstruct unrelated sheets, styles, formulas, drawings or metadata through a full openpyxl save when a targeted patch is supported.
- Keep full-workbook openpyxl saving only as an explicit compatibility fallback for templates that cannot preserve correct cell type/style through the targeted path.
- Preserve `.xls` handling through the existing legacy helpers.
- Batch operations are all-or-nothing per workbook during precheck and write. Different workbook groups may run in parallel.
- Never write directly to a production workbook during tests. Copy a representative workbook to a temporary directory first.
- Verification failure after an atomic replace must be represented as potentially committed. Callers must not blindly retry the Excel mutation.

## Registry and task lifecycle safety

- Registry writes must use `registry/hooks.py` and `registry/service.py`; do not write ad hoc SQL from UI code.
- Reuse the existing business ID and task ID helpers in `registry/util.py`.
- Preserve active, completed, confirmed and archived lifecycle semantics.
- Preserve state inheritance by business ID when source filename or row number changes.
- Preserve confirmed-archive suppression and new-cycle reset rules.
- Preserve ignored state, ignore metadata, responsible person, assignment metadata and response number during batch optimizations.
- Batch prefetch is a performance optimization only. Legacy-schema or query failure must fall back to the established row lookup without changing results.
- Duplicate business IDs within one batch must observe earlier mutations in that same transaction; do not use a stale prefetched value for those duplicates.
- SQLite/UNC failures must not be hidden as successful synchronization.
- A Registry-only compensation task may call Registry hooks only. It must never invoke the Excel response, FU or assignment writer.
- Do not delete, recreate, migrate or bulk-edit a real Registry database without an explicit user request and a verified backup/rollback path.

## Roles, accounts and assignments

- Role tables under `excel_bin/` are business data, not test fixtures.
- The selected department profile determines which role table is authoritative.
- Account passwords are stored in the third column of the applicable role workbook. Never print, expose, hash-report or include password values in fixtures or documentation.
- Account switching must continue to support keyboard text entry and password verification.
- Password changes must preserve workbook structure and use the shared lock/atomic-save path.
- Interface-engineer roles can be project-qualified, for example `2026接口工程师`; do not collapse distinct project permissions.
- Preserve administrator, institute-leader, room-director, interface-engineer and designer visibility differences.
- Assignment writes must validate the responsible-person column for the actual workbook schema. File 6 must not overwrite the host-office column when the responsible-person header is absent or moved.
- Registry assignment failure after Excel success must create Registry-only compensation.

## GUI and concurrency

- Tkinter widgets and Tk variables may be read or written only on the Tk main thread.
- Workbook parsing, public-drive I/O, Registry synchronization and recurring task-log queries belong in background workers.
- Worker results must be passed to the UI through the existing UI queue or Tk-side polling mechanism.
- Coalesce repeated refresh requests; do not launch overlapping public-drive queries every timer tick.
- Preserve the last successful task-list snapshot when a transient shared-drive refresh fails.
- After response, FU completion, confirmation or assignment, invalidate and redraw only affected file types unless a full refresh is required for correctness.
- Preserve preloaded tab data and render signatures so tab switching remains immediate after a processing run.
- Help or settings windows must not trigger main-table geometry changes or rebuild the primary layout.
- Do not trade correctness for responsiveness. If cached state can be stale after a write, invalidate it before display.

## Performance rules

- Measure before and after on the same files and report elapsed time, file counts and result equivalence.
- Optimized and compatibility paths must produce equal row identities, values and scalar types on representative samples.
- Reuse one-run result caches and Registry read snapshots; do not deserialize the same result cache twice in one processing cycle.
- Read the file-6 role table once per processing cycle, not once per workbook.
- Registry batch operations should prefetch in bounded chunks and retain a correctness fallback.
- Keep public-drive concurrency bounded. More worker threads are not automatically faster and can amplify lock contention.
- Add performance regression tests for optimizations that replace a previously slow path.

## Test commands

Use the repository virtual environment when available.

Full suite:

```powershell
.venv\Scripts\python.exe -m pytest -p no:cacheprovider --basetemp .pytest_run_all -q
```

Response and Excel-write changes:

```powershell
.venv\Scripts\python.exe -m pytest -p no:cacheprovider --basetemp .pytest_run_response tests/test_input_handler_response_task.py tests/test_response_write_safety.py tests/test_batch_response_flow.py -q
```

FU changes:

```powershell
.venv\Scripts\python.exe -m pytest -p no:cacheprovider --basetemp .pytest_run_fu tests/test_file7_fu_flow.py tests/test_performance_regressions.py -q
```

Registry and compensation changes:

```powershell
.venv\Scripts\python.exe -m pytest -p no:cacheprovider --basetemp .pytest_run_registry tests/test_registry_read_and_excel_safety.py tests/test_registry_path_consistency.py tests/test_registry_recovery.py tests/test_registry_crash_regression.py tests/test_registry_lock_retry.py tests/test_write_tasks_full_flow.py -q
```

Assignment and role changes:

```powershell
.venv\Scripts\python.exe -m pytest -p no:cacheprovider --basetemp .pytest_run_assignment tests/test_assignment_memory.py tests/test_assignment_project_2416.py tests/test_main_dept_filtering.py tests/test_role_table.py -q
```

Account changes:

```powershell
.venv\Scripts\python.exe -m pytest -p no:cacheprovider --basetemp .pytest_run_account tests/test_account_service.py tests/test_account_app_logic.py tests/test_account_entry_layout.py -q
```

GUI/help/render changes:

```powershell
.venv\Scripts\python.exe -m pytest -p no:cacheprovider --basetemp .pytest_run_ui tests/test_help_viewer_regression.py tests/test_window_status_sorting.py tests/test_ui_registry_confirmation_regression.py tests/test_update_flow_optimization.py -q
```

Always run the focused tests first. Run the full suite before a release, commit requested by the user, or handoff of a high-risk business change. Do not weaken, skip or delete a failing regression test merely to make the suite pass.

Tests must use temporary workbooks and temporary Registry databases. Tests that require a configured external business folder may skip when it is absent; state that explicitly in the result.

## Documentation rules

- `README.md` is the concise human entry point.
- `AGENTS.md` contains agent-specific operational constraints.
- `document/4_使用说明.md` is the packaged user help source; keep its existing formatting when updating it.
- `document/1_程序框架.md`, `2_模块功能说明.md` and `3_技术专题.md` hold detailed architecture and implementation material.
- `document/5_工作流程.md`, `6_阶段1_CIMS-sql分析结果.md` and `7_待处理文件SQL对照表.md` include staged CIMS research and must not be presented as already deployed behaviour unless code confirms it.
- Avoid volatile line counts, benchmark promises, personal absolute paths and copied passwords in documentation.
- Use repository-relative links in Markdown.

## Version, build and release

- `version.json` is the single source of truth for the application version.
- Change the version only when the user explicitly requests a version update or release.
- Release versions must use `YYYY.MM.DD.N`, where the date is the actual local release/build date and `N` starts at 1.
- If the existing version date is not today, replace the date with today and set `N` to 1. If it is already today, increment only `N`.
- `verify_package.py --pre` and `--post` must reject a release whose version date is not the current local date.
- Do not hand-edit a second version string into README or source code.
- Run the full test suite and pre-build verification before packaging:

```powershell
.venv\Scripts\python.exe verify_package.py --pre
```

- Build with `build.bat` or the checked-in spec:

```powershell
.venv\Scripts\pyinstaller.exe excel_processor.spec --noconfirm --clean
```

- Run post-build verification:

```powershell
.venv\Scripts\python.exe verify_package.py --post
```

- Verify the packaged `version.json`, archive integrity and a short EXE startup smoke test.
- Release archives must include the exact version: `接口筛选_<version>.rar`.
- `build/`, `dist/`, caches, logs, local databases and write-task state are generated files and must not be committed.
- `update_log.txt` is a runtime updater log, not a release changelog.

## Git rules

- Preserve unrelated user changes in a dirty worktree.
- Inspect `git status`, `git diff --check` and the staged diff before committing.
- Do not commit, push, rewrite history, create tags or publish a release unless the user explicitly requests it.
- Use focused commit messages such as `fix:`, `feat:`, `perf:`, `test:`, `docs:` or `build:` followed by a concise Chinese description.
- Never use destructive reset/checkout commands to discard work.
- Do not add production spreadsheets, databases, credentials, caches, logs or generated packages to Git.
- If a push fails after the remote may have accepted data, verify branch tracking state before retrying.

## Definition of done

A change is complete only when all applicable items are true:

- The reported issue is reproduced or tied to concrete code/data evidence.
- The smallest coherent fix is implemented in the owning module.
- Excel, Registry and role-state ordering remains correct.
- A regression test covers the defect or changed invariant.
- Focused tests pass.
- The full suite passes for high-risk or release work.
- Real samples are compared read-only when workbook parsing changes.
- Temporary copies are used when workbook writing changes.
- Documentation is synchronized when user-visible behaviour or developer workflow changes.
- The diff contains no unrelated files, generated artifacts or secrets.
- Packaging and Git operations are performed only when requested and their results are reported accurately.
