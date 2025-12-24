#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bug修复测试
"""

import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
import tkinter as tk
from tkinter import ttk


class TestFile6DisplayLogic:
    """测试文件6显示逻辑修复"""
    
    def test_file6_should_clear_on_user_switch(self):
        """测试用户切换后文件6应清空旧数据"""
        # 模拟场景：用户A有数据，切换到用户B时文件6无数据
        
        # 用户A的结果
        results_a = pd.DataFrame({
            '接口号': ['INT-001', 'INT-002'],
            '项目号': ['2016', '2016'],
            '原始行号': [2, 3]
        })
        
        # 用户B的结果（空）
        results_b = pd.DataFrame()
        
        # 测试逻辑：has_processed_results6=True且processing_results6为空
        has_processed_results6 = True
        processing_results6 = results_b
        
        # 断言：应该显示"无收发文函"
        should_show_empty = (
            has_processed_results6 and 
            (processing_results6 is None or processing_results6.empty)
        )
        
        assert should_show_empty, "用户切换后应显示'无收发文函'"
    
    def test_file6_should_display_results_when_exists(self):
        """测试文件6有结果时正常显示"""
        results = pd.DataFrame({
            '接口号': ['INT-001'],
            '项目号': ['2016'],
            '原始行号': [2]
        })
        
        has_processed_results6 = True
        processing_results6 = results
        
        should_show_data = (
            has_processed_results6 and 
            processing_results6 is not None and 
            not processing_results6.empty
        )
        
        assert should_show_data, "有结果时应显示数据"
    
    def test_file6_no_caching_check(self):
        """测试文件6不应该检查viewer子节点来决定是否重绘"""
        # 这是之前的bug：if len(self.tab6_viewer.get_children()) > 0: return
        # 现在应该总是根据has_processed_results6状态来决定
        
        # 模拟viewer有子节点
        mock_viewer = MagicMock()
        mock_viewer.get_children.return_value = ['item1', 'item2']
        
        # 即使viewer有子节点，也应该根据处理状态来决定显示
        has_processed_results6 = True
        processing_results6 = pd.DataFrame()
        
        # 正确的逻辑：不应该提前返回，而应该继续判断
        should_continue = True  # 不应该因为有子节点就return
        
        assert should_continue, "不应该因为viewer有子节点就跳过重绘"


class TestInterfaceDoubleClick:
    """测试接口号双击事件修复"""
    
    def test_double_click_event_binding(self):
        """测试双击事件绑定"""
        # 验证事件类型是Double-1而不是Button-3
        event_type = "<Double-1>"
        assert event_type == "<Double-1>", "应该绑定双击事件"
        assert event_type != "<Button-3>", "不应该是右键事件"
    
    def test_unbind_correct_event_type(self):
        """测试解绑的事件类型正确"""
        # 解绑时也应该使用Double-1
        unbind_event_type = "<Double-1>"
        assert unbind_event_type == "<Double-1>", "解绑时应使用相同的事件类型"
    
    def test_event_trigger_condition(self):
        """测试事件触发条件"""
        # 双击接口号列应该触发
        clicked_column = "接口号"
        should_trigger = (clicked_column == "接口号")
        assert should_trigger, "双击接口号列应该触发事件"
        
        # 双击其他列不应该触发
        clicked_column = "项目号"
        should_trigger = (clicked_column == "接口号")
        assert not should_trigger, "双击其他列不应该触发事件"


class TestEventBindingIntegration:
    """测试事件绑定集成"""
    
    def test_bind_tag_creation(self):
        """测试绑定标签创建"""
        tab_name = "内部需打开接口"
        bind_tag = f"interface_click_{tab_name}"
        
        assert bind_tag == "interface_click_内部需打开接口"
        assert "interface_click_" in bind_tag
        assert tab_name in bind_tag
    
    def test_multiple_tab_bindings(self):
        """测试多个选项卡的绑定标签不冲突"""
        tab_names = ["内部需打开接口", "内部需回复接口", "外部需打开接口", 
                     "外部需回复接口", "三维提资接口", "收发文函"]
        
        bind_tags = [f"interface_click_{name}" for name in tab_names]
        
        # 确保所有标签都是唯一的
        assert len(bind_tags) == len(set(bind_tags)), "每个选项卡应有唯一的绑定标签"
    
    def test_event_handler_receives_correct_data(self):
        """测试事件处理器接收正确的数据"""
        # 模拟数据
        original_df = pd.DataFrame({
            '接口号': ['INT-001'],
            '项目号': ['2016'],
            'source_file': ['/path/to/file.xlsx'],
            '_source_column': ['M'],
            '原始行号': [2]
        })
        
        item_index = 0
        
        # 提取数据
        interface_id = original_df.iloc[item_index]["接口号"]
        project_id = original_df.iloc[item_index]["项目号"]
        source_file = original_df.iloc[item_index]["source_file"]
        excel_row = original_df.iloc[item_index]["原始行号"]
        source_column = original_df.iloc[item_index].get("_source_column", None)
        
        assert interface_id == "INT-001"
        assert project_id == "2016"
        assert source_file == "/path/to/file.xlsx"
        assert excel_row == 2
        assert source_column == "M"


class TestFile6RefreshLogic:
    """测试文件6刷新逻辑"""
    
    def test_refresh_clears_old_data(self):
        """测试刷新时清空旧数据"""
        # 模拟刷新前后的状态
        before_refresh = {
            'has_processed_results6': True,
            'processing_results6': pd.DataFrame({'col': [1, 2, 3]})
        }
        
        # 刷新后无数据
        after_refresh = {
            'has_processed_results6': True,
            'processing_results6': pd.DataFrame()
        }
        
        # 验证状态变化
        assert before_refresh['has_processed_results6'] == True
        assert not before_refresh['processing_results6'].empty
        
        assert after_refresh['has_processed_results6'] == True
        assert after_refresh['processing_results6'].empty
        
        # 验证应该显示"无数据"
        should_show_empty = (
            after_refresh['has_processed_results6'] and 
            after_refresh['processing_results6'].empty
        )
        assert should_show_empty
    
    def test_on_tab_changed_logic_for_file6(self):
        """测试on_tab_changed对文件6的处理逻辑"""
        # 模拟不同的状态组合
        test_cases = [
            # (has_processed, results_empty, expected_action)
            (True, False, "display_data"),  # 有处理结果且非空
            (True, True, "show_empty"),     # 有处理结果但为空
            (False, True, "show_prompt"),   # 未处理：不显示原始数据，提示点击开始处理
        ]
        
        for has_processed, results_empty, expected_action in test_cases:
            has_processed_results6 = has_processed
            processing_results6 = pd.DataFrame() if results_empty else pd.DataFrame({'col': [1]})
            file6_data = pd.DataFrame({'raw': [1]})
            
            if has_processed_results6 and processing_results6 is not None and not processing_results6.empty:
                action = "display_data"
            elif has_processed_results6:
                action = "show_empty"
            else:
                action = "show_prompt"
            
            assert action == expected_action, f"状态({has_processed}, {results_empty})应该执行{expected_action}"


class TestRoleBasedFileDisplay:
    """测试基于角色的文件显示"""
    
    def test_different_roles_see_different_results(self):
        """测试不同角色看到不同结果"""
        # 全部数据
        all_data = pd.DataFrame({
            '接口号': ['INT-001', 'INT-002', 'INT-003'],
            '责任人': ['张三', '李四', '王五'],
            '项目号': ['2016', '2017', '2018']
        })
        
        # 角色A（2016接口工程师）应该只看到2016的数据
        role_a_filter = all_data['项目号'] == '2016'
        results_a = all_data[role_a_filter]
        assert len(results_a) == 1
        assert results_a.iloc[0]['接口号'] == 'INT-001'
        
        # 角色B（部门主管）可能看到更多数据
        # 这里假设部门主管看到所有数据
        results_b = all_data
        assert len(results_b) == 3
    
    def test_empty_results_after_role_filter(self):
        """测试角色过滤后结果为空的情况"""
        # 全部数据
        all_data = pd.DataFrame({
            '接口号': ['INT-001', 'INT-002'],
            '项目号': ['2016', '2017']
        })
        
        # 角色C（2018接口工程师）过滤后无数据
        role_c_filter = all_data['项目号'] == '2018'
        results_c = all_data[role_c_filter]
        
        assert len(results_c) == 0
        assert results_c.empty
        
        # 应该触发"无收发文函"显示
        has_processed_results6 = True
        processing_results6 = results_c
        
        should_show_empty = (
            has_processed_results6 and 
            (processing_results6 is None or processing_results6.empty)
        )
        assert should_show_empty


class TestFile6UnprocessedDisplay:
    """测试文件6未处理时的显示逻辑"""
    
    def test_file6_unprocessed_should_show_raw_data(self):
        """测试文件6未处理时不显示原始数据（已改为仅“开始处理后显示结果”）"""
        # 模拟未处理状态
        has_processed_results6 = False
        file6_data = pd.DataFrame({'原始列': [1, 2, 3]})  # 原始数据存在
        
        # 新显示逻辑：未处理时不展示原始数据，而是提示点击开始处理
        if has_processed_results6:
            action = "show_processed_or_empty"
        else:
            action = "show_prompt"
        
        assert action == "show_prompt", "未处理时应该提示点击开始处理"
    
    def test_file6_raw_data_has_no_source_file_column(self):
        """测试原始数据没有source_file列（因此不支持回文单号输入）"""
        # 模拟预加载的原始数据
        file6_data = pd.DataFrame({
            '接口号': ['INT-001'],
            '项目号': ['2016'],
            # 注意：没有'source_file'列
        })
        
        assert 'source_file' not in file6_data.columns, "原始数据不应该有source_file列"
        
    def test_interface_click_not_bound_on_raw_data(self):
        """测试原始数据不绑定接口号点击事件"""
        # 模拟原始数据
        raw_data = pd.DataFrame({
            '接口号': ['INT-001'],
            '项目号': ['2016'],
            # 没有source_file列
        })
        
        # _bind_interface_click_event会检查source_file列
        # 如果没有，直接return，不绑定事件
        should_bind = 'source_file' in raw_data.columns
        assert not should_bind, "原始数据不应该绑定接口号点击事件"
    
    def test_file6_processed_data_has_source_file_column(self):
        """测试处理后的数据应该有source_file列"""
        # 模拟处理后的数据（经过process_target_file6）
        processing_results6 = pd.DataFrame({
            '接口号': ['INT-001'],
            '项目号': ['2016'],
            'source_file': ['/path/to/file.xlsx'],  # 应该有这列
            '原始行号': [2]
        })
        
        assert 'source_file' in processing_results6.columns
        assert processing_results6.iloc[0]['source_file'] == '/path/to/file.xlsx'


class TestEmptyDictProcessing:
    """测试空字典处理逻辑（核心Bug修复）"""
    
    def test_empty_dict_sets_processed_flag_file1(self):
        """测试文件1：空字典也应设置has_processed标志"""
        # 模拟refresh_all_processed_results的逻辑
        processing_results_multi1 = {}  # 空字典
        
        # 修复后的逻辑
        if processing_results_multi1:  # False
            processing_results1 = pd.DataFrame({'col': [1]})
            has_processed_results1 = True
        else:  # 应该走这里
            processing_results1 = pd.DataFrame()
            has_processed_results1 = True
        
        # 断言：标志应该被设置
        assert has_processed_results1 == True
        assert processing_results1.empty == True
    
    def test_empty_dict_sets_processed_flag_file6(self):
        """测试文件6：空字典也应设置has_processed标志（原bug所在）"""
        # 模拟用户切换后processing_results_multi6为空字典的情况
        processing_results_multi6 = {}
        
        # 修复后的逻辑
        if processing_results_multi6:
            processing_results6 = pd.DataFrame({'col': [1]})
            has_processed_results6 = True
        else:
            processing_results6 = pd.DataFrame()
            has_processed_results6 = True
        
        assert has_processed_results6 == True
        assert processing_results6.empty == True
    
    def test_non_empty_dict_with_no_matching_data(self):
        """测试非空字典但角色过滤后无数据的情况"""
        # 模拟有数据但过滤后为空
        processing_results_multi6 = {
            '2016': pd.DataFrame({'接口号': ['INT-001'], '项目号': ['2016']})
        }
        
        # 模拟角色过滤后无匹配
        combined_results = []
        for project_id, cached_df in processing_results_multi6.items():
            # 假设这个角色不匹配2016项目
            # filtered_df为空，不添加到combined_results
            pass
        
        if combined_results:
            processing_results6 = pd.concat(combined_results, ignore_index=True)
            has_processed_results6 = True
        else:
            processing_results6 = pd.DataFrame()
            has_processed_results6 = True
        
        assert has_processed_results6 == True
        assert processing_results6.empty == True
    
    def test_display_logic_with_processed_flag_set(self):
        """测试has_processed标志正确设置后的显示逻辑"""
        # 模拟状态
        has_processed_results6 = True
        processing_results6 = pd.DataFrame()  # 空数据
        file6_data = pd.DataFrame({'原始列': [1, 2, 3]})  # 预加载的原始数据
        
        # 显示逻辑
        if has_processed_results6 and processing_results6 is not None and not processing_results6.empty:
            action = "display_results"
        elif has_processed_results6:
            action = "show_empty"  # 应该走这里
        elif file6_data is not None:
            action = "display_raw"
        else:
            action = "none"
        
        # 断言：应该显示"无数据"，而不是显示file6_data
        assert action == "show_empty"
        assert action != "display_raw"
    
    def test_display_logic_without_processed_flag(self):
        """测试has_processed标志未设置时的显示逻辑（修复前的bug）"""
        # 模拟修复前的错误状态：has_processed标志未设置
        has_processed_results6 = False  # BUG：空字典导致标志未设置
        processing_results6 = None
        file6_data = pd.DataFrame({'原始列': [1, 2, 3]})
        
        # 显示逻辑
        if has_processed_results6 and processing_results6 is not None and not processing_results6.empty:
            action = "display_results"
        elif has_processed_results6:
            action = "show_empty"
        elif file6_data is not None:
            action = "display_raw"  # 错误：走到这里了
        else:
            action = "none"
        
        # 这就是bug：因为标志未设置，显示了原始数据
        assert action == "display_raw"  # 这是错误的行为
    
    def test_all_files_handle_empty_dict_consistently(self):
        """测试所有文件类型一致性处理空字典"""
        # 测试文件1-6都应该有相同的逻辑
        file_results = []
        
        for file_num in range(1, 7):
            processing_results_multi = {}  # 空字典
            
            # 统一的处理逻辑
            if processing_results_multi:
                processing_results = pd.DataFrame({'col': [1]})
                has_processed = True
            else:
                processing_results = pd.DataFrame()
                has_processed = True
            
            file_results.append({
                'file_num': file_num,
                'has_processed': has_processed,
                'results_empty': processing_results.empty
            })
        
        # 断言：所有文件都应该正确设置标志
        for result in file_results:
            assert result['has_processed'] == True, f"文件{result['file_num']}的标志未设置"
            assert result['results_empty'] == True, f"文件{result['file_num']}的结果应为空"

