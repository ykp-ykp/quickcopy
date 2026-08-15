# QuickCopy — 轻量级 Windows 剪贴板增强器

一个常驻后台的快捷复制工具：把常用文本（邮箱、地址、模板话术……）存成 Key-Value，
**点击 Key 即可把 Value 复制到剪贴板**，并通过屏幕右上角热区随时唤出速览面板。

## 功能一览

| 功能 | 说明 |
| --- | --- |
| 数据存储 | Key-Value 成对保存，持久化在本地 `quickcopy_data.json`（程序/exe 同目录）；Value 支持换行、JSON 块等任意多行文本 |
| 主界面 | 只显示 Key 列表，单击复制 Value，选中后通过底部按钮编辑 / 删除，条目间有细分隔线 |
| 搜索过滤 | 主界面顶部搜索框，按 Key 不区分大小写模糊过滤，清空即恢复完整列表 |
| 最近置顶 | 复制某个 Key 后，该条目自动移到列表首位并持久化，常用内容永远在第一行 |
| 后台驻留 | 最小化 / 关闭主窗口后隐藏到系统托盘，不退出；托盘菜单可「显示主界面 / 退出」 |
| 悬停唤醒 | 主窗口隐藏时，鼠标移到**屏幕最右上角**，自动弹出右上角浮动面板（Key + Value 卡片列表，支持滚轮） |
| 自动消失 | 鼠标移出面板 **0.3 秒**内未移回，面板即透明度淡出并完全消失，绝不常驻遮挡 |

## 运行（源码方式）

```bash
pip install PySide6
python main.py
```

要求 Python 3.10+，仅支持 Windows（托盘 / 置顶 / 热区逻辑按 Windows 桌面设计）。

## 打包成 exe

双击运行 `build.bat`，自动安装依赖并用 PyInstaller 按 `QuickCopy.spec` 打包：

- 产物：`dist\QuickCopy.exe`，单文件、无控制台黑框，双击即用（约 21MB）
- 数据文件 `quickcopy_data.json` 会生成在 **exe 同目录**，拷贝 exe 时记得带上
- spec 中已剔除未用到的 Qt 模块（Quick/Qml/Pdf/Network/OpenGL/Svg）、
  软件渲染回退 `opengl32sw.dll`、Qt 翻译文件及多余插件，体积从 43MB 降到约一半。
  若在无显卡驱动的机器上显示异常，可把 `opengl32sw.dll` 从 spec 的
  `DROP_BIN_NAMES` 中移除后重新打包

## 使用说明

1. **添加条目**：主界面点「添加」，输入 Key 和 Value 保存；Value 为多行输入框，可直接粘贴换行文本或 JSON 块，`Ctrl+Enter` 快捷保存。
2. **搜索**：主界面顶部搜索框输入关键词，列表实时按 Key 模糊过滤（不区分大小写）。
3. **复制**：单击列表中的 Key，Value 立即进入剪贴板；被复制的条目自动置顶到第一行。
4. **编辑 / 删除**：单击选中条目后，点底部「编辑」「删除」按钮。
5. **隐藏**：点标题栏「–」或「✕」，程序隐藏到系统托盘继续运行。
6. **速览面板**：程序隐藏后，把鼠标推到屏幕**最右上角**，面板自动弹出；点击面板条目同样复制；鼠标移开即自动消失。
7. **退出**：右键托盘图标 →「退出 QuickCopy」。

## 项目结构

```
quickcopy/
├─ main.py            # 界面与交互（主窗口、浮动面板、托盘、鼠标轮询）
├─ config_manager.py  # Key-Value 的 JSON 持久化
├─ build.bat          # 打包入口（调用 QuickCopy.spec）
├─ QuickCopy.spec     # PyInstaller 配置（单文件/无控制台/瘦身规则）
├─ self_test.py       # 自动化自检测试（可选）
└─ README.md
```

## 自检（可选）

```bash
python self_test.py
```

会验证数据层增删改查、剪贴板复制、浮动面板显示 / 延时隐藏 / 取消隐藏等核心逻辑。
