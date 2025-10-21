# PAGE 使用指南

PAGE (Python Automatic GUI Generator) 是一个针对 tkinter 的可视化 GUI 设计工具，可以帮助你通过拖拽组件的方式来设计界面。

## 安装 PAGE

### 方法一：通过 pip 安装
```bash
pip install page
```

### 方法二：从官网下载
访问 [PAGE 官方网站](http://page.sourceforge.net/) 下载安装包

## PAGE 基本使用步骤

### 1. 启动 PAGE
在命令行中运行：
```bash
page
```

### 2. 创建新项目
- 点击菜单栏的 "File" -> "New"
- 保存项目为 `.tpg` 文件（例如 `interface_gui.tpg`）

### 3. 设计界面
- 在左侧面板中选择需要的组件（如 Frame、Label、Button 等）
- 将组件拖拽到中间的设计区域
- 在右侧面板中设置组件的属性（如文本、大小、颜色等）
- 设置组件的布局方式（pack、grid 等）

### 4. 生成代码
- 点击菜单栏的 "Gen" -> "Gen_Python" 生成 Python 代码
- 生成的代码将包括两个文件：
  - 一个包含界面定义的文件（如 `interface_gui.py`）
  - 一个支持文件（如 `interface_gui_support.py`）

## 如何将 PAGE 集成到你的项目中

### 1. 使用 PAGE 重新设计界面
你可以在 PAGE 中重新创建你的界面，参考你现有的 [window.py](file:///D:/PycharmProjects/PythonProject3/window.py) 文件中的布局和组件。

### 2. 保持现有功能
在使用 PAGE 生成的代码时，你需要确保以下功能得到保留：

1. **窗口大小自适应** - 你现有的 [setup_window_size()](file:///D:/PycharmProjects/PythonProject3/window.py#L94-L132) 方法
2. **Excel 数据展示** - Treeview 控件的使用方式
3. **回调函数机制** - 与业务逻辑的交互
4. **资源配置** - 图标等资源文件的加载

### 3. 整合步骤

1. 使用 PAGE 设计界面
2. 生成代码
3. 将生成的界面代码与现有的业务逻辑进行整合
4. 确保所有回调函数正常工作
5. 保持现有的功能特性

## PAGE 与现有代码的对比优势

| 特性 | 纯代码编写 | PAGE 可视化设计 |
|------|------------|----------------|
| 直观性 | 低 | 高 |
| 修改便利性 | 需要理解代码逻辑 | 拖拽式修改 |
| 布局调试 | 困难 | 实时预览 |
| 学习成本 | 需要熟悉tkinter | 可视化操作 |
| 版本控制 | 容易跟踪变更 | 需要同时管理.tpg和.py文件 |

## 注意事项

1. PAGE 生成的代码可能需要根据你的具体需求进行调整
2. 保持与现有业务逻辑的兼容性
3. 注意回调函数的命名和参数传递
4. 确保资源文件（如图标）的正确加载
5. 测试所有功能以确保没有遗漏

## 建议的工作流程

1. 使用 PAGE 重新设计你的主界面
2. 逐步替换现有界面组件
3. 保持与 [WindowManager](file:///D:/PycharmProjects/PythonProject3/window.py#L35-L484) 类的兼容性
4. 确保所有功能正常运行
5. 优化和调整布局细节

通过使用 PAGE，你可以更直观地设计和调整界面布局，提高开发效率。