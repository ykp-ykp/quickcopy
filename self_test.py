# -*- coding: utf-8 -*-
"""QuickCopy 自动化自检：offscreen 平台下验证核心逻辑（无需人工操作）。"""

import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.stdout.reconfigure(encoding="utf-8")

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

import main as qc
from config_manager import ConfigManager

PASS = []


def ok(name):
    PASS.append(name)
    print(f"[PASS] {name}")


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


app = QApplication(sys.argv)
app.setStyleSheet(qc.APP_QSS)

# 1. 数据层：增删改查 + 持久化
tmp = os.path.join(tempfile.mkdtemp(), "data.json")
cfg = ConfigManager(tmp)
cfg.set("email", "a@b.com")
cfg.set("phone", "123")
cfg.set("email", "x@y.com")
assert cfg.get("email") == "x@y.com" and cfg.contains("phone")
cfg2 = ConfigManager(tmp)  # 重新加载验证持久化
assert cfg2.get("email") == "x@y.com" and cfg2.items() == [("email", "x@y.com"), ("phone", "123")]
cfg2.delete("phone")
assert not cfg2.contains("phone")
# 损坏文件自愈
with open(tmp, "w", encoding="utf-8") as f:
    f.write("{not valid json")
cfg3 = ConfigManager(tmp)
assert cfg3.items() == [] and os.path.exists(tmp + ".bak")
ok("ConfigManager 增删改查 / 持久化 / 损坏自愈")

# 1.5 多行 / JSON 块 Value 持久化 + move_to_top 置顶
ml = os.path.join(tempfile.mkdtemp(), "ml.json")
cfg_ml = ConfigManager(ml)
json_block = '{\n  "name": "qc",\n  "tags": ["a", "b"]\n}'
cfg_ml.set("json", json_block)
cfg_ml.set("multi", "line1\nline2\nline3")
cfg_ml = ConfigManager(ml)  # 重新加载
assert cfg_ml.get("json") == json_block, "JSON 块应原样持久化"
assert cfg_ml.get("multi") == "line1\nline2\nline3", "多行 Value 应原样持久化"
cfg_ml.move_to_top("multi")
assert cfg_ml.keys()[0] == "multi"
cfg_ml = ConfigManager(ml)  # 置顶顺序应落盘
assert cfg_ml.keys()[0] == "multi"
cfg_ml.move_to_top("multi")  # 已在首位时幂等不报错
assert cfg_ml.keys()[0] == "multi"
ok("多行 / JSON 块 Value 持久化 + move_to_top 置顶")

# 2. 主窗口：列表构建 + 点击复制到剪贴板
win = qc.MainWindow()
iso = os.path.join(tempfile.mkdtemp(), "iso.json")
win.cfg = ConfigManager(iso)  # 测试用独立数据文件，不污染真实数据
win.panel.cfg = win.cfg
win.cfg.set("greet", "hello world")
win.cfg.set("addr", "杭州市西湖区")
win.refresh_list()
win.show()
# 停掉鼠标轮询：面板显隐测试全部手动模拟移入/移出，
# 避免 200ms 轮询在 offscreen 下（光标固定在 (0,0)）随机触发自动隐藏造成抖动
win.mouse_timer.stop()
wait(200)
assert len(win._cards) == 2
win._on_card_clicked("greet")
assert QGuiApplication.clipboard().text() == "hello world", \
    "剪贴板内容应为 hello world"
assert win._selected_key == "greet"
ok("主窗口列表构建 + 单击复制 Value 到剪贴板")

# 2.4 复制成功后弹出「已复制」Toast（主窗口可见时）
assert hasattr(win, "toast"), "主窗口应有 toast 成员"
win.show()
wait(50)
win.toast.pop()
assert win.toast.isVisible(), "pop() 后 Toast 应可见"
# 完整周期 = 淡入 + 停留 + 淡出，再加余量避开 offscreen 定时抖动
wait(qc.TOAST_FADE_MS + qc.TOAST_DURATION + qc.TOAST_FADE_MS + 200)
assert not win.toast.isVisible(), "停留+淡出后 Toast 应自动隐藏"
# 连续 pop() 不崩溃且重新计时
win.toast.pop()
win.toast.pop()
wait(50)
assert win.toast.isVisible(), "重复 pop() 后 Toast 仍可见"
win.toast._hold_timer.stop()
win.toast.hide()
ok("复制成功 Toast 淡入 -> 停留 -> 淡出 / 重复触发不崩溃")

# 2.5 复制后该 Key 置顶显示 + 顶部搜索框模糊过滤
win.cfg.set("email", "a@b.com")
win.cfg.set("phone", "123")
win.refresh_list()
win._on_card_clicked("phone")
assert win.cfg.keys()[0] == "phone", "被复制的 Key 应移到首位"
assert win._cards[0].key == "phone", "列表第一行应是被复制的 Key"
assert win._selected_key == "phone", "置顶后选中态应保留"
win.search_edit.setText("EMA")
wait(50)
assert [c.key for c in win._cards] == ["email"], "搜索应不区分大小写模糊匹配 Key"
win.search_edit.setText("")
wait(50)
assert len(win._cards) == len(win.cfg.items()), "清空搜索应恢复完整列表"
ok("复制后 Key 置顶 + 搜索框模糊过滤")

