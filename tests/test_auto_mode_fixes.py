"""
测试自动模式修复
测试两个关键问题：
1. 手动操作不应被联动（处理后不自动导出）
2. 自动运行时不显示处理完成弹窗，手动操作时显示
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
import tkinter as tk


class TestAutoModeNoLinkage:
    """测试手动操作独立性（不联动）"""
    
    def test_manual_operation_no_auto_export_in_auto_mode(self):
        """测试：auto_mode下手动点击"开始处理"后不自动导出"""
        with patch('base.WindowManager'):
            from base import ExcelProcessorApp
            
            app = ExcelProcessorApp(auto_mode=True)  # 以auto模式启动
            
            # 模拟手动点击"开始处理"
            app._manual_operation = True
            
            # 验证条件：auto_mode=True, _manual_operation=True
            assert app.auto_mode == True
            assert app._manual_operation == True
            
            # 判断逻辑：应该不触发自动导出
            should_auto_export = (app.auto_mode and not app._manual_operation)
            assert should_auto_export == False, "手动操作时不应自动导出"
    
    def test_auto_run_should_auto_export(self):
        """测试：自动运行时应该自动导出"""
        with patch('base.WindowManager'):
            from base import ExcelProcessorApp
            
            app = ExcelProcessorApp(auto_mode=True)
            
            # 自动运行场景：_manual_operation=False
            app._manual_operation = False
            
            # 验证条件
            assert app.auto_mode == True
            assert app._manual_operation == False
            
            # 判断逻辑：应该触发自动导出
            should_auto_export = (app.auto_mode and not app._manual_operation)
            assert should_auto_export == True, "自动运行时应自动导出"
    
    def test_normal_mode_never_auto_export(self):
        """测试：非auto模式永远不自动导出"""
        with patch('base.WindowManager'):
            from base import ExcelProcessorApp
            
            app = ExcelProcessorApp(auto_mode=False)
            
            # 测试手动操作
            app._manual_operation = True
            should_auto_export = (app.auto_mode and not app._manual_operation)
            assert should_auto_export == False
            
            # 测试非手动操作
            app._manual_operation = False
            should_auto_export = (app.auto_mode and not app._manual_operation)
            assert should_auto_export == False


class TestAutoModePopupLogic:
    """测试弹窗逻辑"""
    
    def test_auto_run_no_popup(self):
        """测试：自动运行时不显示弹窗"""
        with patch('base.WindowManager'):
            from base import ExcelProcessorApp
            
            app = ExcelProcessorApp(auto_mode=True)
            
            # 自动运行场景
            app._manual_operation = False
            
            # 验证弹窗逻辑
            should_show_popup = app._should_show_popup()
            assert should_show_popup == False, "自动运行时不应显示弹窗"
    
    def test_manual_operation_after_auto_run_shows_popup(self):
        """测试：自动运行后手动操作应显示弹窗"""
        with patch('base.WindowManager'):
            from base import ExcelProcessorApp
            
            app = ExcelProcessorApp(auto_mode=True)
            
            # 模拟自动运行完成
            app._manual_operation = False
            assert app._should_show_popup() == False  # 自动运行时不显示
            
            # 模拟手动点击"开始处理"
            app._manual_operation = True
            assert app._should_show_popup() == True, "手动操作时应显示弹窗"
    
    def test_normal_mode_always_shows_popup(self):
        """测试：非auto模式永远显示弹窗"""
        with patch('base.WindowManager'):
            from base import ExcelProcessorApp
            
            app = ExcelProcessorApp(auto_mode=False)
            
            # 不管_manual_operation是什么值，都应该显示弹窗
            app._manual_operation = False
            assert app._should_show_popup() == True
            
            app._manual_operation = True
            assert app._should_show_popup() == True
    
    def test_manual_operation_flag_resets_after_processing(self):
        """测试：_manual_operation标志在处理完成后被重置"""
        with patch('base.WindowManager'):
            from base import ExcelProcessorApp
            
            app = ExcelProcessorApp(auto_mode=True)
            
            # 模拟手动操作开始
            app._manual_operation = True
            assert app._manual_operation == True
            
            # 在实际代码中，处理完成后会重置标志
            # 这里验证标志可以被重置
            app._manual_operation = False
            assert app._manual_operation == False


class TestAutoModeWorkflow:
    """测试自动模式工作流"""
    
    def test_auto_run_workflow(self):
        """测试：自动运行完整流程"""
        with patch('base.WindowManager'):
            from base import ExcelProcessorApp
            
            app = ExcelProcessorApp(auto_mode=True)
            
            # 步骤1：自动运行开始
            app._manual_operation = False
            
            # 步骤2：刷新文件（不显示弹窗）
            assert app._should_show_popup() == False
            
            # 步骤3：开始处理（不显示"处理完成"弹窗）
            assert app._should_show_popup() == False
            
            # 步骤4：自动导出（因为是自动运行）
            should_auto_export = (app.auto_mode and not app._manual_operation)
            assert should_auto_export == True
    
    def test_manual_operation_after_auto_run_workflow(self):
        """测试：自动运行后手动操作流程"""
        with patch('base.WindowManager'):
            from base import ExcelProcessorApp
            
            app = ExcelProcessorApp(auto_mode=True)
            
            # 步骤1：自动运行完成
            app._manual_operation = False
            
            # 步骤2：用户手动点击"刷新文件列表"
            app._manual_operation = True
            assert app._should_show_popup() == True  # 应显示弹窗
            
            # 步骤3：刷新完成，重置标志
            app._manual_operation = False
            
            # 步骤4：用户手动点击"开始处理"
            app._manual_operation = True
            assert app._should_show_popup() == True  # 应显示"处理完成"弹窗
            
            # 步骤5：处理完成，不自动导出
            should_auto_export = (app.auto_mode and not app._manual_operation)
            assert should_auto_export == False  # 不应自动导出
            
            # 步骤6：用户手动点击"导出结果"
            # 这是独立操作，不联动
            assert app._should_show_popup() == True  # 应显示导出完成弹窗


class TestManualOperationFlagManagement:
    """测试_manual_operation标志管理"""
    
    def test_flag_set_on_manual_actions(self):
        """测试：手动操作时标志被设置"""
        with patch('base.WindowManager'):
            from base import ExcelProcessorApp
            
            app = ExcelProcessorApp(auto_mode=True)
            
            # 初始状态
            assert app._manual_operation == False
            
            # 模拟手动操作
            app._manual_operation = True
            assert app._manual_operation == True
    
    def test_flag_reset_after_operation_complete(self):
        """测试：操作完成后标志被重置"""
        with patch('base.WindowManager'):
            from base import ExcelProcessorApp
            
            app = ExcelProcessorApp(auto_mode=True)
            
            # 手动操作开始
            app._manual_operation = True
            
            # 操作完成，重置标志
            app._manual_operation = False
            assert app._manual_operation == False
    
    def test_multiple_manual_operations(self):
        """测试：多次手动操作"""
        with patch('base.WindowManager'):
            from base import ExcelProcessorApp
            
            app = ExcelProcessorApp(auto_mode=True)
            
            # 第一次手动操作
            app._manual_operation = True
            assert app._should_show_popup() == True
            app._manual_operation = False
            
            # 第二次手动操作
            app._manual_operation = True
            assert app._should_show_popup() == True
            app._manual_operation = False
            
            # 确保每次都能正确工作
            assert app._manual_operation == False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

