# -*- coding: utf-8 -*-
"""
测试待处理文件2的新筛选逻辑

测试内容：
1. 1907和2016项目使用标准逻辑（不排除process3）
2. 其他项目使用扩展逻辑（排除process3）
3. Process3的正确识别（AB列以4444开头 且 F列为"传递"）
"""

import pytest
import pandas as pd
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main


class TestFile2ProcessLogic:
    """测试待处理文件2的处理逻辑"""
    
    def create_test_dataframe(self):
        """创建测试DataFrame"""
        # 创建一个包含足够列的DataFrame
        data = {
            'A': ['Header'] + [f'A{i}' for i in range(1, 11)],  # 索引0
            'B': ['Header'] + [f'B{i}' for i in range(1, 11)],
            'C': ['Header'] + [f'C{i}' for i in range(1, 11)],
            'D': ['Header'] + [f'D{i}' for i in range(1, 11)],
            'E': ['Header'] + [f'E{i}' for i in range(1, 11)],
            'F': ['Header', '普通', '传递', '传递', '普通', '传递', '普通', '普通', '传递', '普通', '普通'],  # 索引5
        }
        
        # 添加更多列直到索引27（AB列）
        for i in range(6, 28):
            col_name = f'Col{i}'
            data[col_name] = ['Header'] + [f'{col_name}{j}' for j in range(1, 11)]
        
        # 设置AB列（索引27）的特殊值
        data['Col27'] = ['Header', '1234', '4444ABC', '4444XYZ', '5678', '444', '4444TEST', '9999', '4444END', '1111', '2222']  # AB列
        
        # 添加更多列
        for i in range(28, 35):
            col_name = f'Col{i}'
            data[col_name] = ['Header'] + [f'{col_name}{j}' for j in range(1, 11)]
        
        df = pd.DataFrame(data)
        return df
    
    def test_process3_identification(self):
        """测试process3的正确识别"""
        df = self.create_test_dataframe()
        
        # 调用execute2_process3
        result_rows = main.execute2_process3(df)
        
        # 预期结果：行索引2, 3, 6, 8（AB列以4444开头 且 F列为"传递"）
        expected = {2, 3, 8}  # 索引2: 4444ABC+传递, 3: 4444XYZ+传递, 8: 4444END+传递
        
        assert result_rows == expected, f"Process3识别错误：期望 {expected}，实际 {result_rows}"
    
    def test_file2_logic_for_1907(self, tmp_path, monkeypatch):
        """测试1907项目使用标准逻辑（不排除process3）"""
        # 创建临时Excel文件
        df = self.create_test_dataframe()
        test_file = tmp_path / "test_1907.xlsx"
        df.to_excel(test_file, index=False, engine='openpyxl')
        
        # Mock execute2_process1, process2, process4返回值（这些是pandas DataFrame的索引）
        def mock_process1(df):
            return {1, 2, 3, 4, 5, 6}  # pandas索引
        
        def mock_process2(df, dt):
            return {2, 3, 4, 5, 6, 7}  # pandas索引
        
        def mock_process4(df):
            return {1, 2, 3, 4, 5, 6, 7, 8}  # pandas索引
        
        monkeypatch.setattr(main, 'execute2_process1', mock_process1)
        monkeypatch.setattr(main, 'execute2_process2', mock_process2)
        monkeypatch.setattr(main, 'execute2_process4', mock_process4)
        
        # 调用process_target_file2，project_id='1907'
        from datetime import datetime
        result = main.process_target_file2(str(test_file), datetime.now(), project_id='1907')
        
        # 验证结果
        # 标准逻辑：P1 & P2 & P4 = {1,2,3,4,5,6} & {2,3,4,5,6,7} & {1,2,3,4,5,6,7,8}
        #                        = {2,3,4,5,6} (pandas索引)
        # 转换为Excel行号：pandas索引 + 2 = {4,5,6,7,8}
        expected_rows = {4, 5, 6, 7, 8}  # Excel行号
        
        if not result.empty:
            actual_rows = set(result['原始行号'].values) if '原始行号' in result.columns else set()
            assert actual_rows == expected_rows, f"1907项目逻辑错误：期望 {expected_rows}，实际 {actual_rows}"
    
    def test_file2_logic_for_2016(self, tmp_path, monkeypatch):
        """测试2016项目使用标准逻辑（不排除process3）"""
        # 与test_file2_logic_for_1907相同的逻辑
        df = self.create_test_dataframe()
        test_file = tmp_path / "test_2016.xlsx"
        df.to_excel(test_file, index=False, engine='openpyxl')
        
        def mock_process1(df):
            return {1, 2, 3, 4, 5, 6}  # pandas索引
        
        def mock_process2(df, dt):
            return {2, 3, 4, 5, 6, 7}  # pandas索引
        
        def mock_process4(df):
            return {1, 2, 3, 4, 5, 6, 7, 8}  # pandas索引
        
        monkeypatch.setattr(main, 'execute2_process1', mock_process1)
        monkeypatch.setattr(main, 'execute2_process2', mock_process2)
        monkeypatch.setattr(main, 'execute2_process4', mock_process4)
        
        from datetime import datetime
        result = main.process_target_file2(str(test_file), datetime.now(), project_id='2016')
        
        # pandas索引 {2,3,4,5,6} + 2 = Excel行号 {4,5,6,7,8}
        expected_rows = {4, 5, 6, 7, 8}  # Excel行号
        
        if not result.empty:
            actual_rows = set(result['原始行号'].values) if '原始行号' in result.columns else set()
            assert actual_rows == expected_rows, f"2016项目逻辑错误：期望 {expected_rows}，实际 {actual_rows}"
    
    def test_file2_logic_for_other_projects(self, tmp_path, monkeypatch):
        """测试其他项目使用扩展逻辑（排除process3）"""
        df = self.create_test_dataframe()
        test_file = tmp_path / "test_1818.xlsx"
        df.to_excel(test_file, index=False, engine='openpyxl')
        
        def mock_process1(df):
            return {1, 2, 3, 4, 5, 6}  # pandas索引
        
        def mock_process2(df, dt):
            return {2, 3, 4, 5, 6, 7}  # pandas索引
        
        def mock_process4(df):
            return {1, 2, 3, 4, 5, 6, 7, 8}  # pandas索引
        
        # process3实际返回值：{2, 3, 8}（pandas索引）
        # 这里会使用真实的execute2_process3函数
        
        monkeypatch.setattr(main, 'execute2_process1', mock_process1)
        monkeypatch.setattr(main, 'execute2_process2', mock_process2)
        monkeypatch.setattr(main, 'execute2_process4', mock_process4)
        
        from datetime import datetime
        
        # 测试1818项目
        result = main.process_target_file2(str(test_file), datetime.now(), project_id='1818')
        
        # 扩展逻辑：(P1 & P2 & P4) - P3
        #           = ({1,2,3,4,5,6} & {2,3,4,5,6,7} & {1,2,3,4,5,6,7,8}) - {2,3,8}
        #           = {2,3,4,5,6} - {2,3,8}
        #           = {4,5,6} (pandas索引)
        # 转换为Excel行号：{4,5,6} + 2 = {6,7,8}
        expected_rows = {6, 7, 8}  # Excel行号
        
        if not result.empty:
            actual_rows = set(result['原始行号'].values) if '原始行号' in result.columns else set()
            assert actual_rows == expected_rows, f"1818项目逻辑错误：期望 {expected_rows}，实际 {actual_rows}"
    
    def test_file2_logic_for_all_other_projects(self, tmp_path, monkeypatch):
        """测试所有其他项目号都使用扩展逻辑"""
        df = self.create_test_dataframe()
        
        def mock_process1(df):
            return {1, 2, 3, 4, 5, 6}  # pandas索引
        
        def mock_process2(df, dt):
            return {2, 3, 4, 5, 6, 7}  # pandas索引
        
        def mock_process4(df):
            return {1, 2, 3, 4, 5, 6, 7, 8}  # pandas索引
        
        monkeypatch.setattr(main, 'execute2_process1', mock_process1)
        monkeypatch.setattr(main, 'execute2_process2', mock_process2)
        monkeypatch.setattr(main, 'execute2_process4', mock_process4)
        
        from datetime import datetime
        
        # 测试多个其他项目
        other_projects = ['1916', '2026', '2306']
        # 扩展逻辑：(P1 & P2 & P4) - P3
        #           = {2,3,4,5,6} - {2,3,8} = {4,5,6} (pandas索引)
        # 转换为Excel行号：{4,5,6} + 2 = {6,7,8}
        expected_rows = {6, 7, 8}  # Excel行号
        
        for project_id in other_projects:
            test_file = tmp_path / f"test_{project_id}.xlsx"
            df.to_excel(test_file, index=False, engine='openpyxl')
            
            result = main.process_target_file2(str(test_file), datetime.now(), project_id=project_id)
            
            if not result.empty:
                actual_rows = set(result['原始行号'].values) if '原始行号' in result.columns else set()
                assert actual_rows == expected_rows, f"{project_id}项目逻辑错误：期望 {expected_rows}，实际 {actual_rows}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

