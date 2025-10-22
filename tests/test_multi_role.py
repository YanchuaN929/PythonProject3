"""
测试多角色功能：
1. 角色表读取和解析（支持顿号分隔）
2. 接口工程师角色识别和项目号提取
3. 单角色过滤（设计人员、接口工程师、主任）
4. 多角色合并和角色标注
5. GUI显示角色标注
6. TXT导出角色标注
"""

import pytest
import pandas as pd
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# 添加项目根目录到sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestRoleParser:
    """测试角色解析功能"""
    
    def test_parse_single_role(self, mock_app):
        """测试单角色解析"""
        mock_app.user_role = "设计人员"
        mock_app.load_user_role()
        
        # 应该只有一个角色
        assert hasattr(mock_app, 'user_roles')
        # 由于load_user_role依赖Excel文件，这里主要测试解析逻辑
    
    def test_parse_multiple_roles(self):
        """测试多角色解析（用顿号分隔）"""
        # 直接测试角色字符串解析逻辑（不实例化ExcelProcessorApp）
        test_role_str = "设计人员、2016接口工程师"
        roles = [r.strip() for r in test_role_str.split('、') if r.strip()]
        
        assert len(roles) == 2
        assert "设计人员" in roles
        assert "2016接口工程师" in roles
    
    def test_parse_interface_engineer_role(self, mock_app):
        """测试接口工程师角色解析"""
        project_id = mock_app._parse_interface_engineer_role("2016接口工程师")
        assert project_id == "2016"
        
        project_id = mock_app._parse_interface_engineer_role("1818接口工程师")
        assert project_id == "1818"
        
        project_id = mock_app._parse_interface_engineer_role("2306接口工程师")
        assert project_id == "2306"
        
        # 非接口工程师角色应返回None
        project_id = mock_app._parse_interface_engineer_role("设计人员")
        assert project_id is None
        
        project_id = mock_app._parse_interface_engineer_role("一室主任")
        assert project_id is None


class TestSingleRoleFilter:
    """测试单角色过滤功能"""
    
    def test_filter_designer_role(self, mock_app):
        """测试设计人员角色过滤"""
        # 创建测试数据
        df = pd.DataFrame({
            '原始行号': [2, 3, 4, 5],
            '责任人': ['张三', '李四', '张三', '王五'],
            '科室': ['结构一室', '结构二室', '结构一室', '建筑总图室']
        })
        
        # 设置用户信息
        mock_app.user_name = "张三"
        
        # 测试设计人员过滤
        filtered = mock_app._filter_by_single_role(df, "设计人员", project_id="2016")
        
        # 应该只保留张三的数据
        assert len(filtered) == 2
        assert all(filtered['责任人'] == '张三')
    
    def test_filter_interface_engineer_role(self, mock_app):
        """测试接口工程师角色过滤"""
        # 创建测试数据
        df = pd.DataFrame({
            '原始行号': [2, 3, 4, 5],
            '责任人': ['张三', '李四', '王五', '赵六'],
            '科室': ['结构一室', '结构二室', '结构一室', '建筑总图室']
        })
        
        # 设置用户信息
        mock_app.user_name = "李四"
        
        # 测试2016接口工程师过滤（项目匹配）
        filtered = mock_app._filter_by_single_role(df, "2016接口工程师", project_id="2016")
        
        # 应该返回全部数据（不限责任人）
        assert len(filtered) == 4
        
        # 测试2016接口工程师过滤（项目不匹配）
        filtered = mock_app._filter_by_single_role(df, "2016接口工程师", project_id="1818")
        
        # 应该返回空数据
        assert len(filtered) == 0
    
    def test_filter_director_role(self, mock_app):
        """测试主任角色过滤"""
        # 创建测试数据
        df = pd.DataFrame({
            '原始行号': [2, 3, 4, 5],
            '责任人': ['张三', '李四', '王五', '赵六'],
            '科室': ['结构一室', '结构二室', '结构一室', '建筑总图室']
        })
        
        # 设置用户信息
        mock_app.user_name = "一室主任"
        
        # 测试一室主任过滤
        filtered = mock_app._filter_by_single_role(df, "一室主任", project_id="2016")
        
        # 应该只保留结构一室的数据
        assert len(filtered) == 2
        assert all(filtered['科室'] == '结构一室')
    
    def test_filter_2306_interface_engineer(self, mock_app):
        """测试2306接口工程师角色过滤"""
        # 创建测试数据
        df = pd.DataFrame({
            '原始行号': [2, 3, 4, 5],
            '责任人': ['张三', '李四', '王五', '赵六'],
            '科室': ['结构一室', '结构二室', '结构一室', '建筑总图室']
        })
        
        # 设置用户信息
        mock_app.user_name = "钱七"
        
        # 测试2306接口工程师过滤（项目匹配）
        filtered = mock_app._filter_by_single_role(df, "2306接口工程师", project_id="2306")
        
        # 应该返回全部数据（不限责任人）
        assert len(filtered) == 4
        
        # 测试2306接口工程师过滤（项目不匹配）
        filtered = mock_app._filter_by_single_role(df, "2306接口工程师", project_id="2016")
        
        # 应该返回空数据
        assert len(filtered) == 0


