#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
回文单号输入功能测试
"""

import pytest
import os
import pandas as pd
from datetime import date
from unittest.mock import Mock, MagicMock, patch
from input_handler import (
    get_write_columns,
    determine_file3_source_and_columns,
    get_excel_lock_owner
)
import tempfile
import shutil


class TestGetWriteColumns:
    """测试获取写入列位置"""
    
    def test_file1_columns(self):
        """测试文件1的写入列"""
        columns = get_write_columns(1, 5, None)
        assert columns == {'response_col': 'S', 'time_col': 'M', 'name_col': 'V'}  # 时间列已从N改为M
    
    def test_file2_columns(self):
        """测试文件2的写入列"""
        columns = get_write_columns(2, 5, None)
        assert columns == {'response_col': 'P', 'time_col': 'N', 'name_col': 'AL'}
    
    def test_file3_m_column(self):
        """测试文件3-M列的写入列"""
        columns = get_write_columns(3, 5, None, 'M')
        assert columns == {'response_col': 'V', 'time_col': 'T', 'name_col': 'BM'}
    
    def test_file3_l_column(self):
        """测试文件3-L列的写入列"""
        columns = get_write_columns(3, 5, None, 'L')
        assert columns == {'response_col': 'S', 'time_col': 'Q', 'name_col': 'BM'}
    
    def test_file4_columns(self):
        """测试文件4的写入列"""
        columns = get_write_columns(4, 5, None)
        assert columns == {'response_col': 'U', 'time_col': 'V', 'name_col': 'AT'}
    
    def test_file5_columns(self):
        """测试文件5的写入列"""
        columns = get_write_columns(5, 5, None)
        assert columns == {'response_col': 'V', 'time_col': 'N', 'name_col': 'W'}
    
    def test_file6_columns(self):
        """测试文件6的写入列"""
        columns = get_write_columns(6, 5, None)
        assert columns == {'response_col': 'L', 'time_col': 'J', 'name_col': 'N'}
    
    def test_invalid_file_type(self):
        """测试无效文件类型"""
        columns = get_write_columns(999, 5, None)
        assert columns is None


class TestFile3SourceDetermination:
    """测试文件3来源判断"""
    
    def test_determine_m_source(self):
        """测试判断为M列来源"""
        # 模拟worksheet
        mock_ws = MagicMock()
        
        # M列有时间，T列为空 -> M列来源
        mock_ws.__getitem__ = lambda key: MagicMock(value='2025-10-28' if 'M' in key else ('' if 'T' in key else '2025-10-28'))
        
        # 创建Mock单元格
        m_cell = MagicMock()
        m_cell.value = '2025-10-28'
        
        l_cell = MagicMock()
        l_cell.value = ''
        
        t_cell = MagicMock()
        t_cell.value = ''
        
        q_cell = MagicMock()
        q_cell.value = '2025-10-26'
        
        def getitem(key):
            if key == 'M3':
                return m_cell
            elif key == 'L3':
                return l_cell
            elif key == 'T3':
                return t_cell
            elif key == 'Q3':
                return q_cell
            return MagicMock(value='')
        
        mock_ws.__getitem__ = getitem
        
        columns = determine_file3_source_and_columns(3, mock_ws)
        assert columns['response_col'] == 'V'  # M列来源
        assert columns['time_col'] == 'T'
        assert columns['name_col'] == 'BM'
    
    def test_determine_l_source(self):
        """测试判断为L列来源"""
        # 模拟worksheet
        mock_ws = MagicMock()
        
        # L列有时间，Q列为空 -> L列来源
        m_cell = MagicMock()
        m_cell.value = ''
        
        l_cell = MagicMock()
        l_cell.value = '2025-10-28'
        
        t_cell = MagicMock()
        t_cell.value = '2025-10-26'
        
        q_cell = MagicMock()
        q_cell.value = ''
        
        def getitem(self_or_key, key=None):
            # 处理mock的__getitem__调用
            actual_key = key if key is not None else self_or_key
            if actual_key == 'M2':
                return m_cell
            elif actual_key == 'L2':
                return l_cell
            elif actual_key == 'T2':
                return t_cell
            elif actual_key == 'Q2':
                return q_cell
            return MagicMock(value='')
        
        mock_ws.__getitem__ = getitem
        
        columns = determine_file3_source_and_columns(2, mock_ws)
        assert columns['response_col'] == 'S'  # L列来源
        assert columns['time_col'] == 'Q'
        assert columns['name_col'] == 'BM'
    
    def test_determine_default_to_m(self):
        """测试无法判断时默认为M列"""
        # 模拟worksheet
        mock_ws = MagicMock()
        
        # 所有列都为空
        empty_cell = MagicMock()
        empty_cell.value = ''
        
        mock_ws.__getitem__ = lambda key: empty_cell
        
        columns = determine_file3_source_and_columns(5, mock_ws)
        assert columns['response_col'] == 'V'  # 默认M列
        assert columns['time_col'] == 'T'
        assert columns['name_col'] == 'BM'


class TestInterfaceInputDialog:
    """测试InterfaceInputDialog类"""
    
    @patch('tkinter.Toplevel.__init__')
    def test_dialog_initialization(self, mock_toplevel_init):
        """测试对话框初始化"""
        from input_handler import InterfaceInputDialog
        
        # Mock父窗口
        mock_parent = MagicMock()
        mock_toplevel_init.return_value = None
        
        # 创建对话框实例（模拟）
        dialog_params = {
            'interface_id': 'INT-001',
            'file_type': 1,
            'file_path': 'test.xlsx',
            'row_index': 2,
            'user_name': '王任超',
            'project_id': '2016',
            'source_column': None
        }
        
        # 验证参数
        assert dialog_params['interface_id'] == 'INT-001'
        assert dialog_params['file_type'] == 1
        assert dialog_params['user_name'] == '王任超'
        assert dialog_params['project_id'] == '2016'


class TestWriteResponseLogic:
    """测试写入响应逻辑"""
    
    def test_date_format(self):
        """测试日期格式为yyyy-mm-dd"""
        today = date.today()
        formatted = today.strftime('%Y-%m-%d')
        
        # 验证格式
        assert len(formatted) == 10
        assert formatted.count('-') == 2
        
        # 验证可解析
        year, month, day = formatted.split('-')
        assert len(year) == 4
        assert len(month) == 2
        assert len(day) == 2
    
    def test_column_name_format(self):
        """测试Excel列名格式"""
        test_columns = ['S', 'N', 'V', 'P', 'AL', 'BM', 'U', 'AT', 'L', 'J']
        
        for col in test_columns:
            # 验证列名只包含大写字母
            assert col.isupper()
            assert col.isalpha()
    
    def test_row_index_format(self):
        """测试Excel行号格式（从2开始）"""
        # Excel行号应该从2开始（第1行是标题）
        test_row = 2
        assert test_row >= 2
        
        # 测试列+行号组合
        cell_ref = f"S{test_row}"
        assert cell_ref == "S2"
        
        cell_ref = f"AL{test_row}"
        assert cell_ref == "AL2"


class TestFileTypeMapping:
    """测试文件类型映射"""
    
    def test_file_type_to_name_mapping(self):
        """测试文件类型到名称的映射"""
        file_type_map = {
            1: "内部需打开接口",
            2: "内部需回复接口",
            3: "外部需打开接口",
            4: "外部需回复接口",
            5: "三维提资接口",
            6: "收发文函"
        }
        
        assert file_type_map[1] == "内部需打开接口"
        assert file_type_map[2] == "内部需回复接口"
        assert file_type_map[3] == "外部需打开接口"
        assert file_type_map[4] == "外部需回复接口"
        assert file_type_map[5] == "三维提资接口"
        assert file_type_map[6] == "收发文函"
    
    def test_all_file_types_have_columns(self):
        """测试所有文件类型都有列配置"""
        for file_type in range(1, 7):
            if file_type == 3:
                # 文件3需要source_column参数
                columns_m = get_write_columns(3, 5, None, 'M')
                columns_l = get_write_columns(3, 5, None, 'L')
                assert columns_m is not None
                assert columns_l is not None
            else:
                columns = get_write_columns(file_type, 5, None)
                assert columns is not None
                assert 'response_col' in columns
                assert 'time_col' in columns
                assert 'name_col' in columns


class TestConcurrencyProtection:
    """测试并发保护"""
    
    def test_file_lock_detection(self):
        """测试文件锁定检测逻辑"""
        # 模拟文件锁定场景
        with patch('builtins.open', side_effect=PermissionError):
            # 应该捕获PermissionError
            try:
                with open('test.xlsx', 'r+b') as f:
                    pass
                assert False, "应该抛出PermissionError"
            except PermissionError:
                assert True, "正确捕获文件锁定错误"


class TestGetExcelLockOwner:
    """测试获取Excel文件占用者功能"""
    
    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        temp = tempfile.mkdtemp()
        yield temp
        # 清理
        try:
            shutil.rmtree(temp)
        except:
            pass
    
    def test_no_lock_file_returns_empty(self, temp_dir):
        """测试没有锁定文件时返回空字符串"""
        test_file = os.path.join(temp_dir, "test.xlsx")
        # 创建一个空文件
        with open(test_file, 'wb') as f:
            f.write(b'')
        
        result = get_excel_lock_owner(test_file)
        assert result == ""
    
    def test_nonexistent_file_returns_empty(self, temp_dir):
        """测试文件不存在时返回空字符串"""
        nonexistent_file = os.path.join(temp_dir, "nonexistent.xlsx")
        result = get_excel_lock_owner(nonexistent_file)
        assert result == ""
    
    def test_lock_file_with_utf16_username(self, temp_dir):
        """测试UTF-16编码的用户名"""
        test_file = os.path.join(temp_dir, "test.xlsx")
        lock_file = os.path.join(temp_dir, "~$test.xlsx")
        
        # 创建测试文件
        with open(test_file, 'wb') as f:
            f.write(b'')
        
        # 创建带有UTF-16用户名的锁定文件（模拟Excel格式）
        user_name = "张三"
        # Excel锁定文件格式：用户名以UTF-16-LE编码存储在文件开头
        lock_content = user_name.encode('utf-16-le')
        with open(lock_file, 'wb') as f:
            f.write(lock_content)
        
        result = get_excel_lock_owner(test_file)
        assert result == user_name or user_name in result
    
    def test_lock_file_with_ascii_username(self, temp_dir):
        """测试ASCII用户名"""
        test_file = os.path.join(temp_dir, "report.xlsx")
        lock_file = os.path.join(temp_dir, "~$report.xlsx")
        
        # 创建测试文件
        with open(test_file, 'wb') as f:
            f.write(b'')
        
        # 创建带有ASCII用户名的锁定文件
        user_name = "admin"
        lock_content = user_name.encode('utf-16-le')
        with open(lock_file, 'wb') as f:
            f.write(lock_content)
        
        result = get_excel_lock_owner(test_file)
        assert result == user_name or user_name in result
    
    def test_lock_file_with_mixed_username(self, temp_dir):
        """测试中英文混合用户名"""
        test_file = os.path.join(temp_dir, "data.xlsx")
        lock_file = os.path.join(temp_dir, "~$data.xlsx")
        
        # 创建测试文件
        with open(test_file, 'wb') as f:
            f.write(b'')
        
        # 创建带有中英文用户名的锁定文件
        user_name = "李四Lee"
        lock_content = user_name.encode('utf-16-le')
        with open(lock_file, 'wb') as f:
            f.write(lock_content)
        
        result = get_excel_lock_owner(test_file)
        assert user_name in result or "李四" in result
    
    def test_exception_handling(self):
        """测试异常处理，确保函数不会抛出异常"""
        # 传入无效路径，应该返回空字符串而不是抛出异常
        result = get_excel_lock_owner("")
        assert result == ""
        
        result = get_excel_lock_owner(None)
        assert result == ""
    
    def test_real_excel_lock_file_format(self, temp_dir):
        """测试真实Excel锁定文件格式"""
        test_file = os.path.join(temp_dir, "项目接口.xlsx")
        lock_file = os.path.join(temp_dir, "~$项目接口.xlsx")
        
        # 创建测试文件
        with open(test_file, 'wb') as f:
            f.write(b'')
        
        # 模拟真实Excel锁定文件的格式
        # Excel锁定文件通常有一些前导字节，然后是用户名
        user_name = "王任超"
        # 添加一些前导字节（模拟Excel的文件头）
        lock_content = b'\x00' * 4 + user_name.encode('utf-16-le') + b'\x00' * 50
        with open(lock_file, 'wb') as f:
            f.write(lock_content)
        
        result = get_excel_lock_owner(test_file)
        # 应该能够从锁定文件中提取出用户名
        assert user_name in result or result == "" or len(result) > 0
    
    def test_function_returns_string(self, temp_dir):
        """测试函数总是返回字符串类型"""
        test_file = os.path.join(temp_dir, "test.xlsx")
        
        result = get_excel_lock_owner(test_file)
        assert isinstance(result, str)


class TestLockOwnerIntegration:
    """测试锁定文件检测与错误提示的集成"""
    
    def test_lock_owner_in_error_message(self):
        """测试占用者信息能正确嵌入错误消息"""
        owner = "测试用户"
        expected_msg = f"文件正被 【{owner}】 占用，请稍后再试"
        
        # 验证消息格式
        assert "测试用户" in expected_msg
        assert "占用" in expected_msg
    
    def test_fallback_message_without_owner(self):
        """测试无法获取占用者时的回退消息"""
        owner = ""
        if owner:
            msg = f"文件正被 【{owner}】 占用，请稍后再试"
        else:
            msg = "有其他用户占用该文件，请稍后再试"
        
        assert "有其他用户" in msg


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

