import os
from datetime import datetime, date
from typing import Dict, Any, Optional


def _format_date_for_filename(current_datetime: Optional[Any]) -> str:
    """将传入的日期/时间对象或字符串格式化为 YYYY-MM-DD，用于文件名。
    兼容传入 datetime/date/字符串/None。
    """
    # datetime/date
    try:
        if hasattr(current_datetime, 'strftime'):
            return current_datetime.strftime('%Y-%m-%d')
    except Exception:
        pass

    # 字符串（尽量提取前10位日期样式）
    if isinstance(current_datetime, str) and len(current_datetime) >= 10:
        return current_datetime[:10]

    # 兜底：今天
    return date.today().strftime('%Y-%m-%d')


def write_export_summary(
    folder_path: str,
    current_datetime: Optional[Any],
    results_multi1: Optional[Dict[str, Any]] = None,
    results_multi2: Optional[Dict[str, Any]] = None,
    results_multi3: Optional[Dict[str, Any]] = None,
    results_multi4: Optional[Dict[str, Any]] = None,
    results_multi5: Optional[Dict[str, Any]] = None,
    results_multi6: Optional[Dict[str, Any]] = None,
) -> str:
    """依据导出的批量处理结果，生成结果汇总TXT文件。

    内容包括：涉及的项目号；每个项目下待处理文件1/2/3/4的筛选结果数量。
    返回生成的汇总文件绝对路径。
    """
    results_multi1 = results_multi1 or {}
    results_multi2 = results_multi2 or {}
    results_multi3 = results_multi3 or {}
    results_multi4 = results_multi4 or {}
    results_multi5 = results_multi5 or {}
    results_multi6 = results_multi6 or {}

    # 参与的项目号（四类结果字典的并集）
    project_ids = set()
    project_ids.update(results_multi1.keys())
    project_ids.update(results_multi2.keys())
    project_ids.update(results_multi3.keys())
    project_ids.update(results_multi4.keys())
    project_ids.update(results_multi5.keys())
    project_ids.update(results_multi6.keys())

    date_str = _format_date_for_filename(current_datetime)
    filename = f"结果汇总{date_str}.txt"
    output_path = os.path.join(folder_path, filename)

    # 计算总计
    total_1 = sum(len(df) for df in results_multi1.values())
    total_2 = sum(len(df) for df in results_multi2.values())
    total_3 = sum(len(df) for df in results_multi3.values())
    total_4 = sum(len(df) for df in results_multi4.values())
    total_5 = sum(len(df) for df in results_multi5.values())
    total_6 = sum(len(df) for df in results_multi6.values())

    lines = []
    lines.append(f"结果汇总 - {date_str}")
    lines.append("=" * 32)
    if project_ids:
        lines.append("涉及的项目号：" + ", ".join(sorted(project_ids)))
    else:
        lines.append("涉及的项目号：无（本次无任何可导出结果）")
    lines.append("")

    # 每个项目的明细
    def _pid_display(pid: str) -> str:
        return pid if pid else "未知项目"

    for pid in sorted(project_ids):
        c1 = len(results_multi1.get(pid, []))
        c2 = len(results_multi2.get(pid, []))
        c3 = len(results_multi3.get(pid, []))
        c4 = len(results_multi4.get(pid, []))
        c5 = len(results_multi5.get(pid, []))
        c6 = len(results_multi6.get(pid, []))
        total = c1 + c2 + c3 + c4 + c5 + c6
        lines.append(
            f"项目 {_pid_display(pid)}：内部需打开接口={c1}，内部需回复接口={c2}，外部需打开接口={c3}，外部需回复接口={c4}，三维提资接口={c5}，收发文函={c6}，合计={total}"
        )

    lines.append("")
    lines.append("总计：")
    lines.append(f"内部需打开接口合计={total_1}")
    lines.append(f"内部需回复接口合计={total_2}")
    lines.append(f"外部需打开接口合计={total_3}")
    lines.append(f"外部需回复接口合计={total_4}")
    lines.append(f"三维提资接口合计={total_5}")
    lines.append(f"收发文函合计={total_6}")

    # 追加：按文件类别 -> 科室 -> 项目号 的层级明细
    lines.append("")
    lines.append("按科室与项目分类明细：")

    def _normalize_department_value(val: Any) -> str:
        try:
            s = str(val).strip()
        except Exception:
            s = ""
        return s if s else "请室主任确认"

    # 文件类别顺序固定
    file_categories = [
        ("内部需打开接口", results_multi1),
        ("内部需回复接口", results_multi2),
        ("外部需打开接口", results_multi3),
        ("外部需回复接口", results_multi4),
        ("三维提资接口", results_multi5),
        ("收发文函", results_multi6),
    ]

    # 当前日期用于时间提醒
    try:
        if hasattr(current_datetime, 'date'):
            _current_date = current_datetime.date()
        elif isinstance(current_datetime, datetime):
            _current_date = current_datetime.date()
        elif isinstance(current_datetime, date):
            _current_date = current_datetime
        else:
            _current_date = date.today()
    except Exception:
        _current_date = date.today()

    def _warn_tag(mmdd: str) -> str:
        # 根据 mm.dd 与当前日期天数差生成提醒标签
        try:
            if not mmdd or mmdd == "未知":
                return ""
            m, d = mmdd.split(".")
            due = date(_current_date.year, int(m), int(d))
            delta = (due - _current_date).days
            if delta <= 0:
                return "（已延误！！）"
            if delta <= 3:
                return "（下班前必须完成）"
            if delta <= 7:
                return "（注意时间）"
            return ""
        except Exception:
            return ""

    # 重组为：科室 -> 文件类型 -> 项目 -> 接口时间
    # 构建聚合映射：dept -> category -> pid -> time_key -> {'count': int, 'interface_ids': list}
    dept_map: Dict[str, Dict[str, Dict[str, Dict[str, Dict]]]] = {}
    
    # 定义接口号列映射
    interface_column_map = {
        "内部需打开接口": "A",
        "内部需回复接口": "R", 
        "外部需打开接口": "C",
        "外部需回复接口": "E",
        "三维提资接口": "A",  # 三维提资接口使用A列
        "收发文函": "E"
    }
    
    for category_name, category_results in file_categories:
        if not category_results:
            continue
        for pid, df in category_results.items():
            try:
                if df is None or (hasattr(df, 'empty') and df.empty):
                    continue
                # 确定部门列
                if "科室" in getattr(df, 'columns', []):
                    dept_series = [
                        _normalize_department_value(v) for v in df["科室"].tolist()
                    ]
                else:
                    dept_series = ["请室主任确认"] * len(df)

                # 确定接口时间列
                if "接口时间" in getattr(df, 'columns', []):
                    time_series = [
                        (str(v).strip() if v is not None and str(v).strip() else "未知")
                        for v in df["接口时间"].tolist()
                    ]
                else:
                    time_series = ["未知"] * len(df)
                
                # 确定接口号列索引（使用列索引而非列名）
                interface_col_letter = interface_column_map.get(category_name, "A")
                # 将字母转换为索引：A=0, B=1, C=2, ..., R=17
                col_index_map = {
                    "A": 0, "B": 1, "C": 2, "D": 3, "E": 4, "F": 5,
                    "G": 6, "H": 7, "I": 8, "J": 9, "K": 10, "L": 11,
                    "M": 12, "N": 13, "O": 14, "P": 15, "Q": 16, "R": 17
                }
                col_idx = col_index_map.get(interface_col_letter, 0)
                
                # 使用iloc通过索引获取列数据
                if col_idx < len(df.columns):
                    interface_series = [
                        (str(v).strip() if v is not None and str(v).strip() and str(v) != 'nan' else "")
                        for v in df.iloc[:, col_idx].tolist()
                    ]
                else:
                    interface_series = [""] * len(df)

                # 累计计数和接口号
                for dept_value, time_key, interface_id in zip(dept_series, time_series, interface_series):
                    dept_entry = dept_map.setdefault(dept_value, {})
                    cat_entry = dept_entry.setdefault(category_name, {})
                    pid_entry = cat_entry.setdefault(pid, {})
                    time_entry = pid_entry.setdefault(time_key, {'count': 0, 'interface_ids': []})
                    time_entry['count'] += 1
                    if interface_id:  # 只添加非空的接口号
                        time_entry['interface_ids'].append(interface_id)
            except Exception:
                continue

    # 输出结构：科室 -> 文件类型 -> 项目 -> 时间明细
    def _sort_key(k: str):
        try:
            m, d = k.split(".")
            return (0, int(m), int(d))
        except Exception:
            return (1, 99, 99)

    if not dept_map:
        lines.append("")
        lines.append("（无数据）")
    else:
        for dept in sorted(dept_map.keys()):
            lines.append("")
            lines.append(f"科室：{dept}")
            # 按既定文件类别次序输出
            for category_name, _cr in file_categories:
                if category_name not in dept_map[dept]:
                    continue
                lines.append(f"  {category_name}")
                cat_entry = dept_map[dept][category_name]
                for pid in sorted(cat_entry.keys()):
                    lines.append(f"    {_pid_display(pid)}项目：")
                    time_data = cat_entry[pid]
                    action_word = "需打开" if category_name in ("内部需打开接口", "外部需打开接口", "三维提资接口") else "需回复"
                    # 按时间排序逐条输出：mm.dd + 动词 + 数量 + 时间提醒 + 接口号列表
                    for t in sorted(time_data.keys(), key=_sort_key):
                        entry = time_data[t]
                        cnt = entry['count']
                        interface_ids = entry['interface_ids']
                        tag = _warn_tag(t)
                        
                        # 基本信息行
                        lines.append(f"      {t}{action_word}{cnt}个{tag}")
                        
                        # 接口号详情（如果有）
                        if interface_ids:
                            # 将接口号用逗号分隔，每行最多显示10个
                            interface_str = "、".join(interface_ids)
                            lines.append(f"        接口号：{interface_str}")
                    
                    # 明确标注排序规则
                    if time_data:
                        lines.append("      （按时间排序）")

    # 仍保留一个分割线用于视觉提示（现在收发文函已并入上方层级明细）
    lines.append("")
    lines.append("================================")

    # 写入文件
    os.makedirs(folder_path, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))

    return output_path


