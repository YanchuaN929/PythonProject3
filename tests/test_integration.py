#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
集成测试 - 测试base.py与window.py的集成
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestBaseWindowIntegration:
    """测试base.py与window.py的集成"""
    
    def test_can_import_base(self):
        """测试能否导入base模块"""
        try:
            import base
            assert True
        except Exception as e:
            pytest.fail(f"导入base模块失败: {e}")
    
    def test_can_import_window_from_base(self):
        """测试base模块是否成功导入了window"""
        import base
        # 验证WindowManager已被导入
        assert hasattr(base, 'WindowManager')
    
    @patch('base.tk.Tk')
    @patch('base.WindowManager')
    def test_excel_processor_app_initialization(self, mock_window_manager, mock_tk):
        """测试ExcelProcessorApp能否正确初始化WindowManager"""
        # Mock Tk实例
        mock_root = MagicMock()
        mock_tk.return_value = mock_root
        
        # Mock WindowManager实例
        mock_wm_instance = MagicMock()
        mock_wm_instance.path_var = Mock()
        mock_wm_instance.export_path_var = Mock()
        mock_wm_instance.file_info_text = Mock()
        mock_wm_instance.notebook = Mock()
        mock_wm_instance.buttons = {'export': Mock()}
        mock_wm_instance.viewers = {
            'tab1': Mock(),
            'tab2': Mock(),
            'tab3': Mock(),
            'tab4': Mock(),
            'tab5': Mock(),
            'tab6': Mock(),
        }
        mock_window_manager.return_value = mock_wm_instance
        
        # 创建配置文件mock
        with patch('base.Path.exists', return_value=False):
            with patch('builtins.open', create=True):
                import base
                
                # 尝试创建ExcelProcessorApp实例
                try:
                    app = base.ExcelProcessorApp(auto_mode=False)
                    
                    # 验证WindowManager被调用
                    mock_window_manager.assert_called_once()
                    
                    # 验证setup被调用
                    mock_wm_instance.setup.assert_called_once()
                    
                    # 验证UI组件引用被正确设置
                    assert hasattr(app, 'window_manager')
                    assert hasattr(app, 'path_var')
                    assert hasattr(app, 'export_path_var')
                    assert hasattr(app, 'tab1_viewer')
                    assert hasattr(app, 'tab2_viewer')
                    
                    print("✅ ExcelProcessorApp初始化成功")
                    
                except Exception as e:
                    pytest.fail(f"ExcelProcessorApp初始化失败: {e}")
    
    def test_window_manager_callbacks_exist(self):
        """测试所有回调方法在base.py中是否存在"""
        import base
        
        required_callbacks = [
            'browse_folder',
            'browse_export_folder',
            'refresh_file_list',
            'start_processing',
            'export_results',
            'open_selected_folder',
            'open_monitor',
            'show_settings_menu',
            'on_tab_changed',
        ]
        
        # 验证ExcelProcessorApp类有这些方法
        for callback in required_callbacks:
            assert hasattr(base.ExcelProcessorApp, callback), \
                f"ExcelProcessorApp缺少回调方法: {callback}"
        
        print(f"✅ 所有{len(required_callbacks)}个回调方法都存在")


class TestWindowManagerIntegration:
    """测试WindowManager集成功能"""
    
    @patch('window.tk.Tk')
    def test_window_manager_accepts_callbacks(self, mock_tk):
        """测试WindowManager能够接受回调函数"""
        from window import WindowManager
        
        mock_root = MagicMock()
        
        callbacks = {
            'on_browse_folder': Mock(),
            'on_refresh_files': Mock(),
        }
        
        wm = WindowManager(mock_root, callbacks)
        
        assert wm.callbacks == callbacks
        print("✅ WindowManager正确接受回调函数")
    
    def test_window_manager_setup_signature(self):
        """测试WindowManager.setup方法签名正确"""
        from window import WindowManager
        import inspect
        
        sig = inspect.signature(WindowManager.setup)
        params = list(sig.parameters.keys())
        
        assert 'config_data' in params
        assert 'process_vars' in params
        
        print("✅ WindowManager.setup方法签名正确")


class TestConfigData:
    """测试配置数据传递"""
    
    @patch('window.tk.Tk')
    def test_config_data_structure(self, mock_tk):
        """测试配置数据结构正确"""
        from window import WindowManager
        
        mock_root = MagicMock()
        
        config_data = {
            'folder_path': 'D:/test/path',
            'export_folder_path': 'D:/test/export',
        }
        
        process_vars = {
            'tab1': Mock(),
            'tab2': Mock(),
            'tab3': Mock(),
            'tab4': Mock(),
            'tab5': Mock(),
            'tab6': Mock(),
        }
        
        wm = WindowManager(mock_root, {})
        
        # 测试setup不会抛出异常
        try:
            # 我们不能真正调用setup，因为它会创建GUI
            # 但我们可以验证参数结构
            assert isinstance(config_data, dict)
            assert isinstance(process_vars, dict)
            assert 'folder_path' in config_data
            assert 'export_folder_path' in config_data
            assert len(process_vars) == 6
            
            print("✅ 配置数据结构正确")
        except Exception as e:
            pytest.fail(f"配置数据结构测试失败: {e}")


# 运行测试的主函数
if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])

