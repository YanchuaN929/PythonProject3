#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# 接口处理程序
# 鏀寔Win7+绯荤粺锛屽叿澶嘒UI鐣岄潰銆佸悗鍙拌繍琛屻€佺郴缁熸墭鐩樼瓑鍔熻兘


import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import tkinter.scrolledtext as scrolledtext
import os
import sys
import json
import datetime
import traceback
import faulthandler
import atexit
import threading
import time
import platform
import winreg
import re
from pathlib import Path
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from openpyxl import load_workbook
from typing import List, Dict, Any, Optional, Tuple

# 瀵煎叆绐楀彛绠＄悊鍣?
from ui.window import WindowManager
from write_tasks import get_write_task_manager, get_pending_cache

try:
    from core.sql.file1_db_source import (
        build_file1_export_dataframe,
        build_file1_virtual_source,
        get_file1_db_connection_status,
        is_file1_db_source_list,
        is_file1_db_virtual_source,
    )
    from core.sql.file2_db_source import (
        build_file2_virtual_source,
        get_file2_debug_snapshots,
        prime_file2_db_cache,
    )
    from core.sql.file3_db_source import (
        build_file3_virtual_source,
        get_file3_debug_snapshots,
        prime_file3_db_cache,
    )
    from core.sql.file4_db_source import (
        build_file4_virtual_source,
        get_file4_debug_snapshots,
        prime_file4_db_cache,
    )
    from core.sql.provider import get_sql_backend_status
except Exception:
    def build_file1_virtual_source(project_id: str) -> str:
        return f"db://file1/{project_id}"

    def is_file1_db_virtual_source(path: str) -> bool:
        return str(path or "").startswith("db://file1/")

    def is_file1_db_source_list(source_files):
        return bool(source_files) and all(is_file1_db_virtual_source(item) for item in source_files)

    def get_file1_db_connection_status():
        return {"connected": "0", "message": "鏈繛鎺ワ細鏁版嵁搴撻┍鍔ㄦ湭灏辩华", "connector": ""}

    def build_file1_export_dataframe(df):
        return df

    def build_file2_virtual_source(project_id: str) -> str:
        return f"db://file2/{project_id}"

    def get_file2_debug_snapshots():
        return {}

    def prime_file2_db_cache(project_ids, current_datetime):
        return {}

    def build_file3_virtual_source(project_id: str) -> str:
        return f"db://file3/{project_id}"

    def get_file3_debug_snapshots():
        return {}

    def prime_file3_db_cache(project_ids, current_datetime):
        return {}

    def build_file4_virtual_source(project_id: str) -> str:
        return f"db://file4/{project_id}"

    def get_file4_debug_snapshots():
        return {}

    def prime_file4_db_cache(project_ids, current_datetime):
        return {}

    def get_sql_backend_status():
        return {"mode": "unavailable", "connected": "0", "message": "SQL provider unavailable"}

try:
    from services.processing_diagnostics import write_processing_diagnostic_log
except Exception:
    def write_processing_diagnostic_log(_app, total_projects=None, error_message: str = ""):
        return ""

try:
    from utils.dept_config import (
        get_default_folder_path,
        get_director_role_mapping,
        get_director_roles,
        get_projects,
        get_role_export_days,
        get_role_table_file,
        get_time_window_roles,
        get_use_workdays_roles,
        get_watermark_text,
    )
except ImportError:
    # 后备：兼容极端打包异常
    def get_default_folder_path():
        return r"//10.102.2.7/文件服务器/建筑结构所/接口文件/各项目内外部接口手册"
    def get_director_role_mapping():
        return {"一室主任": "结构一室", "二室主任": "结构二室", "建筑总图室主任": "建筑总图室"}
    def get_director_roles():
        return ["一室主任", "二室主任", "建筑总图室主任"]
    def get_projects():
        return ["1818", "1907", "1915", "1916", "2016", "2026", "2306"]
    def get_role_table_file():
        return "excel_bin/姓名角色表.xlsx"
    def get_time_window_roles():
        return {"所领导", "一室主任", "二室主任", "建筑总图室主任"}
    def get_role_export_days():
        return {"一室主任": 7, "二室主任": 7, "建筑总图室主任": 7,
                "所领导": 2, "管理员": None, "设计人员": None}
    def get_use_workdays_roles():
        return ["所领导", "一室主任", "二室主任", "建筑总图室主任"]
    def get_watermark_text():
        return "建筑结构所"

FORCED_DEFAULT_FOLDER = get_default_folder_path()
DEV_OVERRIDE_PASSWORD = "0929"

_CRASH_LOG_FH = None


def _init_crash_logging():
    """doc"""
    # 浠庢簮鏂囦欢鏂囦欢鍚嶄腑瑙ｆ瀽鈥滄椂闂村悗缂€鈥濓紝鐢ㄤ簬鍚岄」鐩悓绫诲瀷鍙彇鏈€鏂版枃浠躲€?

    # 绾﹀畾锛堝凡鍦?main.py 鐨勫尮閰嶈鍒欎腑鍑虹幇锛夛細
    # - file1: 2016鎸夐」鐩鍑篒DI鎵嬪唽2025-08-01-17_55_52.xlsx锛堝惈鏃跺垎绉掞級鎴?2016鎸夐」鐩鍑篒DI鎵嬪唽2025-08-01.xlsx锛堜粎鏃ユ湡锛?
    # - file2: 鍐呴儴鎺ュ彛淇℃伅鍗曟姤琛?90720251203.xlsx锛圷YYYMMDD锛?
    # - file3: 澶栭儴鎺ュ彛ICM鎶ヨ〃190720251203.xlsx锛圷YYYMMDD锛?
    # - file4: 澶栭儴鎺ュ彛鍗曟姤琛?90720251203.xlsx锛圷YYYMMDD锛?

    # 杩斿洖锛?
    # - datetime.datetime锛堝彲姣旇緝锛?
    # - 瑙ｆ瀽澶辫触杩斿洖 None锛堜负瀹夊叏璧疯锛岃皟鐢ㄦ柟鍙€夋嫨鈥滀笉鍘婚噸鈥濓級

    try:
        if file_type == 1:
            # 鎸夐」鐩鍑篒DI鎵嬪唽 + YYYY-MM-DD[-HH_MM_SS]
            m = re.search(
                r"鎸夐」鐩鍑篒DI鎵嬪唽(?P<date>\d{4}-\d{2}-\d{2})(?:-(?P<h>\d{2})_(?P<m>\d{2})_(?P<s>\d{2}))?",
                filename
            )
            if not m:
                return None
            date_str = m.group("date")
            h = m.group("h")
            mi = m.group("m")
            s = m.group("s")
            if h and mi and s:
                return datetime.datetime.strptime(f"{date_str}-{h}_{mi}_{s}", "%Y-%m-%d-%H_%M_%S")
            return datetime.datetime.strptime(date_str, "%Y-%m-%d")

        if file_type == 2:
            m = re.search(r"内部接口信息单报表\d{4}(?P<date>\d{8})", filename)
        elif file_type == 3:
            m = re.search(r"外部接口ICM报表\d{4}(?P<date>\d{8})", filename)
        elif file_type == 4:
            m = re.search(r"外部接口单报表\d{4}(?P<date>\d{8})", filename)
        else:
            return None

        if not m:
            return None
        return datetime.datetime.strptime(m.group("date"), "%Y%m%d")
    except Exception:
        return None


def select_latest_source_files_per_project(
    # file_type: int,
    # file_list: List[Tuple[str, str]],
    file_type_name: str = ""
) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str, str]]]:

    # 瀵瑰悓涓€ file_type 鐨勫€欓€夋枃浠舵寜 project_id 鍘婚噸锛氭瘡涓」鐩彧淇濈暀鏂囦欢鍚嶆椂闂存渶鏂扮殑閭ｄ竴浠姐€?

    # 杩斿洖锛?
    # - filtered: [(file_path, project_id), ...]
    # - ignored:  [(file_path, project_id, reason), ...]

    # 瀹夊叏绛栫暐锛?
    # - 鑻ヤ换鎰忔枃浠舵棤娉曡В鏋愭椂闂达紙杩斿洖None锛夛紝鍒?**涓嶅仛鍘婚噸**锛堢洿鎺ヨ繑鍥炲師鍒楄〃锛夛紝閬垮厤璇垹銆?

    if not file_list:
        return [], []

    parsed: List[Tuple[str, datetime.datetime, str, str]] = []
    for file_path, project_id in file_list:
        base = os.path.basename(file_path)
        dt = _parse_datetime_from_source_filename(file_type, base)
        if dt is None:
            # 保守：不去重
            tip = f"[鏈€鏂版枃浠剁瓫閫塢 {file_type_name or f'file{file_type}'}: 鏃犳硶浠庢枃浠跺悕瑙ｆ瀽鏃堕棿锛岃烦杩囧幓閲嶏細{base}"
            print(tip)
            return file_list, []
        parsed.append((project_id, dt, base, file_path))

    # project_id -> (key, chosen_path)
    chosen: Dict[str, Tuple[Tuple[datetime.datetime, str], str]] = {}
    for project_id, dt, base, file_path in parsed:
        key = (dt, base)  # dt浼樺厛锛涘悓鏃ュ悓绉掑垯鎸夋枃浠跺悕瀛楃涓插仛娆＄骇姣旇緝锛堟洿鈥滄柊鈥濓級
        cur = chosen.get(project_id)
        if cur is None or key > cur[0]:
            chosen[project_id] = (key, file_path)

    filtered: List[Tuple[str, str]] = []
    ignored: List[Tuple[str, str, str]] = []
    for file_path, project_id in file_list:
        keep_path = chosen.get(project_id, (None, None))[1]
        if keep_path and file_path == keep_path:
            filtered.append((file_path, project_id))
        else:
            ignored.append((file_path, project_id, f"{file_type_name or f'file{file_type}'}旧版本(仅保留最新)"))

    if ignored:
        try:
            print(
                f"[最新文件筛选] {file_type_name or f'file{file_type}'}: "
                f"同项目多版本去重 {len(file_list)}→{len(filtered)}，忽略{len(ignored)}个旧文件"
            )
        except Exception:
            pass

    return filtered, ignored

# 导入任务指派模块
try:
    from services import distribution
except ImportError:
    print("璀﹀憡: 鏈壘鍒癲istribution妯″潡")
    distribution = None

# 导入Registry模块
try:
    from registry import hooks as registry_hooks
except ImportError:
    print("璀﹀憡: 鏈壘鍒皉egistry妯″潡")
    registry_hooks = None

# 导入数据库状态显示器
try:
    from services.db_status import (
        DatabaseStatusIndicator, 
        set_db_status_indicator,
        notify_syncing, 
        notify_connected, 
        notify_error
    )
except ImportError:
    print("璀﹀憡: 鏈壘鍒癲b_status妯″潡")
    DatabaseStatusIndicator = None
    set_db_status_indicator = None
    notify_syncing = notify_connected = notify_error = lambda *args, **kwargs: None

# 鑷姩鏇存柊妯″潡
try:
    from update import UpdateManager, UpdateReason
    from update.versioning import read_version as read_version_file, DEFAULT_VERSION
except ImportError:
    UpdateManager = None
    DEFAULT_VERSION = "0.0.0.0"

    def read_version_file(_path: str) -> str:
        return DEFAULT_VERSION

    class UpdateReason:  # type: ignore
        AUTO_FLOW = "auto_flow"
        START_PROCESSING = "start_processing"
        EXPORT_RESULTS = "export_results"

def get_resource_path(relative_path):
    """doc"""
    # 浼樺寲鐨凟xcel璇诲彇鏂规硶锛堟柟妗?锛歰penpyxl鍙妯″紡锛?
    
    # 参数:
        # file_path: Excel鏂囦欢璺緞
        # use_openpyxl_readonly: 鏄惁浣跨敤鍙妯″紡锛堥粯璁rue锛屾彁鍗?0-50%閫熷害锛?
    
    # 返回:
        # pandas.DataFrame
    
    # 性能提升:
        # - 速度: 提升30-50%
        # - 内存: 减少40-60%

    try:
        # AUTO-COMMENTED during syntax recovery: if file_path.endswith('.xlsx') and use_openpyxl_readonly:
            # 鏂规1: 浣跨敤openpyxl鍙妯″紡锛堥€熷害鎻愬崌30-50%锛?
            # AUTO-COMMENTED during syntax recovery: wb = load_workbook(file_path, read_only=True, data_only=True)
            # AUTO-COMMENTED during syntax recovery: ws = wb.active
            
            # 蹇€熻鍙栦负DataFrame
            # AUTO-COMMENTED during syntax recovery: data = ws.values
            # AUTO-COMMENTED during syntax recovery: columns = next(data)  # 绗竴琛屼綔涓哄垪鍚?
            # AUTO-COMMENTED during syntax recovery: df = pd.DataFrame(data, columns=columns)
            # AUTO-COMMENTED during syntax recovery: wb.close()
            
            # AUTO-COMMENTED during syntax recovery: return df
        # AUTO-COMMENTED during syntax recovery: elif file_path.endswith('.xlsx'):
            # 鍥為€€鍒版爣鍑嗘柟娉曪紙濡傛灉绂佺敤鍙妯″紡锛?
            # AUTO-COMMENTED during syntax recovery: return pd.read_excel(file_path, sheet_name=0, engine='openpyxl')
        # AUTO-COMMENTED during syntax recovery: else:
            # .xls文件使用xlrd引擎
            # AUTO-COMMENTED during syntax recovery: return pd.read_excel(file_path, sheet_name=0, engine='xlrd')
    # AUTO-COMMENTED during syntax recovery: except Exception as e:
        # AUTO-COMMENTED during syntax recovery: print(f"浼樺寲璇诲彇澶辫触锛屽洖閫€鍒版爣鍑嗘柟娉? {e}")
        # 澶辫触鏃跺洖閫€鍒板師濮嬫柟娉?
        # AUTO-COMMENTED during syntax recovery: if file_path.endswith('.xlsx'):
            # AUTO-COMMENTED during syntax recovery: return pd.read_excel(file_path, sheet_name=0, engine='openpyxl')
        # AUTO-COMMENTED during syntax recovery: else:
            # AUTO-COMMENTED during syntax recovery: return pd.read_excel(file_path, sheet_name=0, engine='xlrd')