# 2.6 编辑对话框 Value 支持多行文本
dlg = qc.EntryDialog(win, "测试", "k", "v1\nv2")
assert dlg.value() == "v1\nv2", "对话框应保留多行 Value"
dlg.key_edit.setText("  newkey  ")
assert dlg.key() == "newkey"
dlg.deleteLater()
ok("添加 / 编辑对话框 Value 多行输入")

# 3. 关闭窗口 = 隐藏不退出
win.close()
wait(100)
assert not win.isVisible()
ok("关闭主窗口仅隐藏（驻留托盘）")

# 4. 浮动面板：唤出 -> 内容正确 -> 0.3s 延时后自动淡出消失
screen = QGuiApplication.primaryScreen()
win.panel.show_on_screen(screen)
wait(300)
assert win.panel.isVisible()
assert win.panel.list_layout.count() >= 4  # 2 卡片 + 1 分隔线 + stretch
win.panel.schedule_auto_hide()  # 模拟鼠标移出
wait(300 + 500 + 400)           # 延时 300ms + 淡出 500ms + 余量
assert not win.panel.isVisible(), "面板应在鼠标离开后自动消失"
ok("浮动面板唤出 / 分隔线 / 移出 0.3s 后自动淡出消失")

# 5. 0.3s 内鼠标重新进入 -> 取消自动隐藏
win.panel.show_on_screen(screen)
wait(250)
win.panel.schedule_auto_hide()
wait(100)
win.panel.cancel_auto_hide()    # 模拟鼠标重新进入
wait(600)
assert win.panel.isVisible(), "鼠标及时回来后面板不应消失"
win.panel.fade_out(150)
wait(400)
assert not win.panel.isVisible()
ok("鼠标 0.3s 内重新进入面板可取消自动隐藏")

# 6. 复制时若面板展开 -> 面板 1s 内淡出（复制瞬间先 pop Toast）
win.panel.show_on_screen(screen)
wait(250)
win.copy_value("addr")
assert QGuiApplication.clipboard().text() == "杭州市西湖区"
wait(30)
assert win.panel.toast.isVisible(), "面板复制时应弹出「已复制」Toast"
wait(1000 + 400)
assert not win.panel.isVisible(), "复制后面板应在 1s 内淡出"
ok("复制成功后面板 1s 内淡出并关闭")

# 6.4 面板重新唤出时清掉上次的残留 Toast
win.panel.show_on_screen(screen)
wait(100)
win.panel.toast.pop()
assert win.panel.toast.isVisible(), "残留 Toast 应可见以便被清掉"
win.panel.show_on_screen(screen)
assert not win.panel.toast.isVisible(), "show_on_screen 应清掉残留 Toast"
win.panel.fade_out(150)
wait(400)
ok("面板唤出清空残留 Toast")

# 6.5 浮动面板搜索过滤 + 唤出时清空搜索词 + 搜索焦点暂停自动隐藏
win.panel.show_on_screen(screen)
wait(250)
win.panel.search_edit.setText("GREE")
wait(50)
cards = win.panel.list_widget.findChildren(qc.EntryCard)
assert [c.key for c in cards] == ["greet"], "面板搜索应不区分大小写过滤 Key"
# 搜索框有焦点时（用户正在打字）不启动自动隐藏
win.panel.search_edit.hasFocus = lambda: True  # offscreen 下模拟输入焦点
win.panel.schedule_auto_hide()
assert not win.panel._leave_timer.isActive(), "搜索框有焦点时不应启动自动隐藏"
del win.panel.search_edit.hasFocus
win.panel.fade_out(150)
wait(400)
win.panel.search_edit.setText("残留词")
win.panel.show_on_screen(screen)
wait(250)
assert win.panel.search_edit.text() == "", "面板唤出时应清空上次搜索词"
assert len(win.panel.list_widget.findChildren(qc.EntryCard)) \
    == len(win.cfg.items()), "清空搜索后面板应显示全部条目"
win.panel.fade_out(150)
wait(400)
ok("浮动面板搜索过滤 / 唤出清空 / 焦点暂停自动隐藏")

# 6.6 开机自启注册表读写（用独立 value 名，不碰真实设置）
_test_name = "QuickCopy_selftest"
qc.set_autostart(True, _test_name)
assert qc.get_autostart(_test_name), "写入后应读到开机自启已开启"
qc.set_autostart(False, _test_name)
assert not qc.get_autostart(_test_name), "删除后应读到开机自启已关闭"
qc.set_autostart(False, _test_name)  # 重复删除应幂等不报错
ok("开机自启注册表写入 / 读取 / 删除")

# 7. 鼠标轮询函数不崩溃
win._poll_mouse()
ok("鼠标位置轮询正常执行")

print()
print(f"全部通过：{len(PASS)} 项")
for name in PASS:
    print("  -", name)