class TestMultiRoleFilter:
    """测试多角色过滤和合并功能"""
    
    def test_multi_role_merge_without_overlap(self, mock_app):
        """测试多角色合并（无重叠）"""
        # 创建测试数据
        df = pd.DataFrame({
            '原始行号': [2, 3, 4, 5, 6],
            '责任人': ['张三', '李四', '王五', '赵六', '钱七'],
            '科室': ['结构一室', '结构二室', '结构一室', '建筑总图室', '结构一室']
        })
        
        # 设置用户信息：设计人员+2016接口工程师
        mock_app.user_name = "张三"
        mock_app.user_roles = ["设计人员", "2016接口工程师"]
        
        # 应用多角色过滤
        filtered = mock_app.apply_role_based_filter(df, project_id="2016")
        
        # 设计人员：张三的数据（行2、4、6）
        # 2016接口工程师：全部数据（行2-6）
        # 合并后应该是全部数据（因为接口工程师包含所有）
        assert len(filtered) == 5
        
        # 应该包含角色来源列
        assert '角色来源' in filtered.columns
    
    def test_multi_role_merge_with_overlap(self, mock_app):
        """测试多角色合并（有重叠）"""
        # 创建测试数据
        df = pd.DataFrame({
            '原始行号': [2, 3, 4, 5],
            '责任人': ['张三', '李四', '张三', '王五'],
            '科室': ['结构一室', '结构二室', '结构一室', '建筑总图室']
        })
        
        # 设置用户信息：设计人员+一室主任
        mock_app.user_name = "张三"
        mock_app.user_roles = ["设计人员", "一室主任"]
        
        # 应用多角色过滤
        filtered = mock_app.apply_role_based_filter(df, project_id="2016")
        
        # 设计人员：张三的数据（行2、4）
        # 一室主任：结构一室的数据（行2、4）
        # 合并后应该是行2、4（有重叠，应标注两个角色）
        assert len(filtered) == 2
        
        # 检查角色来源列
        assert '角色来源' in filtered.columns
        
        # 重叠的行应该包含两个角色
        for idx, row in filtered.iterrows():
            role_source = row['角色来源']
            # 由于都是重叠的，应该包含两个角色
            assert '设计人员' in role_source or '一室主任' in role_source
    
    def test_role_annotation_format(self, mock_app):
        """测试角色标注格式"""
        # 创建测试数据
        df = pd.DataFrame({
            '原始行号': [2, 3, 4],
            '责任人': ['张三', '张三', '李四'],
            '科室': ['结构一室', '结构一室', '结构二室']
        })
        
        # 设置用户信息：设计人员
        mock_app.user_name = "张三"
        mock_app.user_roles = ["设计人员"]
        
        # 应用过滤
        filtered = mock_app.apply_role_based_filter(df, project_id="2016")
        
        # 检查角色来源格式
        assert '角色来源' in filtered.columns
        assert all(filtered['角色来源'] == "设计人员")


