from base import select_latest_source_files_per_project


def test_select_latest_file1_prefers_latest_timestamp_in_filename():
    files = [
        (r"E:\program\接口筛选\测试文件\2016按项目导出IDI手册2025-08-01-09_00_00.xlsx", "2016"),
        (r"E:\program\接口筛选\测试文件\2016按项目导出IDI手册2025-08-01-17_55_52.xlsx", "2016"),
        (r"E:\program\接口筛选\测试文件\2016按项目导出IDI手册2025-07-31-23_59_59.xlsx", "2016"),
    ]
    filtered, ignored = select_latest_source_files_per_project(1, files, "待处理文件1")
    assert len(filtered) == 1
    assert filtered[0][0].endswith(r"2016按项目导出IDI手册2025-08-01-17_55_52.xlsx")
    assert len(ignored) == 2


def test_select_latest_file2_3_4_by_yyyymmdd_suffix():
    f2 = [
        (r"E:\program\接口筛选\测试文件\内部接口信息单报表190720251126.xlsx", "1907"),
        (r"E:\program\接口筛选\测试文件\内部接口信息单报表190720251203.xlsx", "1907"),
    ]
    f3 = [
        (r"E:\program\接口筛选\测试文件\外部接口ICM报表190720251126.xlsx", "1907"),
        (r"E:\program\接口筛选\测试文件\外部接口ICM报表190720251203.xlsx", "1907"),
    ]
    f4 = [
        (r"E:\program\接口筛选\测试文件\外部接口单报表190720251126.xlsx", "1907"),
        (r"E:\program\接口筛选\测试文件\外部接口单报表190720251203.xlsx", "1907"),
    ]

    filtered2, _ = select_latest_source_files_per_project(2, f2, "待处理文件2")
    filtered3, _ = select_latest_source_files_per_project(3, f3, "待处理文件3")
    filtered4, _ = select_latest_source_files_per_project(4, f4, "待处理文件4")

    assert filtered2[0][0].endswith(r"内部接口信息单报表190720251203.xlsx")
    assert filtered3[0][0].endswith(r"外部接口ICM报表190720251203.xlsx")
    assert filtered4[0][0].endswith(r"外部接口单报表190720251203.xlsx")