def concurrent_read_excel_files(file_paths, max_workers=4):
    """doc"""
    def read_single_file(file_info):
        """doc"""
        # 鍒ゆ柇褰撳墠鎿嶄綔鏄惁搴旇鏄剧ず寮圭獥
        # 閫昏緫锛氭墜鍔ㄦ搷浣滄椂鏄剧ず寮圭獥锛岃嚜鍔ㄨ繍琛屼笖闈炴墜鍔ㄦ搷浣滄椂涓嶆樉绀?

        # 濡傛灉鏍囪涓烘墜鍔ㄦ搷浣滐紝鍒欐樉绀哄脊绐楋紙鍗充娇绋嬪簭鏄互auto妯″紡鍚姩鐨勶級
        if self._manual_operation:
            return True
        # 如果不是auto模式，则显示弹窗
        if not self.auto_mode:
            return True
        # 鍚﹀垯锛坅uto妯″紡涓旈潪鎵嬪姩鎿嶄綔锛夛紝涓嶆樉绀哄脊绐?
        return False

    # ------------------------------------------------------------------
    # 鑷姩鏇存柊鐩稿叧杈呭姪鏂规硶
    # ------------------------------------------------------------------
    def _detect_app_root(self) -> str:
        if getattr(sys, 'frozen', False):
            return os.path.dirname(sys.executable)
        return os.path.dirname(os.path.abspath(__file__))

    def _create_update_manager(self):
        if not UpdateManager:
            return None
        try:
            main_exec = os.path.basename(sys.executable) if getattr(sys, 'frozen', False) else ""
            return UpdateManager(
                app_root=self.app_root,
                main_executable=main_exec,
                log_fn=self._log_update_message,
            )
        except Exception as e:
            print(f"[Update] 鍒濆鍖栧け璐? {e}")
            return None

    def _log_update_message(self, message: str):
        print(f"[Update] {message}")
        try:
            from core import Monitor
            Monitor.log_info(message)
        except Exception:
            pass

    def _log_exit_reason(self, reason: str):
        try:
            user_config_dir = os.path.expanduser("~/.excel_processor")
            os.makedirs(user_config_dir, exist_ok=True)
            log_path = os.path.join(user_config_dir, "exit_reason.log")
            ts = datetime.datetime.now().isoformat()
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"{ts} {reason}\n")
        except Exception:
            pass

    def _schedule_exit_for_update(self):
        if getattr(self, "_update_shutdown_scheduled", False):
            return
        self._update_shutdown_scheduled = True
        self._log_update_message("宸茶Е鍙戣嚜鍔ㄦ洿鏂帮紝绋嬪簭鍗冲皢閫€鍑轰互瀹屾垚鏇存柊")

        def _perform_shutdown():
            try:
                root = getattr(self, 'root', None)
                if root:
                    try:
                        root.quit()
                    except Exception:
                        pass
                    try:
                        root.destroy()
                    except Exception:
                        pass
            # finally:
                self._log_exit_reason("update_exit")
                os._exit(0)

        # AUTO-COMMENTED during syntax recovery: try:
            # AUTO-COMMENTED during syntax recovery: self.root.after(500, _perform_shutdown)
        # AUTO-COMMENTED during syntax recovery: except Exception:
            # AUTO-COMMENTED during syntax recovery: def _delayed_exit():
                time.sleep(0.5)
                _perform_shutdown()

            # AUTO-COMMENTED during syntax recovery: threading.Thread(target=_delayed_exit, daemon=True).start()

    # AUTO-COMMENTED during syntax recovery: def _schedule_resume_action(self):
        # AUTO-COMMENTED during syntax recovery: if not getattr(self, 'resume_action', ''):
            # AUTO-COMMENTED during syntax recovery: return
        # AUTO-COMMENTED during syntax recovery: try:
            # AUTO-COMMENTED during syntax recovery: self.root.after(800, self._handle_resume_action)
        # AUTO-COMMENTED during syntax recovery: except Exception:
            # AUTO-COMMENTED during syntax recovery: pass

    # AUTO-COMMENTED during syntax recovery: def _handle_resume_action(self):
        # AUTO-COMMENTED during syntax recovery: action = getattr(self, 'resume_action', '') or ''
        # AUTO-COMMENTED during syntax recovery: if not action:
            # AUTO-COMMENTED during syntax recovery: return
        # auto妯″紡鏈韩浼氳嚜鍔ㄦ墽琛岋紝涓嶉渶瑕侀澶栬Е鍙?
        # AUTO-COMMENTED during syntax recovery: if action == UpdateReason.AUTO_FLOW and getattr(self, 'auto_mode', False):
            # AUTO-COMMENTED during syntax recovery: self.resume_action = ""
            # AUTO-COMMENTED during syntax recovery: return

        # AUTO-COMMENTED during syntax recovery: self.resume_action = ""

        # AUTO-COMMENTED during syntax recovery: if action == UpdateReason.START_PROCESSING:
            # AUTO-COMMENTED during syntax recovery: self._manual_operation = True
            # AUTO-COMMENTED during syntax recovery: self.start_processing()
        # AUTO-COMMENTED during syntax recovery: elif action == UpdateReason.EXPORT_RESULTS:
            # AUTO-COMMENTED during syntax recovery: return
        # AUTO-COMMENTED during syntax recovery: elif action == UpdateReason.AUTO_FLOW:
            # AUTO-COMMENTED during syntax recovery: self._run_auto_flow()

    # AUTO-COMMENTED during syntax recovery: def _ensure_up_to_date(self, reason: str, resume_action: Optional[str] = None) -> bool:
        # AUTO-COMMENTED during syntax recovery: """doc"""
        # 绋嬪簭鍚姩鍚庤嚜鍔ㄦ娴嬫洿鏂帮紙鍚庡彴绾跨▼鎵ц缃戠粶/IO锛岄伩鍏嶉樆濉濽I锛夈€?
        # 鏇存柊閫昏緫涓嶅彉锛氫粛閫氳繃 UpdateManager 鍒ゆ柇鐗堟湰骞跺惎鍔?update.exe銆?

        # AUTO-COMMENTED during syntax recovery: if getattr(self, "_startup_update_check_scheduled", False):
            # AUTO-COMMENTED during syntax recovery: return
        # AUTO-COMMENTED during syntax recovery: self._startup_update_check_scheduled = True

        # 娴嬭瘯鐜/鏄惧紡璺宠繃锛氶伩鍏峱ytest杩愯鏃惰Е鍙戝閮ㄨ矾寰勬鏌ユ垨閫€鍑?
        # AUTO-COMMENTED during syntax recovery: if getattr(self, "_skip_auto_startup_bootstrap", False):
            # AUTO-COMMENTED during syntax recovery: return

        # AUTO-COMMENTED during syntax recovery: def _kickoff():
            # AUTO-COMMENTED during syntax recovery: try:
                threading.Thread(
                    target=self._startup_update_check_worker,
                    daemon=True,
                    name="StartupUpdateCheck",
                ).start()
            except Exception:
                pass

        try:
            # 璁╀富绐楀彛鍏堝畬鎴愪竴娆℃覆鏌擄紝鍐嶅惎鍔ㄥ悗鍙版鏌?
            self.root.after(200, _kickoff)
        except Exception:
            _kickoff()

    def _startup_update_check_worker(self) -> None:
        """doc"""
        # 鑾峰彇鐢ㄦ埛鍕鹃€夌殑椤圭洰鍙峰垪琛?
        # 杩斿洖: 鍕鹃€夌殑椤圭洰鍙峰垪琛紝濡?['1818', '1907', ...]

        return [pid for pid, var in self.project_vars.items() if var.get()]

    def _is_file1_db_mode_enabled(self) -> bool:
        """doc"""
        # 鏍规嵁椤圭洰鍙风瓫閫夋枃浠跺垪琛?
        
        # 参数:
            # AUTO-COMMENTED during syntax recovery: file_list: 鏂囦欢鍒楄〃 [(鏂囦欢璺緞, 椤圭洰鍙?, ...]
            # enabled_projects: 鐢ㄦ埛鍕鹃€夌殑椤圭洰鍙峰垪琛?
            # file_type_name: 文件类型名称（用于日志）
        
        # 返回:
            # AUTO-COMMENTED during syntax recovery: (filtered_files, ignored_files): 
                # - filtered_files: 绛涢€夊悗鐨勬枃浠跺垪琛?
                # - ignored_files: 琚拷鐣ョ殑鏂囦欢鍒楄〃 [(鏂囦欢璺緞, 椤圭洰鍙? 鏂囦欢绫诲瀷), ...]

        if not file_list:
            return [], []
        
        filtered = []
        ignored = []
        
        for file_path, project_id in file_list:
            if project_id in enabled_projects:
                filtered.append((file_path, project_id))
            else:
                ignored.append((file_path, project_id, file_type_name))
                # AUTO-COMMENTED during syntax recovery: print(f"椤圭洰鍙风瓫閫? 蹇界暐椤圭洰{project_id}鐨剓file_type_name} - {os.path.basename(file_path)}")
        
        return filtered, ignored
    
    def _on_manual_start_processing(self):
        """doc"""
        # Step4锛氬鐞嗗畬鎴愬悗鐨勭粺涓€娓叉煋鍏ュ彛
        # - 鍐呴儴浼氶€夋嫨 active_tab锛屼絾鎶戝埗 <<NotebookTabChanged>> 鐨勪簩娆℃覆鏌?
        # - 鏈€缁堝彧娓叉煋涓€娆″綋鍓嶉€変腑 tab

        try:
            # AUTO-COMMENTED during syntax recovery: self._suppress_tab_change_render = True
            # AUTO-COMMENTED during syntax recovery: try:
                # ttk.Notebook.select 鏀寔浼?index
                # AUTO-COMMENTED during syntax recovery: self.notebook.select(active_tab)
            # finally:
                # AUTO-COMMENTED during syntax recovery: self._suppress_tab_change_render = False
        # AUTO-COMMENTED during syntax recovery: except Exception:
            # 鏃?Notebook/闈?GUI 鐜锛堟祴璇曪級涓嬬洿鎺ュ拷鐣?
            # AUTO-COMMENTED during syntax recovery: self._suppress_tab_change_render = False

        # 涓诲姩娓叉煋涓€娆″綋鍓?tab
        try:
            self.on_tab_changed(None)
        except Exception:
            pass

    def load_file_to_viewer(self, file_path, viewer, tab_name):
        """doc"""
        # 鍦╲iewer涓樉绀篍xcel鏁版嵁锛屼娇鐢ㄥ師濮婨xcel琛屽彿锛堝鐞嗙粨鏋?鏄剧ず鍏ㄩ儴鏁版嵁锛?
        
        # 参数:
            # source_files: 婧愭枃浠惰矾寰勫垪琛紙鐢ㄤ簬鍕鹃€夊姛鑳斤級锛屽彲閫?

        # 如果没有提供source_files，尝试从当前处理的文件中获取
        if source_files is None:
            source_files = self._get_source_files_for_tab(tab_name)
        
        # 銆愬叧閿慨澶嶃€戝湪鏄剧ず鍓嶈繃婊ゅ凡瀹屾垚/宸茬‘璁ょ殑浠诲姟
        if source_files and len(source_files) > 0:
            # 鏍规嵁tab_name纭畾file_type
            file_type_map = {
                "鍐呴儴闇€鎵撳紑鎺ュ彛": 1,
                "鍐呴儴闇€鍥炲鎺ュ彛": 2,
                "澶栭儴闇€鎵撳紑鎺ュ彛": 3,
                "澶栭儴闇€鍥炲鎺ュ彛": 4,
                "三维提资接口": 5,
                "收发文函": 6
            }
            file_type = file_type_map.get(tab_name)
            is_file1_db_tab = (
                file_type == 1
                and self._is_file1_db_mode_enabled()
                and is_file1_db_source_list(source_files)
            )
            
            # 銆愪慨澶嶃€戣幏鍙栭」鐩彿鍒版簮鏂囦欢鐨勬槧灏勶紙鏀寔澶氶」鐩級
            project_source_map = self._get_project_source_file_map(tab_name)
            
            if file_type and (project_source_map or source_files):
                if not is_file1_db_tab:
                    # 璋冪敤杩囨护鍑芥暟锛屼紶鍏ラ」鐩彿鍒版簮鏂囦欢鐨勬槧灏?
                    original_count = len(df)
                    df = self._exclude_pending_confirmation_rows(df, source_files[0], file_type, None, project_source_map)
                    filtered_count = original_count - len(df)
                    
                    if filtered_count > 0:
                        # AUTO-COMMENTED during syntax recovery: print(f"[鏄剧ず杩囨护] {tab_name}: 宸茶繃婊filtered_count}琛屽凡瀹屾垚/宸茬‘璁や换鍔★紝鍓╀綑{len(df)}琛?)
                        
                        # 更新original_row_numbers以匹配过滤后的df
                        if "鍘熷琛屽彿" in df.columns:
                            original_row_numbers = list(df["鍘熷琛屽彿"])
        
        # 銆愭柊澧炪€戣幏鍙栧綋鍓嶇敤鎴风殑瑙掕壊鍒楄〃
        user_roles = getattr(self, 'user_roles', [])
        if not user_roles:
            # 鍏煎锛氬鏋滄病鏈塽ser_roles锛屽皾璇曚粠user_role鑾峰彇
            user_role = getattr(self, 'user_role', '').strip()
            if user_role:
                user_roles = [user_role]
        
        # 浣跨敤WindowManager鐨刣isplay_excel_data鏂规硶锛屾樉绀哄叏閮ㄦ暟鎹?
        self.window_manager.display_excel_data(
            viewer=viewer,
            df=df,
            tab_name=tab_name,
            show_all=True,  # 澶勭悊瀹屾垚鍚庢樉绀哄叏閮ㄦ暟鎹?
            original_row_numbers=original_row_numbers,
            source_files=source_files,
            file_manager=self.file_manager,
            current_user_roles=user_roles  # 銆愭柊澧炪€戜紶閫掔敤鎴疯鑹插垪琛?
        )
        print(f"{tab_name}澶勭悊缁撴灉宸叉樉绀猴細{len(df)} 琛岋紙鍏ㄩ儴鏁版嵁锛屾敮鎸佹粴鍔級")

    def _exclude_completed_rows(self, df, source_file):
        """doc"""
        try:
            # AUTO-COMMENTED during syntax recovery: if df is None or df.empty:
                # AUTO-COMMENTED during syntax recovery: return df
            
            # 妫€鏌ユ槸鍚︽湁"鍘熷琛屽彿"鍒?
            # AUTO-COMMENTED during syntax recovery: if "鍘熷琛屽彿" not in df.columns:
                # AUTO-COMMENTED during syntax recovery: print("璀﹀憡锛欴ataFrame涓病鏈?鍘熷琛屽彿'鍒楋紝鏃犳硶鎺掗櫎宸插畬鎴愯")
                # AUTO-COMMENTED during syntax recovery: return df
            
            # 銆愪慨澶嶃€戣幏鍙栧凡瀹屾垚鐨勮鍙烽泦鍚堬紝浼犲叆鐢ㄦ埛濮撳悕
            # AUTO-COMMENTED during syntax recovery: user_name = getattr(self, 'user_name', '').strip()
            # AUTO-COMMENTED during syntax recovery: completed_rows = self.file_manager.get_completed_rows(source_file, user_name)
            
            # AUTO-COMMENTED during syntax recovery: if not completed_rows:
                # 没有已完成的行，直接返回
                # AUTO-COMMENTED during syntax recovery: return df
            
            # 杩囨护鎺夊凡瀹屾垚鐨勮
            # AUTO-COMMENTED during syntax recovery: original_count = len(df)
            # AUTO-COMMENTED during syntax recovery: df_filtered = df[~df['鍘熷琛屽彿'].isin(completed_rows)].copy()
            # AUTO-COMMENTED during syntax recovery: filtered_count = original_count - len(df_filtered)
            
            # AUTO-COMMENTED during syntax recovery: if filtered_count > 0:
                # AUTO-COMMENTED during syntax recovery: print(f"瀵煎嚭鏃舵帓闄や簡{filtered_count}琛屽凡瀹屾垚鐨勬暟鎹紙鏂囦欢锛歿source_file}锛?)
            
            # AUTO-COMMENTED during syntax recovery: return df_filtered
            
        # AUTO-COMMENTED during syntax recovery: except Exception as e:
            # AUTO-COMMENTED during syntax recovery: print(f"鎺掗櫎宸插畬鎴愯鏃跺嚭閿? {e}")
            # AUTO-COMMENTED during syntax recovery: import traceback
            # AUTO-COMMENTED during syntax recovery: traceback.print_exc()
            # AUTO-COMMENTED during syntax recovery: return df  # 鍑洪敊鏃惰繑鍥炲師濮嬫暟鎹紝纭繚瀵煎嚭涓嶅彈褰卞搷
    
    def _exclude_pending_confirmation_rows(self, df, source_file, file_type, project_id, project_source_map=None):
        """doc"""
        try:
            # AUTO-COMMENTED during syntax recovery: if df is None or df.empty:
                # AUTO-COMMENTED during syntax recovery: return df
            
            # 妫€鏌ュ繀瑕佸垪
            # AUTO-COMMENTED during syntax recovery: if "鍘熷琛屽彿" not in df.columns:
                # AUTO-COMMENTED during syntax recovery: print("[Registry] 璀﹀憡锛欴ataFrame涓病鏈?鍘熷琛屽彿'鍒楋紝鏃犳硶杩囨护寰呯‘璁よ")
                # AUTO-COMMENTED during syntax recovery: return df
            
            # 銆怰egistry銆戞煡璇㈡墍鏈夊緟纭鐨勪换鍔?
            # AUTO-COMMENTED during syntax recovery: from registry import hooks as registry_hooks
            # AUTO-COMMENTED during syntax recovery: from registry.util import extract_interface_id, extract_project_id, make_task_id
            
            # 銆愪紭鍖栥€戝噺灏戞棩蹇楄緭鍑猴紝鍙湪璋冭瘯妯″紡涓嬫樉绀鸿缁嗕俊鎭?
            # AUTO-COMMENTED during syntax recovery: _debug_export = False  # 璁句负True鍙惎鐢ㄨ缁嗚皟璇曟棩蹇?
            
            # 如果没有提供映射，使用默认的source_file
            # AUTO-COMMENTED during syntax recovery: if project_source_map is None:
                # AUTO-COMMENTED during syntax recovery: project_source_map = {}
            
            # 鏋勯€爐ask_keys
            # AUTO-COMMENTED during syntax recovery: task_keys = []
            # AUTO-COMMENTED during syntax recovery: df_index_map = {}  # task_id -> df_index映射
            # AUTO-COMMENTED during syntax recovery: for idx in range(len(df)):
                # AUTO-COMMENTED during syntax recovery: try:
                    # AUTO-COMMENTED during syntax recovery: row_data = df.iloc[idx]
                    # AUTO-COMMENTED during syntax recovery: interface_id = extract_interface_id(row_data, file_type)
                    # AUTO-COMMENTED during syntax recovery: proj_id = extract_project_id(row_data, file_type) or project_id
                    # AUTO-COMMENTED during syntax recovery: row_index = row_data.get("鍘熷琛屽彿", idx + 2)
                    
                    # 銆愪慨澶嶃€戞牴鎹」鐩彿鑾峰彇瀵瑰簲鐨勬簮鏂囦欢锛屾敮鎸佸椤圭洰
                    # AUTO-COMMENTED during syntax recovery: row_source_file = project_source_map.get(str(proj_id), source_file) if proj_id else source_file
                    
                    # AUTO-COMMENTED during syntax recovery: if interface_id and proj_id:
                        # AUTO-COMMENTED during syntax recovery: task_key = {
                            # AUTO-COMMENTED during syntax recovery: 'file_type': file_type,
                            # AUTO-COMMENTED during syntax recovery: 'project_id': proj_id,
                            # AUTO-COMMENTED during syntax recovery: 'interface_id': interface_id,
                            # AUTO-COMMENTED during syntax recovery: 'source_file': row_source_file,  # 使用对应项目的源文件
                            # AUTO-COMMENTED during syntax recovery: 'row_index': row_index
                        # AUTO-COMMENTED during syntax recovery: }
                        # AUTO-COMMENTED during syntax recovery: task_keys.append(task_key)
                        
                        # 记录映射关系
                        # AUTO-COMMENTED during syntax recovery: tid = make_task_id(
                            # AUTO-COMMENTED during syntax recovery: file_type, proj_id, interface_id,
                            # AUTO-COMMENTED during syntax recovery: row_source_file, row_index  # 使用对应项目的源文件
                        # AUTO-COMMENTED during syntax recovery: )
                        # AUTO-COMMENTED during syntax recovery: df_index_map[tid] = idx
                # AUTO-COMMENTED during syntax recovery: except Exception:
                    # AUTO-COMMENTED during syntax recovery: continue
            
            # AUTO-COMMENTED during syntax recovery: if not task_keys:
                # 銆愪慨澶嶃€戝嵆浣挎病鏈塕egistry浠诲姟锛屼篃瑕佸簲鐢ㄨ秴鏈熻繃婊?
                # AUTO-COMMENTED during syntax recovery: return self._apply_overdue_filter(df, file_type)
            
            # 鎵归噺鏌ヨ鐘舵€?
            # AUTO-COMMENTED during syntax recovery: status_map = registry_hooks.get_display_status(task_keys)

            # 銆愬叧閿厹搴曘€戝鏋淩egistry鏄柊搴?璺緞鍙樺寲/鏈垵濮嬪寲瀵艰嚧鏌ヤ笉鍒颁换浣曚换鍔★紝
            # 涓嶈兘鎶婃墍鏈夎褰撲綔鈥滄棤鐘舵€?=宸插拷鐣?宸插綊妗?鈥濈洿鎺ヨ繃婊ゆ帀锛屽惁鍒欎細鍑虹幇鈥滅粨鏋滃叏鍙?鈥濈殑鐏鹃毦鎬т綋楠屻€?
            # 杩欑鎯呭喌涓嬶紝闄嶇骇涓猴細璺宠繃 Registry 杩囨护锛屼粎淇濈暀瓒呮湡杩囨护銆?
            # AUTO-COMMENTED during syntax recovery: if not status_map:
                # AUTO-COMMENTED during syntax recovery: try:
                    # AUTO-COMMENTED during syntax recovery: print(f"[Registry] 璀﹀憡锛氭枃浠秢file_type} status_map涓虹┖锛岃烦杩嘡egistry杩囨护锛堝彲鑳芥槸鏂板簱/璺緞鍙樺寲/鏈垵濮嬪寲/鏈疆鏈啓鍏ワ級")
                # AUTO-COMMENTED during syntax recovery: except Exception:
                    # AUTO-COMMENTED during syntax recovery: pass
                # AUTO-COMMENTED during syntax recovery: return self._apply_overdue_filter(df, file_type)
            
            # 銆愪慨澶嶃€戞牴鎹敤鎴疯鑹插喅瀹氳繃婊ら€昏緫
            # AUTO-COMMENTED during syntax recovery: user_roles = getattr(self, 'user_roles', [])
            # AUTO-COMMENTED during syntax recovery: if not user_roles:
                # AUTO-COMMENTED during syntax recovery: user_role = getattr(self, 'user_role', '').strip()
                # AUTO-COMMENTED during syntax recovery: if user_role:
                    # AUTO-COMMENTED during syntax recovery: user_roles = [user_role]
            
            # 鍒ゆ柇鏄惁涓鸿璁′汉鍛?
            # AUTO-COMMENTED during syntax recovery: is_designer = '璁捐浜哄憳' in user_roles
            # AUTO-COMMENTED during syntax recovery: is_superior = any(keyword in ' '.join(user_roles) for keyword in ['鎵€棰嗗', '瀹や富浠?, '鎺ュ彛宸ョ▼甯?])
            
            # AUTO-COMMENTED during syntax recovery: exclude_indices = []
            
            # 銆愭柊澧炪€戝厛杩囨护鎵€鏈変笉鍦╯tatus_map涓殑浠诲姟锛堝凡蹇界暐/宸插綊妗ｏ級
            # AUTO-COMMENTED during syntax recovery: not_in_map_count = 0
            # AUTO-COMMENTED during syntax recovery: for tid in df_index_map.keys():
                # AUTO-COMMENTED during syntax recovery: if tid not in status_map:
                    # AUTO-COMMENTED during syntax recovery: exclude_indices.append(df_index_map[tid])
                    # AUTO-COMMENTED during syntax recovery: not_in_map_count += 1
            
            # AUTO-COMMENTED during syntax recovery: status_filter_count = 0
            # AUTO-COMMENTED during syntax recovery: if is_designer and not is_superior:
                # 璁捐浜哄憳锛氳繃婊ゆ帀"寰呭鏌?鍜?寰呮寚娲句汉瀹℃煡"鐨勪换鍔★紝浠ュ強宸茬‘璁ょ殑浠诲姟
                # AUTO-COMMENTED during syntax recovery: for tid, status_text in status_map.items():
                    # AUTO-COMMENTED during syntax recovery: if tid not in df_index_map:
                        # AUTO-COMMENTED during syntax recovery: continue
                    # 鍘婚櫎emoji鍜屽欢鏈熷墠缂€
                    # AUTO-COMMENTED during syntax recovery: clean_status = status_text.replace('鈴?, '').replace('馃搶', '').replace('鉂?, '').replace('锛堝凡寤舵湡锛?, '').strip()
                    # AUTO-COMMENTED during syntax recovery: if clean_status in ['寰呭鏌?, '寰呮寚娲句汉瀹℃煡', '寰呬笂绾х‘璁?, '寰呮寚娲句汉纭', '宸插鏌?]:
                        # AUTO-COMMENTED during syntax recovery: if df_index_map[tid] not in exclude_indices:
                            # AUTO-COMMENTED during syntax recovery: exclude_indices.append(df_index_map[tid])
                            # AUTO-COMMENTED during syntax recovery: status_filter_count += 1
                    # AUTO-COMMENTED during syntax recovery: elif not status_text:
                        # AUTO-COMMENTED during syntax recovery: if df_index_map[tid] not in exclude_indices:
                            # AUTO-COMMENTED during syntax recovery: exclude_indices.append(df_index_map[tid])
                            # AUTO-COMMENTED during syntax recovery: status_filter_count += 1
            # AUTO-COMMENTED during syntax recovery: else:
                # 涓婄骇瑙掕壊锛氳繃婊ゅ凡纭鐨勪换鍔″拰绌虹姸鎬佷换鍔?
                # AUTO-COMMENTED during syntax recovery: for tid, status_text in status_map.items():
                    # AUTO-COMMENTED during syntax recovery: if tid not in df_index_map:
                        # AUTO-COMMENTED during syntax recovery: continue
                    # AUTO-COMMENTED during syntax recovery: clean_status = status_text.replace('鈴?, '').replace('馃搶', '').replace('鉂?, '').replace('锛堝凡寤舵湡锛?, '').strip()
                    # AUTO-COMMENTED during syntax recovery: if clean_status == '宸插鏌? or not status_text:
                        # AUTO-COMMENTED during syntax recovery: if df_index_map[tid] not in exclude_indices:
                            # AUTO-COMMENTED during syntax recovery: exclude_indices.append(df_index_map[tid])
                            # AUTO-COMMENTED during syntax recovery: status_filter_count += 1
            
            # AUTO-COMMENTED during syntax recovery: if not exclude_indices:
                # AUTO-COMMENTED during syntax recovery: df_filtered = df
            # AUTO-COMMENTED during syntax recovery: else:
                # 杩囨护鎺夋寚瀹氱殑琛?
                # AUTO-COMMENTED during syntax recovery: original_count = len(df)
                # AUTO-COMMENTED during syntax recovery: df_filtered = df.drop(df.index[exclude_indices]).reset_index(drop=True)
                # AUTO-COMMENTED during syntax recovery: filtered_count = len(exclude_indices)
                
                # 銆愪紭鍖栥€戠畝娲佺殑姹囨€昏緭鍑?
                # AUTO-COMMENTED during syntax recovery: if filtered_count > 0:
                    # AUTO-COMMENTED during syntax recovery: role_desc = "璁捐浜哄憳" if (is_designer and not is_superior) else "涓婄骇"
                    # AUTO-COMMENTED during syntax recovery: print(f"[Registry杩囨护] 鏂囦欢{file_type}: {original_count}鈫抺len(df_filtered)}琛?"
                          # AUTO-COMMENTED during syntax recovery: f"(鎺掗櫎{not_in_map_count}涓棤鐘舵€?{status_filter_count}涓獅role_desc}杩囨护)")
            
            # 銆愭柊澧炪€戣嚜鍔ㄩ殣钘忚秴鏈熶换鍔¤繃婊?
            # AUTO-COMMENTED during syntax recovery: df_filtered = self._apply_overdue_filter(df_filtered, file_type)
            
            # AUTO-COMMENTED during syntax recovery: return df_filtered
            
        # AUTO-COMMENTED during syntax recovery: except Exception as e:
            # AUTO-COMMENTED during syntax recovery: print(f"[Registry] 鎺掗櫎寰呯‘璁よ鏃跺嚭閿欙紙涓嶅奖鍝嶄富娴佺▼锛? {e}")
            # 銆愪慨澶嶃€戝嚭閿欐椂涔熻灏濊瘯搴旂敤瓒呮湡杩囨护
            # AUTO-COMMENTED during syntax recovery: return self._apply_overdue_filter(df, file_type)
    
    def _apply_overdue_filter(self, df, file_type):
        """doc"""
        try:
            # 妫€鏌ユ槸鍚﹀惎鐢ㄨ嚜鍔ㄩ殣钘?
            # AUTO-COMMENTED during syntax recovery: if not self.config.get("auto_hide_overdue_enabled", True):
                # AUTO-COMMENTED during syntax recovery: return df
            
            # AUTO-COMMENTED during syntax recovery: if df is None or df.empty:
                # AUTO-COMMENTED during syntax recovery: return df
            
            # 妫€鏌ユ槸鍚︽湁鎺ュ彛鏃堕棿鍒?
            # AUTO-COMMENTED during syntax recovery: if "接口时间" not in df.columns:
                # AUTO-COMMENTED during syntax recovery: return df
            
            # 鑾峰彇闃堝€煎ぉ鏁?
            # AUTO-COMMENTED during syntax recovery: threshold_days = self.config.get("auto_hide_overdue_days", 30)
            # AUTO-COMMENTED during syntax recovery: if threshold_days <= 0:
                # AUTO-COMMENTED during syntax recovery: return df
            
            # AUTO-COMMENTED during syntax recovery: from utils.date_utils import parse_mmdd_to_date, get_workday_difference
            # AUTO-COMMENTED during syntax recovery: from datetime import date
            
            # AUTO-COMMENTED during syntax recovery: today = date.today()
            # AUTO-COMMENTED during syntax recovery: exclude_indices = []
            
            # AUTO-COMMENTED during syntax recovery: for idx in range(len(df)):
                # AUTO-COMMENTED during syntax recovery: try:
                    # AUTO-COMMENTED during syntax recovery: interface_time = df.iloc[idx].get("接口时间", "")
                    # AUTO-COMMENTED during syntax recovery: if not interface_time or str(interface_time).strip() in ['', '-', 'nan', 'None', '鏈煡']:
                        # AUTO-COMMENTED during syntax recovery: continue
                    
                    # 解析日期
                    # AUTO-COMMENTED during syntax recovery: due_date = parse_mmdd_to_date(str(interface_time).strip(), today)
                    # AUTO-COMMENTED during syntax recovery: if due_date is None:
                        # AUTO-COMMENTED during syntax recovery: continue
                    
                    # 计算工作日差
                    # AUTO-COMMENTED during syntax recovery: workday_diff = get_workday_difference(due_date, today)
                    
                    # 濡傛灉瓒呮湡宸ヤ綔鏃ヨ秴杩囬槇鍊硷紝鏍囪涓烘帓闄?
                    # AUTO-COMMENTED during syntax recovery: if workday_diff < 0 and abs(workday_diff) > threshold_days:
                        # AUTO-COMMENTED during syntax recovery: exclude_indices.append(idx)
                        
                # AUTO-COMMENTED during syntax recovery: except Exception:
                    # AUTO-COMMENTED during syntax recovery: continue
            
            # AUTO-COMMENTED during syntax recovery: if not exclude_indices:
                # AUTO-COMMENTED during syntax recovery: return df
            
            # 杩囨护鎺夎秴鏈熶换鍔?
            # AUTO-COMMENTED during syntax recovery: original_count = len(df)
            # AUTO-COMMENTED during syntax recovery: df_filtered = df.drop(df.index[exclude_indices]).reset_index(drop=True)
            
            # AUTO-COMMENTED during syntax recovery: print(f"[瓒呮湡杩囨护] 鏂囦欢{file_type}: 闅愯棌{len(exclude_indices)}涓秴鏈?{threshold_days}宸ヤ綔鏃ョ殑浠诲姟 "
                  # AUTO-COMMENTED during syntax recovery: f"({original_count}鈫抺len(df_filtered)}琛?")
            
            # AUTO-COMMENTED during syntax recovery: return df_filtered
            
        # AUTO-COMMENTED during syntax recovery: except Exception as e:
            # AUTO-COMMENTED during syntax recovery: print(f"[瓒呮湡杩囨护] 杩囨护鏃跺嚭閿欙紙涓嶅奖鍝嶄富娴佺▼锛? {e}")
            # AUTO-COMMENTED during syntax recovery: return df
    
    def _get_source_files_for_tab(self, tab_name):
        """doc"""
        try:
            # 鏍规嵁tab鍚嶇О鏄犲皠鍒板搴旂殑target_files灞炴€?
            # AUTO-COMMENTED during syntax recovery: tab_file_mapping = {
                # AUTO-COMMENTED during syntax recovery: "鍐呴儴闇€鎵撳紑鎺ュ彛": "target_files1",
                # AUTO-COMMENTED during syntax recovery: "鍐呴儴闇€鍥炲鎺ュ彛": "target_files2",
                # AUTO-COMMENTED during syntax recovery: "澶栭儴闇€鎵撳紑鎺ュ彛": "target_files3",
                # AUTO-COMMENTED during syntax recovery: "澶栭儴闇€鍥炲鎺ュ彛": "target_files4",
                # AUTO-COMMENTED during syntax recovery: "三维提资接口": "target_files5",
                # AUTO-COMMENTED during syntax recovery: "收发文函": "target_files6"
            # AUTO-COMMENTED during syntax recovery: }
            
            # AUTO-COMMENTED during syntax recovery: attr_name = tab_file_mapping.get(tab_name)
            # AUTO-COMMENTED during syntax recovery: if not attr_name:
                # AUTO-COMMENTED during syntax recovery: return []
            
            # AUTO-COMMENTED during syntax recovery: target_files = getattr(self, attr_name, None)
            # AUTO-COMMENTED during syntax recovery: if not target_files:
                # AUTO-COMMENTED during syntax recovery: return []
            
            # target_files格式: [(file_path, project_id), ...]
            # 鎻愬彇鎵€鏈夋枃浠惰矾寰?
            # AUTO-COMMENTED during syntax recovery: file_paths = [f[0] for f in target_files if isinstance(f, tuple) and len(f) >= 1]
            # AUTO-COMMENTED during syntax recovery: return file_paths
            
        # AUTO-COMMENTED during syntax recovery: except Exception as e:
            # AUTO-COMMENTED during syntax recovery: print(f"鑾峰彇婧愭枃浠跺垪琛ㄥけ璐? {e}")
            # AUTO-COMMENTED during syntax recovery: return []

    def _get_project_source_file_map(self, tab_name):
        """Return {project_id: source_file} for the current tab."""
        try:
            tab_file_mapping = {
                "内部接口文件1": "target_files1",
                "内部接口文件2": "target_files2",
                "外部接口文件3": "target_files3",
                "外部接口文件4": "target_files4",
                "三维提资接口": "target_files5",
                "收发文函": "target_files6",
            }
            attr_name = tab_file_mapping.get(tab_name)
            if not attr_name:
                return {}
            target_files = getattr(self, attr_name, None) or []
            project_file_map = {}
            for item in target_files:
                if isinstance(item, tuple) and len(item) >= 2:
                    file_path, project_id = item[0], item[1]
                    project_file_map[str(project_id)] = file_path
            return project_file_map
        except Exception:
            return {}

    def calculate_column_widths(self, df, columns):
        """Calculate basic Treeview column widths."""
        try:
            widths = {}
            for col in columns or []:
                header_width = len(str(col)) * 14 + 24
                sample_width = header_width
                if df is not None and hasattr(df, 'columns') and col in df.columns:
                    sample_values = df[col].head(50).tolist()
                    for value in sample_values:
                        sample_width = max(sample_width, len(str(value)) * 9 + 24)
                widths[col] = min(max(sample_width, 80), 420)
            return widths
        except Exception:
            return {col: 120 for col in (columns or [])}

    def _refresh_views_with_pending_cache(self):
        try:
            if self.has_processed_results1 and self.processing_results is not None:
                self.display_results(self.processing_results, show_popup=False)
            if self.has_processed_results2 and self.processing_results2 is not None:
                self.display_results2(self.processing_results2, show_popup=False)
            if self.has_processed_results3 and self.processing_results3 is not None:
                self.display_results3(self.processing_results3, show_popup=False)
            if self.has_processed_results4 and self.processing_results4 is not None:
                self.display_results4(self.processing_results4, show_popup=False)
            if self.has_processed_results5 and self.processing_results5 is not None:
                self.display_results5(self.processing_results5, show_popup=False)
            if self.has_processed_results6 and self.processing_results6 is not None:
                self.display_results6(self.processing_results6, show_popup=False)
        except Exception as e:
            print(f"[PendingCache] 刷新视图失败: {e}")

    def _block_if_pending_write_tasks(self):
        manager = getattr(self, "write_task_manager", None)
        if manager is None:
            return False

        if not manager.has_pending_tasks():
            self._pending_write_waiting = False
            return False

        if getattr(self, 'auto_mode', False) and not self._manual_operation:
            if not self._pending_write_waiting:
                print("[鍐欏叆闃熷垪] 妫€娴嬪埌寰呮墽琛屼换鍔★紝鑷姩妯″紡灏嗙瓑寰?20 绉掑悗閲嶈瘯")
            self._pending_write_waiting = True
            try:
                self.root.after(20000, self._retry_start_processing_after_pending)
            except Exception:
                pass
        else:
            try:
                pass
            except Exception:
                pass
            self._manual_operation = False
        return True

    def _retry_start_processing_after_pending(self):
        self._pending_write_waiting = False
        self.start_processing()

    def _handle_response_submitted(self, file_path: str, row_index: int, file_type: int):
        """doc"""
        # 瑙ｆ瀽鎺ュ彛宸ョ▼甯堣鑹诧紝鎻愬彇椤圭洰鍙?
        # 渚嬪锛?2016鎺ュ彛宸ョ▼甯? -> "2016"
        # 杩斿洖锛氶」鐩彿瀛楃涓诧紝濡傛灉涓嶆槸鎺ュ彛宸ョ▼甯堣鑹插垯杩斿洖None

        import re
        # 鍏煎鏇村鐪熷疄鍐欐硶锛氬彲鑳藉寘鍚┖鏍?鎷彿璇存槑/澶氳鑹叉嫾鎺ョ瓑
        # 鍙鑳芥壘鍒扳€?浣嶉」鐩彿 + 鎺ュ彛宸ョ▼甯堚€濆嵆鍙瘑鍒?
        s = (role or "").strip()
        # AUTO-COMMENTED during syntax recovery: match = re.search(r'(\d{4})\s*鎺ュ彛宸ョ▼甯?, s)
        if match:
            return match.group(1)
        return None
    
    def _filter_by_single_role(self, df: pd.DataFrame, role: str, project_id: str = None) -> pd.DataFrame:
        """doc"""
        try:
            user_name = getattr(self, 'user_name', '').strip()
            if not role or not user_name:
                return df.iloc[0:0]  # 返回空DataFrame
            
            safe_df = df.copy()
            
            # 1. 鎺ュ彛宸ョ▼甯堬細鎸夐」鐩彿绛涢€夋墍鏈夋暟鎹?
            engineer_project = self._parse_interface_engineer_role(role)
            if engineer_project:
                # 濡傛灉褰撳墠鏁版嵁鐨勯」鐩彿涓庢帴鍙ｅ伐绋嬪笀璐熻矗鐨勯」鐩彿鍖归厤锛屽垯杩斿洖鍏ㄩ儴鏁版嵁
                if project_id == engineer_project:
                    return safe_df
                else:
                    return safe_df.iloc[0:0]  # 项目号不匹配，返回空
            
            # 2. 璁捐浜哄憳锛氳矗浠讳汉 == 濮撳悕
            if role == '璁捐浜哄憳':
                # AUTO-COMMENTED during syntax recovery: if '璐ｄ换浜? in safe_df.columns:
                    # AUTO-COMMENTED during syntax recovery: return safe_df[safe_df['璐ｄ换浜?].astype(str).str.strip() == user_name]
                return safe_df
            
            # 3-5. 瀹や富浠伙細绉戝杩囨护 + 鏃堕棿绐楀彛杩囨护锛堜笌瀵煎嚭缁熶竴锛?
            director_roles = get_director_role_mapping()
            
            if role in director_roles:
                target_dept = director_roles[role]
                
                # 绗竴姝ワ細绉戝杩囨护
                # 浼樺厛妫€鏌?涓诲姙瀹?鍒楋紙鐢ㄤ簬鏂囦欢6锛?
                # AUTO-COMMENTED during syntax recovery: if '涓诲姙瀹? in safe_df.columns:
                    # AUTO-COMMENTED during syntax recovery: mask = safe_df['涓诲姙瀹?].astype(str).str.contains(target_dept, na=False, regex=False)
                    filtered = safe_df[mask]
                    if not filtered.empty:
                        safe_df = filtered
                    elif '绉戝' in safe_df.columns:
                        safe_df = safe_df[safe_df['绉戝'].isin([target_dept, '璇峰涓讳换纭'])]
                elif '绉戝' in safe_df.columns:
                    safe_df = safe_df[safe_df['绉戝'].isin([target_dept, '璇峰涓讳换纭'])]
                
                if safe_df.empty:
                    return safe_df
                
                # 绗簩姝ワ細鏃堕棿绐楀彛杩囨护锛堜笌瀵煎嚭缁熶竴锛屼娇鐢╮ole_export_days閰嶇疆锛?
                # 浠巆onfig璇诲彇澶╂暟闄愬埗锛屽欢鏈熶换鍔″缁堜繚鐣?
                role_days_map = self.config.get("role_export_days", {})
                max_workdays = role_days_map.get(role, 7)  # 榛樿7涓伐浣滄棩
                
                if max_workdays is None:
                    # None琛ㄧず鏃犻檺鍒?
                    return safe_df
                
                if '接口时间' not in safe_df.columns:
                    return safe_df
                
                from datetime import date
                from utils.date_utils import get_workday_difference, parse_mmdd_to_date
                
                today = date.today()
                kept_idx = []
                
                for idx, time_val in safe_df["接口时间"].items():
                    if pd.isna(time_val) or str(time_val).strip() in ['', '-']:
                        continue
                    
                    try:
                        due_date = parse_mmdd_to_date(str(time_val).strip(), today)
                        if due_date is None:
                            continue
                        
                        workday_diff = get_workday_difference(due_date, today)
                        
                        # 保留条件（与导出统一）：
                        # 1. 已延期（workday_diff < 0）：全部保留
                        # 2. 鏈潵N涓伐浣滄棩鍐咃紙workday_diff <= max_workdays锛夛細淇濈暀
                        if workday_diff <= max_workdays:
                            kept_idx.append(idx)
                    except Exception:
                        continue
                
                if not kept_idx:
                    return safe_df.iloc[0:0]
                
                return safe_df.loc[kept_idx]
            
            # 6. 鎵€棰嗗锛氫笉鍖哄垎绉戝锛屼絾闇€搴旂敤鏃堕棿绐楀彛杩囨护锛堜笌瀵煎嚭缁熶竴锛?
            #    鏃堕棿绐楀彛瀹氫箟锛氭墍鏈夊凡寤舵湡鏁版嵁 + 鏈潵N涓伐浣滄棩鍐呭埌鏈熺殑鏁版嵁
            if role == '鎵€棰嗗':
                if '接口时间' not in safe_df.columns:
                    return safe_df
                
                # 浠巖ole_export_days璇诲彇澶╂暟闄愬埗锛堜笌瀵煎嚭缁熶竴锛?
                role_days_map = self.config.get("role_export_days", {})
                max_workdays = role_days_map.get('鎵€棰嗗', 2)  # 榛樿2涓伐浣滄棩
                
                if max_workdays is None:
                    return safe_df
                
                from datetime import date
                from utils.date_utils import get_workday_difference, parse_mmdd_to_date
                
                today = date.today()
                kept_idx = []
                
                for idx, time_val in safe_df["接口时间"].items():
                    if pd.isna(time_val) or str(time_val).strip() in ['', '-']:
                        continue
                    
                    try:
                        due_date = parse_mmdd_to_date(str(time_val).strip(), today)
                        if due_date is None:
                            continue
                        
                        workday_diff = get_workday_difference(due_date, today)
                        
                        # 保留条件（与导出统一）：
                        # 1. 已延期（workday_diff < 0）：全部保留
                        # 2. 鏈潵N涓伐浣滄棩鍐咃紙workday_diff <= max_workdays锛夛細淇濈暀
                        if workday_diff <= max_workdays:
                            kept_idx.append(idx)
                    except Exception:
                        continue
                
                if not kept_idx:
                    return safe_df.iloc[0:0]
                
                return safe_df.loc[kept_idx]
            
            # 7. 绠＄悊鍛樻垨鍏朵粬鏈煡瑙掕壊锛氫笉杩囨护
            return safe_df
        except Exception as e:
            print(f"鍗曡鑹茶繃婊ゅけ璐?[{role}]: {e}")
            return df.iloc[0:0]
    
    def apply_role_based_filter(self, df: pd.DataFrame, project_id: str = None) -> pd.DataFrame:
        """doc"""
        try:
            user_name = getattr(self, 'user_name', '').strip()
            user_roles = getattr(self, 'user_roles', [])
            
            # 鍏煎鏃ч€昏緫锛氬鏋滄病鏈塽ser_roles锛屽皾璇曚粠user_role瑙ｆ瀽
            if not user_roles:
                user_role = getattr(self, 'user_role', '').strip()
                if user_role:
                    user_roles = [user_role]
            
            # 鎺у埗鍙拌緭鍑轰紭鍖栵細宸查獙璇侀€昏緫锛岄粯璁や笉杈撳嚭
            
            if not user_roles or not user_name:
                return df

            # ------------------------------------------------------------
            # 閲嶈锛氬瑙掕壊鈥滄墿澶ф樉绀鸿寖鍥粹€濈殑淇濇姢
            #
            # 濡傛灉鐢ㄦ埛鍚屾椂鎷ユ湁鈥滅鐞嗗憳鈥濆拰鈥滄墍棰嗗/瀹や富浠烩€濈被瑙掕壊锛?
            # 鐩存帴鎸夊瑙掕壊鍙栧苟闆嗕細鎶娾€滅鐞嗗憳(涓嶈繃婊?鈥濈殑鍏ㄩ噺鏁版嵁涔熷悎骞惰繘鏉ワ紝
            # 瀵艰嚧鐪嬭捣鏉モ€滃涓讳换浠嶆樉绀鸿秴杩?7 涓伐浣滄棩鈥濈殑鏁版嵁銆?
            #
            # 涓轰繚璇佸涓讳换/鎵€棰嗗鐨勬椂闂寸獥鍙ｉ鏈燂紙榛樿 7/2 涓伐浣滄棩锛変笉琚粫杩囷紝
            # 褰撳瓨鍦ㄨ繖浜涙椂闂寸獥鍙ｈ鑹叉椂锛屽拷鐣モ€滅鐞嗗憳鈥濊鑹插弬涓庡悎骞躲€?
            # ------------------------------------------------------------
            try:
                time_window_roles = get_time_window_roles()
                # AUTO-COMMENTED during syntax recovery: if "绠＄悊鍛? in user_roles and any(r in time_window_roles for r in user_roles):
                    # AUTO-COMMENTED during syntax recovery: user_roles = [r for r in user_roles if r != "绠＄悊鍛?]
            except Exception:
                pass
            
            safe_df = df.copy()
            
            # 濡傛灉鍙湁涓€涓鑹蹭笖涓嶆槸鎺ュ彛宸ョ▼甯堬紝浣跨敤鏃ч€昏緫锛堝悜鍚庡吋瀹癸級
            if len(user_roles) == 1 and not self._parse_interface_engineer_role(user_roles[0]):
                filtered = self._filter_by_single_role(safe_df, user_roles[0], project_id)
                # 娣诲姞瑙掕壊鏉ユ簮鍒?
                if not filtered.empty and '角色来源' not in filtered.columns:
                    filtered['角色来源'] = user_roles[0]
                return filtered
            
            # 澶氳鑹插鐞嗭細鍒嗗埆绛涢€夛紝鐒跺悗鍚堝苟
            all_results = []
            role_map = {}  # {鍘熷琛屽彿: [瑙掕壊鍒楄〃]}
            
            for role in user_roles:
                filtered = self._filter_by_single_role(safe_df, role, project_id)
                if not filtered.empty:
                    all_results.append(filtered)
                    # 璁板綍姣忎釜鍘熷琛屽彿瀵瑰簲鐨勮鑹?
                    for idx in filtered.index:
                        original_row = filtered.loc[idx, '鍘熷琛屽彿'] if '鍘熷琛屽彿' in filtered.columns else idx
                        if original_row not in role_map:
                            role_map[original_row] = []
                        role_map[original_row].append(role)
            
            if not all_results:
                return safe_df.iloc[0:0]
            
            # 鍚堝苟鎵€鏈夌粨鏋滐紙鎸夊師濮嬭鍙峰幓閲嶏級
            merged = pd.concat(all_results, ignore_index=False)
            if '鍘熷琛屽彿' in merged.columns:
                merged = merged.drop_duplicates(subset=['鍘熷琛屽彿'], keep='first')
            else:
                merged = merged.drop_duplicates(keep='first')
            
            # 娣诲姞瑙掕壊鏉ユ簮鍒?
            if '鍘熷琛屽彿' in merged.columns:
                merged['瑙掕壊鏉ユ簮'] = merged['鍘熷琛屽彿'].apply(
                    # AUTO-COMMENTED during syntax recovery: lambda x: '銆?.join(role_map.get(x, []))
                )
            else:
                # 濡傛灉娌℃湁鍘熷琛屽彿锛屽彧鑳界敤绗竴涓鑹?
                merged['角色来源'] = user_roles[0] if user_roles else ''
            
            return merged
        except Exception as e:
            print(f"角色过滤失败: {e}")
            return df

    def apply_auto_role_date_window(self, df: pd.DataFrame) -> pd.DataFrame:
        """doc"""
        try:
            if not getattr(self, 'auto_mode', False):
                return df
            user_role = getattr(self, 'user_role', '').strip()
            if not user_role:
                return df
            role_days_map = self.config.get("role_export_days", {}) or {}
            if user_role not in role_days_map:
                return df
            raw_days = role_days_map.get(user_role, None)
            if raw_days is None or (isinstance(raw_days, str) and raw_days.strip() == ""):
                return df
            try:
                max_days = int(raw_days)
            except Exception:
                return df
            if "接口时间" not in df.columns:
                return df.iloc[0:0]
            from datetime import date
            from utils.date_utils import get_workday_difference, parse_mmdd_to_date
            
            today = date.today()
            # 鍒ゆ柇鏄惁浣跨敤宸ヤ綔鏃ヨ绠楋紙鎵€棰嗗銆佸涓讳换浣跨敤宸ヤ綔鏃ワ級
            # 绠＄悊鍛樸€佽璁′汉鍛樻棤澶╂暟闄愬埗锛涙帴鍙ｅ伐绋嬪笀涓嶅湪姝ら厤缃腑
            use_workdays = (user_role in get_use_workdays_roles())
            
            kept_idx = []
            for idx, val in df["接口时间"].items():
                try:
                    s = str(val).strip()
                    if not s or s == "鏈煡":
                        continue
                    
                    # 使用统一的日期解析函数（正确处理跨年和跨月）
                    due = parse_mmdd_to_date(s, today)
                    if due is None:
                        continue
                    
                    # 根据角色选择计算方式
                    if use_workdays:
                        delta = get_workday_difference(due, today)
                    else:
                        delta = (due - today).days
                    
                    if delta <= max_days:
                        kept_idx.append(idx)
                except Exception:
                    continue
            if not kept_idx:
                return df.iloc[0:0]
            return df.loc[kept_idx]
        except Exception:
            return df

    def load_user_role(self):
        """doc"""
        self.user_name = self.config.get("user_name", "").strip()
        self.user_role = ""
        self.user_roles = []  # 鏂板锛氳鑹插垪琛?
        if not self.user_name:
            return
        try:
            xls_path = get_resource_path(get_role_table_file())
            if not os.path.exists(xls_path):
                return
            # 浣跨敤浼樺寲鐨勮鍙栨柟娉?
            df = optimized_read_excel(xls_path)
            # 鍏煎鏃犺〃澶?涓嶅悓琛ㄥご
            cols = list(df.columns)
            name_col = None
            role_col = None
            for i, c in enumerate(cols):
                cs = str(c)
                if name_col is None and (cs.find('姓名') != -1):
                    name_col = i
                if role_col is None and (cs.find('角色') != -1):
                    role_col = i
            if name_col is None:
                name_col = 0 if len(cols) >= 1 else None
            if role_col is None:
                role_col = 1 if len(cols) >= 2 else None
            if name_col is None or role_col is None:
                return
            for _, row in df.iterrows():
                try:
                    name_val = str(row.iloc[name_col]).strip()
                    role_val = str(row.iloc[role_col]).strip()
                    if name_val == self.user_name:
                        self.user_role = role_val  # 淇濈暀鍘熷瀛楃涓诧紙鍏煎鎬э級
                        # 解析多重角色（用顿号、分隔）
                        # AUTO-COMMENTED during syntax recovery: self.user_roles = [r.strip() for r in role_val.split('銆?) if r.strip()]
                        print(f"加载角色成功: 用户={self.user_name}, 角色={self.user_roles}")
                        break
                except Exception:
                    continue
        except Exception as e:
            print(f"鍔犺浇瑙掕壊琛ㄥけ璐? {e}")
            pass
    
    def get_valid_names_from_role_table(self):
        """doc"""
        valid_names = set()
        try:
            xls_path = get_resource_path(get_role_table_file())
            if not os.path.exists(xls_path):
                print("姓名角色表不存在")
                return valid_names
            
            # 浣跨敤浼樺寲鐨勮鍙栨柟娉?
            df = optimized_read_excel(xls_path)
            
            # 鍏煎鏃犺〃澶?涓嶅悓琛ㄥご
            cols = list(df.columns)
            name_col = None
            for i, c in enumerate(cols):
                cs = str(c)
                if name_col is None and (cs.find('姓名') != -1):
                    name_col = i
            if name_col is None:
                name_col = 0 if len(cols) >= 1 else None
            
            if name_col is None:
                return valid_names
            
            # 鏀堕泦鎵€鏈夋湁鏁堝鍚?
            for _, row in df.iterrows():
                try:
                    name_val = str(row.iloc[name_col]).strip()
                    if name_val and name_val not in ['nan', 'None', '']:
                        valid_names.add(name_val)
                except Exception:
                    continue
            
            print(f"浠庡鍚嶈鑹茶〃鍔犺浇浜?{len(valid_names)} 涓湁鏁堝鍚?)
            return valid_names
            
        except Exception as e:
            print(f"鍔犺浇濮撳悕瑙掕壊琛ㄥけ璐? {e}")
            return valid_names

    def adjust_font_sizes(self):
        """doc"""
        # 褰撶敤鎴峰悕鎴栬鑹叉敼鍙樻椂锛岄噸鏂扮瓫閫夊苟鏄剧ず鎵€鏈夊凡澶勭悊鐨勬暟鎹?
        
        # 鍔熻兘锛?
        # 1. 瀵规墍鏈?processing_results_multiX 涓殑缂撳瓨鏁版嵁閲嶆柊搴旂敤瑙掕壊绛涢€?
        # 2. 鏇存柊鎵€鏈?processing_resultsX 鍗曟枃浠剁粨鏋?
        # 3. 閲嶆柊鏄剧ず褰撳墠閫夐」鍗＄殑鍐呭
        # 4. 姝ｇ‘澶勭悊"鏃犳暟鎹?鐨勬儏鍐?

        try:
            print("🔄 角色改变，重新筛选所有已处理数据...")
            
            # 澶勭悊鏂囦欢1锛堝唴閮ㄩ渶鎵撳紑鎺ュ彛锛?
            if hasattr(self, 'processing_results_multi1'):
                if self.processing_results_multi1:  # 鏈夌紦瀛樻暟鎹?
                    combined_results = []
                    for project_id, cached_df in self.processing_results_multi1.items():
                        if cached_df is not None and not cached_df.empty:
                            filtered_df = self.apply_role_based_filter(cached_df.copy(), project_id=project_id)
                            if filtered_df is not None and not filtered_df.empty:
                                combined_results.append(filtered_df)
                    
                    if combined_results:
                        self.processing_results = pd.concat(combined_results, ignore_index=True)
                        self.has_processed_results1 = True
                    else:
                        self.processing_results = pd.DataFrame()
                        self.has_processed_results1 = True
                else:  # 绌哄瓧鍏革紝浣嗕粛闇€璁剧疆鏍囧織
                    self.processing_results = pd.DataFrame()
                    self.has_processed_results1 = True
            
            # 澶勭悊鏂囦欢2锛堝唴閮ㄩ渶鍥炲鎺ュ彛锛?
            if hasattr(self, 'processing_results_multi2'):
                if self.processing_results_multi2:  # 鏈夌紦瀛樻暟鎹?
                    combined_results = []
                    for project_id, cached_df in self.processing_results_multi2.items():
                        if cached_df is not None and not cached_df.empty:
                            filtered_df = self.apply_role_based_filter(cached_df.copy(), project_id=project_id)
                            if filtered_df is not None and not filtered_df.empty:
                                combined_results.append(filtered_df)
                    
                    if combined_results:
                        self.processing_results2 = pd.concat(combined_results, ignore_index=True)
                        self.has_processed_results2 = True
                    else:
                        self.processing_results2 = pd.DataFrame()
                        self.has_processed_results2 = True
                else:  # 绌哄瓧鍏革紝浣嗕粛闇€璁剧疆鏍囧織
                    self.processing_results2 = pd.DataFrame()
                    self.has_processed_results2 = True
            
            # 澶勭悊鏂囦欢3锛堝閮ㄩ渶鎵撳紑鎺ュ彛锛?
            if hasattr(self, 'processing_results_multi3'):
                if self.processing_results_multi3:  # 鏈夌紦瀛樻暟鎹?
                    combined_results = []
                    for project_id, cached_df in self.processing_results_multi3.items():
                        if cached_df is not None and not cached_df.empty:
                            filtered_df = self.apply_role_based_filter(cached_df.copy(), project_id=project_id)
                            if filtered_df is not None and not filtered_df.empty:
                                combined_results.append(filtered_df)
                    
                    if combined_results:
                        self.processing_results3 = pd.concat(combined_results, ignore_index=True)
                        self.has_processed_results3 = True
                    else:
                        self.processing_results3 = pd.DataFrame()
                        self.has_processed_results3 = True
                else:  # 绌哄瓧鍏革紝浣嗕粛闇€璁剧疆鏍囧織
                    self.processing_results3 = pd.DataFrame()
                    self.has_processed_results3 = True
            
            # 澶勭悊鏂囦欢4锛堝閮ㄩ渶鍥炲鎺ュ彛锛?
            if hasattr(self, 'processing_results_multi4'):
                if self.processing_results_multi4:  # 鏈夌紦瀛樻暟鎹?
                    combined_results = []
                    for project_id, cached_df in self.processing_results_multi4.items():
                        if cached_df is not None and not cached_df.empty:
                            filtered_df = self.apply_role_based_filter(cached_df.copy(), project_id=project_id)
                            if filtered_df is not None and not filtered_df.empty:
                                combined_results.append(filtered_df)
                    
                    if combined_results:
                        self.processing_results4 = pd.concat(combined_results, ignore_index=True)
                        self.has_processed_results4 = True
                    else:
                        self.processing_results4 = pd.DataFrame()
                        self.has_processed_results4 = True
                else:  # 绌哄瓧鍏革紝浣嗕粛闇€璁剧疆鏍囧織
                    self.processing_results4 = pd.DataFrame()
                    self.has_processed_results4 = True
            
            # 处理文件5（三维提资接口）
            if hasattr(self, 'processing_results_multi5'):
                if self.processing_results_multi5:  # 鏈夌紦瀛樻暟鎹?
                    combined_results = []
                    for project_id, cached_df in self.processing_results_multi5.items():
                        if cached_df is not None and not cached_df.empty:
                            filtered_df = self.apply_role_based_filter(cached_df.copy(), project_id=project_id)
                            if filtered_df is not None and not filtered_df.empty:
                                combined_results.append(filtered_df)
                    
                    if combined_results:
                        self.processing_results5 = pd.concat(combined_results, ignore_index=True)
                        self.has_processed_results5 = True
                    else:
                        self.processing_results5 = pd.DataFrame()
                        self.has_processed_results5 = True
                else:  # 绌哄瓧鍏革紝浣嗕粛闇€璁剧疆鏍囧織
                    self.processing_results5 = pd.DataFrame()
                    self.has_processed_results5 = True
            
            # 处理文件6（收发文函）
            if hasattr(self, 'processing_results_multi6'):
                if self.processing_results_multi6:  # 鏈夌紦瀛樻暟鎹?
                    combined_results = []
                    for project_id, cached_df in self.processing_results_multi6.items():
                        if cached_df is not None and not cached_df.empty:
                            filtered_df = self.apply_role_based_filter(cached_df.copy(), project_id=project_id)
                            if filtered_df is not None and not filtered_df.empty:
                                combined_results.append(filtered_df)
                    
                    if combined_results:
                        self.processing_results6 = pd.concat(combined_results, ignore_index=True)
                        self.has_processed_results6 = True
                    else:
                        self.processing_results6 = pd.DataFrame()
                        self.has_processed_results6 = True
                else:  # 绌哄瓧鍏革紝浣嗕粛闇€璁剧疆鏍囧織
                    self.processing_results6 = pd.DataFrame()
                    self.has_processed_results6 = True
            
            # 刷新当前选项卡的显示
            self.refresh_current_tab_display()
            
            # 鏇存柊瀵煎嚭鎸夐挳鐘舵€?
            self.update_export_button_state()
            
            print("鉁?瑙掕壊绛涢€夊埛鏂板畬鎴?)
            
        except Exception as e:
            print(f"鍒锋柊宸插鐞嗙粨鏋滃け璐? {e}")
            import traceback
            traceback.print_exc()

    def refresh_current_tab_display(self):
        """doc"""
        # 璇嗗埆鐗瑰畾鏍煎紡鐨勭洰鏍囨枃浠?
        
        # 参数:
            # update_ui: 鏄惁鏇存柊Tk鐣岄潰锛堥€夐」鍗♀湏鏍囪锛夈€傚悗鍙扮嚎绋嬭皟鐢ㄦ椂蹇呴』涓篎alse銆?
            # enabled_projects_override: 鍙€夛紝鐩存帴浼犲叆宸插嬀閫夌殑椤圭洰鍙峰垪琛紝閬垮厤鍚庡彴绾跨▼璇诲彇Tk鍙橀噺銆?

        # 閲嶇疆鍗曟枃浠剁姸鎬侊紙鍏煎鎬т繚鐣欙級
        self.target_file1 = None
        self.target_file1_project_id = None
        self.target_file2 = None
        self.target_file2_project_id = None
        self.target_file3 = None
        self.target_file3_project_id = None
        self.target_file4 = None
        self.target_file4_project_id = None
        self.file1_data = None
        self.file2_data = None
        self.file3_data = None
        self.file4_data = None
        
        # 閲嶇疆澶氭枃浠剁姸鎬?
        self.target_files1 = []
        self.target_files2 = []
        self.target_files3 = []
        self.target_files4 = []
        self.target_files5 = []
        self.target_files6 = []
        self.files1_data = {}
        self.files2_data = {}
        self.files3_data = {}
        self.files4_data = {}
        self.files5_data = {}
        self.files6_data = {}
        self.processing_results_multi1 = {}
        self.processing_results_multi2 = {}
        self.processing_results_multi3 = {}
        self.processing_results_multi4 = {}
        self.processing_results_multi5 = {}
        self.processing_results_multi6 = {}
        
        # 閲嶇疆琚拷鐣ョ殑鏂囦欢璁板綍锛堢敤浜庢樉绀猴級
        self.ignored_files = []  # [(鏂囦欢璺緞, 椤圭洰鍙? 鏂囦欢绫诲瀷), ...]
        
        # 閲嶇疆澶勭悊缁撴灉鐘舵€佹爣璁?
        self.has_processed_results1 = False
        self.has_processed_results2 = False
        self.has_processed_results3 = False
        self.has_processed_results4 = False
        self.has_processed_results5 = False
        self.has_processed_results6 = False
        # 閲嶇疆閫夐」鍗＄姸鎬侊紙浠呬富绾跨▼鍙洿鏂癠I锛?
        if update_ui:
            self.update_tab_color(0, "normal")
            self.update_tab_color(1, "normal")
            self.update_tab_color(2, "normal")
            self.update_tab_color(3, "normal")
        if not self.excel_files and not self._is_file1_db_mode_enabled():
            return
        
        # 鑾峰彇鐢ㄦ埛鍕鹃€夌殑椤圭洰鍙凤紙鍚庡彴绾跨▼绂佹璇籘k鍙橀噺锛?
        enabled_projects = enabled_projects_override
        if enabled_projects is None:
            enabled_projects = self.get_enabled_projects()
        try:
            # 瀹夊叏瀵煎叆main妯″潡锛堜笉渚濊禆鏂囦欢绯荤粺妫€鏌ワ級
            try:
                from core import main
            except ImportError:
                import sys
                import os
                # 濡傛灉鏄墦鍖呯幆澧冿紝娣诲姞褰撳墠鐩綍鍒拌矾寰?
                if hasattr(sys, '_MEIPASS'):
                    sys.path.insert(0, sys._MEIPASS)
                else:
                    sys.path.insert(0, os.path.dirname(__file__))
                from core import main
            
            # 璇嗗埆寰呭鐞嗘枃浠?~4锛圫QL铏氭嫙婧愶級
            enabled_pids = enabled_projects or []

            self.target_files1 = [(build_file1_virtual_source(pid), pid) for pid in enabled_pids]
            if self.target_files1:
                self.target_file1, self.target_file1_project_id = self.target_files1[0]
                if update_ui:
                    self.update_tab_color(0, "green")
            else:
                self.target_file1 = None
                self.target_file1_project_id = None

            self.target_files2 = [(build_file2_virtual_source(pid), pid) for pid in enabled_pids]
            if self.target_files2:
                self.target_file2, self.target_file2_project_id = self.target_files2[0]
                if update_ui:
                    self.update_tab_color(1, "green")
            else:
                self.target_file2 = None
                self.target_file2_project_id = None

            self.target_files3 = [(build_file3_virtual_source(pid), pid) for pid in enabled_pids]
            if self.target_files3:
                self.target_file3, self.target_file3_project_id = self.target_files3[0]
                if update_ui:
                    self.update_tab_color(2, "green")
            else:
                self.target_file3 = None
                self.target_file3_project_id = None

            self.target_files4 = [(build_file4_virtual_source(pid), pid) for pid in enabled_pids]
            if self.target_files4:
                self.target_file4, self.target_file4_project_id = self.target_files4[0]
                if update_ui:
                    self.update_tab_color(3, "green")
            else:
                self.target_file4 = None
                self.target_file4_project_id = None

            self.target_files5 = []
            self.target_files6 = []
            self.target_file5 = None
            self.target_file5_project_id = None
            self.target_file6 = None
            self.target_file6_project_id = None
            
            # 鏂囦欢5/6 褰撳墠鐗堟湰鍋滅敤锛屼笉鍙備笌璇嗗埆鍜屽鐞?
            self.target_files5 = []
            self.target_files6 = []
            
            # 銆愭€ц兘浼樺寲Step1銆戝凡纭锛氱Щ闄も€滃苟鍙戦鍔犺浇Excel鈥?
            # 璇存槑锛氶鍔犺浇浠呯敤浜庘€滄湭澶勭悊鐘舵€佸師濮嬮瑙堚€濓紝璇ュ姛鑳藉凡鍒犻櫎銆?
        except Exception as e:
            print(f"璇嗗埆鐩爣鏂囦欢鏃跺彂鐢熼敊璇? {e}")
    
    def _process_with_cache(self, file_path, project_id, file_type, process_func, *args):
        """doc"""
        try:
            if self._is_db_virtual_source(file_path):
                try:
                    self._last_cache_hit_info = {
                        "file_path": file_path,
                        "project_id": str(project_id),
                        "file_type": str(file_type),
                        "hit": False,
                        "db_virtual_source": True,
                    }
                except Exception:
                    pass
                return process_func(file_path, *args)

            # 1. 尝试加载缓存
            cached_result = self.file_manager.load_cached_result(file_path, project_id, file_type)
            
            if cached_result is not None:
                # ------------------------------------------------------------
                # 缂撳瓨鍏煎鎬у厹搴曪紙淇锛氭棫缂撳瓨缂哄皯鍏抽敭娲剧敓鍒椾細瀵艰嚧UI鈥滆矗浠讳汉鈥濆叏涓衡€滄棤鈥濓級
                # - main.py 宸叉槑纭负鍚勬枃浠剁被鍨嬬敓鎴愨€滆矗浠讳汉鈥濆垪锛涜嫢鍛戒腑缂撳瓨鍗寸己鍒楋紝璇存槑缂撳瓨鏉ヨ嚜鏃х増鏈?鎹熷潖
                # - 姝ゆ椂搴旇涓虹紦瀛樻湭鍛戒腑锛岃Е鍙戜竴娆￠噸绠楀苟瑕嗙洊缂撳瓨
                # ------------------------------------------------------------
                try:
                    if isinstance(cached_result, pd.DataFrame):
                        if "璐ｄ换浜? not in cached_result.columns:
                            try:
                                # 仅提示一次：避免刷屏
                                warned = getattr(self, "_warned_incompatible_cache_missing_resp", False)
                                if not warned:
                                    print("[缂撳瓨] 鈿狅笍 鍛戒腑缂撳瓨浣嗙己灏戔€滆矗浠讳汉鈥濆垪锛氬皢蹇界暐鏃х紦瀛樺苟閲嶆柊澶勭悊锛堝缓璁竻鐞?result_cache/ 鐩綍锛?)
                                    self._warned_incompatible_cache_missing_resp = True
                            except Exception:
                                pass
                            try:
                                # 娓呯悊璇ユ枃浠跺搴旂殑 .pkl锛岄伩鍏嶉噸澶嶅懡涓棫缂撳瓨
                                self.file_manager.clear_file_cache(file_path)
                            except Exception:
                                pass
                            cached_result = None
                except Exception:
                    # 鍏滃簳锛氫换浣曟牎楠屽け璐ヤ笉褰卞搷涓绘祦绋?
                    # pass

            if cached_result is not None:
                # 缓存命中
                try:
                    self._last_cache_hit_info = {
                        "file_path": file_path,
                        "project_id": str(project_id),
                        "file_type": str(file_type),
                        "hit": True,
                    }
                except Exception:
                    pass
                print(f"  鉁?浣跨敤缂撳瓨: 椤圭洰{project_id}{file_type} ({len(cached_result)}琛?")
                return cached_result
            
            # 2. 缂撳瓨鏈懡涓紝杩涜澶勭悊
            try:
                self._last_cache_hit_info = {
                    "file_path": file_path,
                    "project_id": str(project_id),
                    "file_type": str(file_type),
                    "hit": False,
                }
            except Exception:
                pass
            result = process_func(file_path, *args)
            
            # 3. 保存缓存
            # Step3锛氬厑璁哥紦瀛樷€滅┖缁撴灉鈥濓紙璐熺紦瀛橈級锛岄伩鍏嶆瘡娆￠兘閲嶅璇诲彇Excel/閲嶅绛涢€夈€?
            if result is not None:
                save_success = self.file_manager.save_cached_result(file_path, project_id, file_type, result)
                if not save_success:
                    # 缓存保存失败，弹窗提醒（仅在手动操作时）
                    if self._should_show_popup():
                        try:
                            from tkinter import messagebox as _mb
                            _mb.showwarning("缓存保存失败", 
                                f"椤圭洰{project_id}{file_type}鐨勭紦瀛樹繚瀛樺け璐ャ€俓n"
                                f"鏁版嵁宸叉甯稿鐞嗭紝浣嗕笅娆″彲鑳介渶瑕侀噸鏂板鐞嗐€?)
                        except Exception:
                            pass
            
            return result
            
        except Exception as e:
            try:
                self._last_cache_hit_info = {
                    "file_path": file_path,
                    "project_id": str(project_id),
                    "file_type": str(file_type),
                    "hit": False,
                    "error": str(e),
                }
            except Exception:
                pass
            print(f"处理{file_type}失败 [项目{project_id}]: {e}")
            return None
    
    def _check_and_load_cache(self):
        """doc"""
        try:
            print("\n馃攳 妫€鏌ユ枃浠舵爣璇嗗拰缂撳瓨...")
            
            # 1. 鏀堕泦鎵€鏈夊緟澶勭悊鏂囦欢鐨勮矾寰?
            all_file_paths = []
            if hasattr(self, 'target_files1') and self.target_files1:
                all_file_paths.extend(
                    [f[0] for f in self.target_files1 if not is_file1_db_virtual_source(f[0])]
                )
            if hasattr(self, 'target_files2') and self.target_files2:
                all_file_paths.extend([f[0] for f in self.target_files2 if not self._is_db_virtual_source(f[0])])
            if hasattr(self, 'target_files3') and self.target_files3:
                all_file_paths.extend([f[0] for f in self.target_files3 if not self._is_db_virtual_source(f[0])])
            if hasattr(self, 'target_files4') and self.target_files4:
                all_file_paths.extend([f[0] for f in self.target_files4 if not self._is_db_virtual_source(f[0])])
            if hasattr(self, 'target_files5') and self.target_files5:
                all_file_paths.extend([f[0] for f in self.target_files5 if not self._is_db_virtual_source(f[0])])
            if hasattr(self, 'target_files6') and self.target_files6:
                all_file_paths.extend([f[0] for f in self.target_files6 if not self._is_db_virtual_source(f[0])])
            
            # 去重
            all_file_paths = list(set(all_file_paths))
            
            if not all_file_paths:
                print("  鏈彂鐜板緟澶勭悊鏂囦欢锛岃烦杩囩紦瀛樻鏌?)
                return
            
            # 2. 妫€鏌ュ摢浜涙枃浠跺彂鐢熷彉鍖栵紙澧為噺锛?
            try:
                changed_files = set(self.file_manager.get_changed_files(all_file_paths) or [])
            except Exception:
                changed_files = set(all_file_paths) if self.file_manager.check_files_changed(all_file_paths) else set()

            if changed_files:
                print(f"  鈿狅笍 妫€娴嬪埌 {len(changed_files)} 涓枃浠跺彉鍖栵細浠呮竻鐞嗗彉鍔ㄦ枃浠跺搴旂紦瀛?鍕鹃€夌姸鎬?)
                for fp in changed_files:
                    try:
                        self.file_manager.clear_file_completed_rows(fp, user_name="")  # 鎵€鏈夌敤鎴?
                    except Exception:
                        pass
                    try:
                        self.file_manager.clear_file_cache(fp)
                    except Exception:
                        pass
                # 鍙樺寲/鏂版枃浠堕渶瑕佸啓鍏ユ渶鏂?identity锛涙湭鍙樺寲鏂囦欢涔熼『渚胯ˉ榻?identity锛堟瀬灏忓紑閿€锛?
                self.file_manager.update_file_identities(all_file_paths)

                # 娓呮帀鍐呭瓨涓€滃彉鍔ㄦ枃浠跺搴旈」鐩€濈殑缁撴灉锛岄伩鍏?UI 缁х画鏄剧ず鏃ф暟鎹?
                def _drop_from_multi(target_list, multi_dict):
                    try:
                        for fp, pid in (target_list or []):
                            if fp in changed_files:
                                try:
                                    multi_dict.pop(pid, None)
                                except Exception:
                                    pass
                    except Exception:
                        pass

                _drop_from_multi(getattr(self, "target_files1", None), getattr(self, "processing_results_multi1", {}))
                _drop_from_multi(getattr(self, "target_files2", None), getattr(self, "processing_results_multi2", {}))
                _drop_from_multi(getattr(self, "target_files3", None), getattr(self, "processing_results_multi3", {}))
                _drop_from_multi(getattr(self, "target_files4", None), getattr(self, "processing_results_multi4", {}))
                _drop_from_multi(getattr(self, "target_files5", None), getattr(self, "processing_results_multi5", {}))
                _drop_from_multi(getattr(self, "target_files6", None), getattr(self, "processing_results_multi6", {}))

            else:
                # 鏂囦欢鏈彉鍖栵紝涔熼渶瑕佹洿鏂版爣璇嗭紙涓烘柊鏂囦欢璁板綍鏍囪瘑锛?
                self.file_manager.update_file_identities(all_file_paths)

            # 3. 鍔犺浇鈥滄湭鍙樺寲鏂囦欢鈥濈殑缂撳瓨锛堝嵆浣块儴鍒嗘枃浠跺彉鍖栵紝涔熷敖閲忓揩閫熸仮澶?UI锛?
            if changed_files:
                print("  鉁?鍙樺姩鏂囦欢宸叉竻鐞嗭細鍔犺浇鏈彉鍖栨枃浠剁殑缂撳瓨浠ラ伩鍏嶇┖绐?..")
            else:
                print("  鉁?鏂囦欢鏈彉鍖栵紝灏濊瘯鍔犺浇缂撳瓨...")
            cache_loaded_count = 0

            # Step2锛氳褰曟湰杞€滃埛鏂板姞杞界紦瀛樷€濈殑蹇収锛岀敤浜?start_processing 澶嶇敤鍐呭瓨缂撳瓨
            try:
                import time as _time
                self._cache_loaded_snapshot = {
                    "all_file_paths": tuple(sorted(all_file_paths or [])),
                    "changed_files": tuple(sorted(changed_files or [])),
                    "ts": float(_time.time()),
                }
            except Exception:
                self._cache_loaded_snapshot = {"all_file_paths": tuple(sorted(all_file_paths or []))}
            # 閲嶇疆鏈疆鍘熷缂撳瓨缁撴灉瀹瑰櫒锛堝彧淇濆瓨鈥渞aw锛堣鑹茬瓫閫夊墠锛夆€濓級
            self._cache_loaded_raw_multi1 = {}
            self._cache_loaded_raw_multi2 = {}
            self._cache_loaded_raw_multi3 = {}
            self._cache_loaded_raw_multi4 = {}
            self._cache_loaded_raw_multi5 = {}
            self._cache_loaded_raw_multi6 = {}
            
            # 鍔犺浇file1缂撳瓨锛堟暟鎹簱妯″紡涓嬬鐢ㄧ紦瀛橈級
            if (not self._is_file1_db_mode_enabled()) and hasattr(self, 'target_files1') and self.target_files1:
                for file_path, project_id in self.target_files1:
                    if file_path in changed_files:
                        continue
                    cached_df = self.file_manager.load_cached_result(file_path, project_id, 'file1')
                    if cached_df is not None:
                        # Step2锛氫繚瀛?raw锛堣鑹茬瓫閫夊墠锛夛紝渚?start_processing 澶嶇敤锛岄伩鍏嶄簩娆¤ .pkl
                        try:
                            raw_df = cached_df.copy()
                            if '椤圭洰鍙? not in raw_df.columns:
                                raw_df['椤圭洰鍙?] = project_id
                            self._cache_loaded_raw_multi1[project_id] = raw_df
                        except Exception:
                            pass
                        # 銆愪慨澶嶃€戝缂撳瓨鏁版嵁搴旂敤瑙掕壊绛涢€夛紝娣诲姞"瑙掕壊鏉ユ簮"鍒?
                        filtered_df = self.apply_role_based_filter(cached_df.copy(), project_id=project_id)
                        if filtered_df is not None and not filtered_df.empty:
                            # 添加项目号列
                            if '椤圭洰鍙? not in filtered_df.columns:
                                filtered_df['椤圭洰鍙?] = project_id
                            self.processing_results_multi1[project_id] = filtered_df
                        cache_loaded_count += 1
                if self.processing_results_multi1:
                    self.has_processed_results1 = True
            
            # 加载file2缓存
            if hasattr(self, 'target_files2') and self.target_files2:
                for file_path, project_id in self.target_files2:
                    if file_path in changed_files:
                        continue
                    cached_df = self.file_manager.load_cached_result(file_path, project_id, 'file2')
                    if cached_df is not None:
                        try:
                            raw_df = cached_df.copy()
                            if '椤圭洰鍙? not in raw_df.columns:
                                raw_df['椤圭洰鍙?] = project_id
                            self._cache_loaded_raw_multi2[project_id] = raw_df
                        except Exception:
                            pass
                        # 銆愪慨澶嶃€戝缂撳瓨鏁版嵁搴旂敤瑙掕壊绛涢€夛紝娣诲姞"瑙掕壊鏉ユ簮"鍒?
                        filtered_df = self.apply_role_based_filter(cached_df.copy(), project_id=project_id)
                        if filtered_df is not None and not filtered_df.empty:
                            # 添加项目号列
                            if '椤圭洰鍙? not in filtered_df.columns:
                                filtered_df['椤圭洰鍙?] = project_id
                            self.processing_results_multi2[project_id] = filtered_df
                        cache_loaded_count += 1
                if self.processing_results_multi2:
                    self.has_processed_results2 = True
            
            # 加载file3缓存
            if hasattr(self, 'target_files3') and self.target_files3:
                for file_path, project_id in self.target_files3:
                    if file_path in changed_files:
                        continue
                    cached_df = self.file_manager.load_cached_result(file_path, project_id, 'file3')
                    if cached_df is not None:
                        try:
                            raw_df = cached_df.copy()
                            if '椤圭洰鍙? not in raw_df.columns:
                                raw_df['椤圭洰鍙?] = project_id
                            self._cache_loaded_raw_multi3[project_id] = raw_df
                        except Exception:
                            pass
                        # 銆愪慨澶嶃€戝缂撳瓨鏁版嵁搴旂敤瑙掕壊绛涢€夛紝娣诲姞"瑙掕壊鏉ユ簮"鍒?
                        filtered_df = self.apply_role_based_filter(cached_df.copy(), project_id=project_id)
                        if filtered_df is not None and not filtered_df.empty:
                            # 添加项目号列
                            if '椤圭洰鍙? not in filtered_df.columns:
                                filtered_df['椤圭洰鍙?] = project_id
                            self.processing_results_multi3[project_id] = filtered_df
                        cache_loaded_count += 1
                if self.processing_results_multi3:
                    self.has_processed_results3 = True
            
            # 加载file4缓存
            if hasattr(self, 'target_files4') and self.target_files4:
                for file_path, project_id in self.target_files4:
                    if file_path in changed_files:
                        continue
                    cached_df = self.file_manager.load_cached_result(file_path, project_id, 'file4')
                    if cached_df is not None:
                        try:
                            raw_df = cached_df.copy()
                            if '椤圭洰鍙? not in raw_df.columns:
                                raw_df['椤圭洰鍙?] = project_id
                            self._cache_loaded_raw_multi4[project_id] = raw_df
                        except Exception:
                            pass
                        # 銆愪慨澶嶃€戝缂撳瓨鏁版嵁搴旂敤瑙掕壊绛涢€夛紝娣诲姞"瑙掕壊鏉ユ簮"鍒?
                        filtered_df = self.apply_role_based_filter(cached_df.copy(), project_id=project_id)
                        if filtered_df is not None and not filtered_df.empty:
                            # 添加项目号列
                            if '椤圭洰鍙? not in filtered_df.columns:
                                filtered_df['椤圭洰鍙?] = project_id
                            self.processing_results_multi4[project_id] = filtered_df
                        cache_loaded_count += 1
                if self.processing_results_multi4:
                    self.has_processed_results4 = True
            
            # 加载file5缓存
            if hasattr(self, 'target_files5') and self.target_files5:
                for file_path, project_id in self.target_files5:
                    if file_path in changed_files:
                        continue
                    cached_df = self.file_manager.load_cached_result(file_path, project_id, 'file5')
                    if cached_df is not None:
                        try:
                            raw_df = cached_df.copy()
                            if '椤圭洰鍙? not in raw_df.columns:
                                raw_df['椤圭洰鍙?] = project_id
                            self._cache_loaded_raw_multi5[project_id] = raw_df
                        except Exception:
                            pass
                        # 銆愪慨澶嶃€戝缂撳瓨鏁版嵁搴旂敤瑙掕壊绛涢€夛紝娣诲姞"瑙掕壊鏉ユ簮"鍒?
                        filtered_df = self.apply_role_based_filter(cached_df.copy(), project_id=project_id)
                        if filtered_df is not None and not filtered_df.empty:
                            # 添加项目号列
                            if '椤圭洰鍙? not in filtered_df.columns:
                                filtered_df['椤圭洰鍙?] = project_id
                            self.processing_results_multi5[project_id] = filtered_df
                        cache_loaded_count += 1
                if self.processing_results_multi5:
                    self.has_processed_results5 = True
            
            # 加载file6缓存
            if hasattr(self, 'target_files6') and self.target_files6:
                for file_path, project_id in self.target_files6:
                    if file_path in changed_files:
                        continue
                    cached_df = self.file_manager.load_cached_result(file_path, project_id, 'file6')
                    if cached_df is not None:
                        try:
                            raw_df = cached_df.copy()
                            if '椤圭洰鍙? not in raw_df.columns:
                                raw_df['椤圭洰鍙?] = project_id
                            self._cache_loaded_raw_multi6[project_id] = raw_df
                        except Exception:
                            pass
                        # 銆愪慨澶嶃€戝缂撳瓨鏁版嵁搴旂敤瑙掕壊绛涢€夛紝娣诲姞"瑙掕壊鏉ユ簮"鍒?
                        filtered_df = self.apply_role_based_filter(cached_df.copy(), project_id=project_id)
                        if filtered_df is not None and not filtered_df.empty:
                            # 添加项目号列
                            if '椤圭洰鍙? not in filtered_df.columns:
                                filtered_df['椤圭洰鍙?] = project_id
                            self.processing_results_multi6[project_id] = filtered_df
                        cache_loaded_count += 1
                if self.processing_results_multi6:
                    self.has_processed_results6 = True
            
            # 4. 鏇存柊鏂囦欢鏍囪瘑锛堝鏋滀箣鍓嶆病鏈夛級
            self.file_manager.update_file_identities(all_file_paths)
            
            if cache_loaded_count > 0:
                print(f"  鉁?鎴愬姛鍔犺浇 {cache_loaded_count} 涓紦瀛樼粨鏋?)
            else:
                print("  鈩癸笍 鏈壘鍒板彲鐢ㄧ紦瀛橈紝闇€瑕侀噸鏂板鐞?)
            
        except Exception as e:
            print(f"妫€鏌ュ拰鍔犺浇缂撳瓨鏃跺彂鐢熼敊璇? {e}")
            import traceback
            traceback.print_exc()

    # ============================================================
    # 鎬ц兘浼樺寲 Step2锛氬埛鏂扮紦瀛樺鐢紙渚?start_processing 浣跨敤锛?
    # ============================================================
    def _can_reuse_refresh_cache(self, all_file_paths) -> bool:
        """doc"""
        # 鑾峰彇 refresh 闃舵宸插姞杞藉埌鍐呭瓨鐨?raw df锛堣鑹茬瓫閫夊墠锛夛紝鐢ㄤ簬 start_processing 澶嶇敤銆?
        # - 浠呭綋 file_path 鏈彉鍖?涓?蹇収鍖归厤 鏃惰繑鍥烇紱鍚﹀垯杩斿洖 None銆?

        try:
            if file_path in (changed_files or set()):
                return None
            if not self._can_reuse_refresh_cache(all_file_paths):
                return None
            store = getattr(self, f"_cache_loaded_raw_multi{int(file_type)}", None)
            if isinstance(store, dict):
                return store.get(project_id)
        except Exception:
            return None
        return None

    def update_file_info(self, text):
        """doc"""
        # 鍒濆鍖朥I浠诲姟闃熷垪骞跺惎鍔ㄤ富绾跨▼杞銆?
        # 鍚庡彴绾跨▼鍙兘鍏ラ槦锛屼笉鍏佽鐩存帴璋冪敤浠讳綍Tk API銆?

        import queue
        if getattr(self, "_ui_task_queue", None) is None:
            self._ui_task_queue = queue.Queue()
        # 鍚姩杞锛堝彧鍦ㄤ富绾跨▼璋冪敤锛?
        try:
            self.root.after(100, self._drain_ui_tasks)
        except Exception:
            pass

    def _post_ui_task(self, func):
        """doc"""
        # 鍙樉绀烘渶缁堢瓫閫夊嚭鏉ョ殑鏁版嵁琛岋紝琛屽彿浠xcel鍘熻〃涓哄噯锛屼笉鏄剧ず琛ㄥご銆?

        try:
            if results is None or results.empty or '鍘熷琛屽彿' not in results.columns:
                self.show_empty_message(self.tab1_viewer, "无内部需打开接口")
                return

            # 鍙彇鏈€缁堢粨鏋滅殑鎵€鏈夋暟鎹
            # 涓嶈drop鍘熷琛屽彿鍒楋紝鍥犱负闇€瑕佸畠鏉ュ姞杞藉嬀閫夌姸鎬?
            excel_row_numbers = list(results['鍘熷琛屽彿'])

            # 鍙樉绀烘暟鎹锛屼笉鏄剧ず琛ㄥご
            self.display_excel_data_with_original_rows(self.tab1_viewer, results, "鍐呴儴闇€鎵撳紑鎺ュ彛", excel_row_numbers)
        except Exception as e:
            print(f"鏄剧ず鏈€缁堢瓫閫夋暟鎹椂鍙戠敓閿欒: {e}")
            self.show_empty_message(self.tab1_viewer, "数据过滤失败")
            # 澶勭悊澶辫触鏃朵篃闇€瑕佹洿鏂板鍑烘寜閽姸鎬?
            self.update_export_button_state()

    def display_results2(self, results, show_popup=True):
        """doc"""
        try:
            # 1. 鑾峰彇鍙墽琛屾枃浠惰矾寰?
            exe_path = os.path.abspath(sys.argv[0])
            
            # 2. 规范化路径（处理空格和特殊字符）
            if exe_path.endswith('.py'):
                # Python脚本模式
                python_exe = sys.executable
                # 纭繚璺緞鐢ㄥ弻寮曞彿鍖呰９
                startup_cmd = f'"{python_exe}" "{exe_path}" --auto'
            else:
                # 鍙墽琛屾枃浠舵ā寮?
                startup_cmd = f'"{exe_path}" --auto'
            
            # 3. 灏濊瘯鍐欏叆娉ㄥ唽琛?
            try:
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER, 
                    r"Software\Microsoft\Windows\CurrentVersion\Run", 
                    0, 
                    winreg.KEY_WRITE | winreg.KEY_READ  # 纭繚鏈夎鍐欐潈闄?
                )
                winreg.SetValueEx(key, "ExcelProcessor", 0, winreg.REG_SZ, startup_cmd)
                winreg.CloseKey(key)
                
                # 4. 楠岃瘉鍐欏叆鏄惁鎴愬姛
                verify_key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER, 
                    r"Software\Microsoft\Windows\CurrentVersion\Run", 
                    0, 
                    winreg.KEY_READ
                )
                try:
                    stored_value, _ = winreg.QueryValueEx(verify_key, "ExcelProcessor")
                    winreg.CloseKey(verify_key)
                    
                    if stored_value != startup_cmd:
                        raise ValueError("娉ㄥ唽琛ㄥ€奸獙璇佸け璐ワ細鍐欏叆鐨勫€间笌璇诲彇鐨勫€间笉涓€鑷?)
                    
                    # 成功提示
                    if show_dialog and self._should_show_popup():
                        messagebox.showinfo("鎴愬姛", f"寮€鏈鸿嚜鍚姩璁剧疆鎴愬姛\n\n璺緞锛歿exe_path}\n鍛戒护锛歿startup_cmd}")
                    
                except Exception as verify_error:
                    raise ValueError(f"验证失败: {verify_error}")
                    
            except PermissionError:
                raise PermissionError("鏉冮檺涓嶈冻锛屾棤娉曞啓鍏ユ敞鍐岃〃銆傝浠ョ鐞嗗憳韬唤杩愯绋嬪簭銆?)
            except OSError as os_error:
                raise OSError(f"娉ㄥ唽琛ㄦ搷浣滃け璐? {os_error}")
            
        except Exception as e:
            error_msg = f"璁剧疆寮€鏈鸿嚜鍚姩澶辫触:\n\n{str(e)}\n\n鍙兘鍘熷洜:\n1. 鏉冮檺涓嶈冻锛堥渶瑕佺鐞嗗憳鏉冮檺锛塡n2. 娉ㄥ唽琛ㄨ瀹夊叏杞欢淇濇姢\n3. 绯荤粺绛栫暐闄愬埗\n\n寤鸿锛氳浠ョ鐞嗗憳韬唤杩愯绋嬪簭閲嶈瘯"
            if show_dialog and self._should_show_popup():
                messagebox.showerror("閿欒", error_msg)
            if show_dialog:
                self.auto_startup_var.set(False)
            # 璁板綍鍒版棩蹇?
            print(f"[寮€鏈鸿嚜鍚姩] 璁剧疆澶辫触: {e}")

    def remove_from_startup(self):
        """doc"""
        # 鏀堕泦褰撳墠鎵€鏈夊凡寤舵湡鐨勪换鍔?
        
        # 銆愬叧閿敼杩涖€戠洿鎺ヤ粠鏁版嵁搴撹鍙栵紝鑰屼笉鏄粠UI鐨剉iewer涓鍙?
        # 杩欐牱鏇村彲闈狅紝涓嶄緷璧朥I鐘舵€?
        
        # 返回:
            List[Dict]: 延期任务列表

        from utils.date_utils import is_date_overdue
        import registry.hooks as registry_hooks
        
        overdue_tasks = []
        
        try:
            # 获取registry配置
            cfg = registry_hooks._cfg()
            if not cfg:
                print("[鏀堕泦寤舵湡浠诲姟] Registry鏈厤缃?)
                return []
            
            db_path = cfg.get('registry_db_path')
            if not db_path:
                print("[收集延期任务] 数据库路径未设置")
                return []
            
            # 鐩存帴浠庢暟鎹簱璇诲彇鎵€鏈夋湭蹇界暐鐨勪换鍔?
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.execute("""
                SELECT 
                    file_type, project_id, interface_id, source_file, 
                    row_index, interface_time, status, display_status,
                    responsible_person, department, role
                FROM tasks
                WHERE status NOT IN ('archived')
                  AND (ignored IS NULL OR ignored = 0)
                ORDER BY file_type, project_id, interface_id
            """)
            
            rows = cursor.fetchall()
            print(f"[鏀堕泦寤舵湡浠诲姟] 浠庢暟鎹簱璇诲彇鍒?{len(rows)} 涓湭褰掓。涓旀湭蹇界暐鐨勪换鍔?)
            
            # 鏂囦欢绫诲瀷鏄犲皠鍒伴€夐」鍗″悕绉?
            file_type_names = {
                1: '鍐呴儴闇€鎵撳紑鎺ュ彛',
                2: '鍐呴儴闇€鍥炲鎺ュ彛',
                3: '澶栭儴闇€鎵撳紑鎺ュ彛',
                4: '澶栭儴闇€鍥炲鎺ュ彛',
                5: '三维提资接口',
                6: '收发文函'
            }
            
            # 妫€鏌ユ瘡涓换鍔℃槸鍚﹀欢鏈?
            for row in rows:
                try:
                    file_type, project_id, interface_id, source_file, row_index, interface_time, status, display_status, responsible_person, department, role = row
                    
                    # 妫€鏌ユ帴鍙ｆ椂闂存槸鍚︽湁鏁?
                    if not interface_time or str(interface_time).strip() in ['', '-', 'nan', 'None', '鏈煡']:
                        continue
                    
                    # 鍒ゆ柇鏄惁寤舵湡
                    if not is_date_overdue(str(interface_time)):
                        continue
                    
                    # 构建任务信息
                    task = {
                        'file_type': file_type,
                        'project_id': str(project_id),
                        'interface_id': str(interface_id),
                        'source_file': str(source_file) if source_file else '',
                        'row_index': row_index if row_index else 0,
                        'interface_time': str(interface_time).strip(),
                        'status': str(status) if status else '',
                        'display_status': str(display_status) if display_status else '',
                        'responsible_person': str(responsible_person) if responsible_person else '',
                        'department': str(department) if department else '',
                        'role': str(role) if role else '',
                        'tab_name': file_type_names.get(file_type, f'文件类型{file_type}')
                    }
                    
                    overdue_tasks.append(task)
                    print(f"  [延期] {interface_id} ({project_id}) - {interface_time} [{file_type_names.get(file_type)}]")
                    
                except Exception as e:
                    print(f"[收集延期任务] 处理任务失败: {e}")
                    continue
            
            conn.close()
            
        except Exception as e:
            print(f"[鏀堕泦寤舵湡浠诲姟] 鏁版嵁搴撴煡璇㈠け璐? {e}")
            import traceback
            traceback.print_exc()
        
        print(f"[鏀堕泦寤舵湡浠诲姟] 鉁?鍏辨壘鍒?{len(overdue_tasks)} 涓欢鏈熶换鍔?)
        return overdue_tasks


def parse_cli_args(argv):
    auto_mode = False
    resume_action = ""
    idx = 0
    while idx < len(argv):
        arg = argv[idx]
        if arg == "--auto":
            auto_mode = True
        elif arg == "--resume":
            if idx + 1 < len(argv):
                resume_action = argv[idx + 1]
                idx += 1
        idx += 1
    return auto_mode, resume_action


def main():
    """涓诲嚱鏁?""
    _init_crash_logging()
    auto_mode, resume_action = parse_cli_args(sys.argv[1:])
    app = ExcelProcessorApp(auto_mode=auto_mode, resume_action=resume_action)
    app.run()


if __name__ == "__main__":
    main()