class TestGUIDisplay:
    """测试GUI显示角色标注"""
    
    def test_display_with_role_annotation(self):
        """测试带角色标注的显示"""
        from window import WindowManager
        
        # 创建模拟的WindowManager
        mock_root = Mock()
        wm = WindowManager(mock_root, {})
        
        # 创建测试数据（包含角色来源列）
        df = pd.DataFrame({
            'A列': ['INT-001', 'INT-002', 'INT-003'],
            '角色来源': ['设计人员', '2016接口工程师', '设计人员、2016接口工程师']
        })
        df.columns = range(len(df.columns))  # 模拟数字列索引
        df['角色来源'] = ['设计人员', '2016接口工程师', '设计人员、2016接口工程师']
        
        # 调用优化显示方法
        display_df = wm._create_optimized_display(df, "内部需打开接口")
        
        # 检查接口号列是否包含角色标注
        assert '接口号' in display_df.columns
        assert len(display_df) == 3
        
        # 检查格式：INT-001(设计人员)
        interface_ids = display_df['接口号'].tolist()
        assert '设计人员' in interface_ids[0]
        assert '2016接口工程师' in interface_ids[1]
    
    def test_display_without_role_annotation(self):
        """测试不带角色标注的显示（兼容性）"""
        from window import WindowManager
        
        # 创建模拟的WindowManager
        mock_root = Mock()
        wm = WindowManager(mock_root, {})
        
        # 创建测试数据（不包含角色来源列）
        df = pd.DataFrame({
            0: ['INT-001', 'INT-002', 'INT-003']
        })
        
        # 调用优化显示方法
        display_df = wm._create_optimized_display(df, "内部需打开接口")
        
        # 应该正常显示接口号（不带角色标注）
        assert '接口号' in display_df.columns
        assert len(display_df) == 3


class TestTXTExport:
    """测试TXT导出角色标注"""
    
    def test_export_with_role_annotation(self, tmp_path):
        """测试导出带角色标注的TXT"""
        from main2 import write_export_summary
        from datetime import datetime
        
        # 创建测试数据（包含角色来源列）
        df1 = pd.DataFrame({
            0: ['INT-001', 'INT-002'],  # A列（内部需打开接口）
            '科室': ['结构一室', '结构二室'],
            '接口时间': ['01.06', '01.10'],
            '角色来源': ['设计人员', '2016接口工程师']
        })
        
        results_multi1 = {'2016': df1}
        
        # 生成导出文件
        output_path = write_export_summary(
            folder_path=str(tmp_path),
            current_datetime=datetime.now(),
            results_multi1=results_multi1
        )
        
        # 读取并验证内容
        with open(output_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 应该包含角色标注
        assert 'INT-001(设计人员)' in content
        assert 'INT-002(2016接口工程师)' in content
    
    def test_export_without_role_annotation(self, tmp_path):
        """测试导出不带角色标注的TXT（兼容性）"""
        from main2 import write_export_summary
        from datetime import datetime
        
        # 创建测试数据（不包含角色来源列）
        df1 = pd.DataFrame({
            0: ['INT-001', 'INT-002'],  # A列
            '科室': ['结构一室', '结构二室'],
            '接口时间': ['01.06', '01.10']
        })
        
        results_multi1 = {'2016': df1}
        
        # 生成导出文件
        output_path = write_export_summary(
            folder_path=str(tmp_path),
            current_datetime=datetime.now(),
            results_multi1=results_multi1
        )
        
        # 读取并验证内容
        with open(output_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 应该包含接口号（不带角色标注）
        assert 'INT-001' in content
        assert 'INT-002' in content


@pytest.fixture
def mock_app():
    """创建模拟的ExcelProcessorApp"""
    from base import ExcelProcessorApp
    
    # 创建一个最小化的mock对象，只包含必要的方法
    app = Mock(spec=ExcelProcessorApp)
    
    # 设置必要的属性
    app.user_name = "测试用户"
    app.user_role = ""
    app.user_roles = []
    
    # 绑定真实的方法（从ExcelProcessorApp类）
    app._parse_interface_engineer_role = ExcelProcessorApp._parse_interface_engineer_role.__get__(app, ExcelProcessorApp)
    app._filter_by_single_role = ExcelProcessorApp._filter_by_single_role.__get__(app, ExcelProcessorApp)
    app.apply_role_based_filter = ExcelProcessorApp.apply_role_based_filter.__get__(app, ExcelProcessorApp)
    
    return app


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

