# -*- coding: utf-8 -*-
"""
QuickCopy - 轻量级 Windows 剪贴板增强器
=========================================
* 主界面：Key 列表，单击复制 Value，底部按钮编辑 / 删除
* 最小化或关闭后主程序驻留系统托盘，不退出
* 鼠标移至屏幕最右上角（热区）唤出浮动速览面板；移出面板 0.3s 后自动淡出
* 托盘菜单可勾选开机自启（写 HKCU Run 注册表，无需管理员权限）
* 所有淡出均使用 QPropertyAnimation，不阻塞主线程

运行：python main.py
打包：build.bat（PyInstaller -> 单文件 exe，无控制台黑框）
"""

import ctypes
import os
import sys
import winreg

from PySide6.QtCore import (QEasingCurve, QPoint, QPropertyAnimation, QRect,
                            Qt, QTimer, Signal)
from PySide6.QtGui import (QColor, QCursor, QGuiApplication, QIcon, QKeySequence,
                           QShortcut)
from PySide6.QtWidgets import (QApplication, QDialog, QFrame,
                               QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
                               QLineEdit, QMenu, QMessageBox, QPlainTextEdit,
                               QPushButton, QScrollArea, QSystemTrayIcon,
                               QVBoxLayout, QWidget)

from config_manager import ConfigManager

# ---------------------------------------------------------------- 常量
PANEL_VISUAL_WIDTH = 280          # 浮动面板可视宽度
WINDOW_MARGIN = 10                # 无边框窗口四周留给阴影的透明边距
HOT_CORNER = 6                    # 右上角热区尺寸（像素）
POLL_INTERVAL = 200               # 鼠标位置轮询间隔（毫秒）
LEAVE_DELAY = 300                 # 鼠标移出面板后的自动隐藏延时（毫秒）
PANEL_COPY_FADE_MS = 1000         # 复制成功后面板的淡出时长
PANEL_LEAVE_FADE_MS = 500         # 鼠标离开后面板的淡出时长

# ---------------------------------------------------------------- 全局样式
APP_QSS = """
* { font-family: "Microsoft YaHei", "Segoe UI", sans-serif; }
QWidget { color: #e6e8ee; font-size: 13px; }

#appContainer, #panelContainer, #dialogContainer {
    background-color: rgba(28, 30, 37, 245);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 14px;
}
#titleLabel { font-size: 14px; font-weight: bold; }
#panelHeader { font-size: 13px; font-weight: bold; color: #cfd4de; padding: 4px 6px; }
#hintLabel { color: #8a8f9c; font-size: 11px; padding: 0 4px 4px 4px; }
#emptyLabel { color: #7a7f8c; padding: 40px 10px; }
#dialogTitle { font-size: 15px; font-weight: bold; padding-bottom: 4px; }
#warnLabel { color: #ff7b7b; font-size: 11px; }

#titleBtn, #titleCloseBtn {
    background: transparent; border: none; border-radius: 6px;
    color: #c9cdd6; font-size: 13px;
}
#titleBtn:hover { background: rgba(255, 255, 255, 0.10); }
#titleCloseBtn:hover { background: #e81123; color: #ffffff; }

#actionBtn {
    background-color: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 8px; padding: 7px 0;
}
#actionBtn:hover { background-color: rgba(255, 255, 255, 0.12); }
#actionBtn:pressed { background-color: rgba(255, 255, 255, 0.04); }
#primaryBtn {
    background-color: #5b7fff; border: none; border-radius: 8px;
    padding: 7px 0; color: #ffffff; font-weight: bold;
}
#primaryBtn:hover { background-color: #6d8bff; }
#primaryBtn:pressed { background-color: #4a6de0; }

#entryCard {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
}
#entryCard:hover { background-color: rgba(255, 255, 255, 0.05); }
#entryCard[selected="true"] {
    background-color: rgba(91, 127, 255, 0.18);
    border: 1px solid rgba(91, 127, 255, 0.45);
}
#keyLabel { font-weight: bold; color: #eef1f6; }
#valueLabel { color: #9aa0ad; font-size: 12px; }
/* 条目分隔线：比背景略深的暗色细线，清晰但不扎眼 */
#separator { background-color: rgba(0, 0, 0, 0.35); margin: 2px 8px; }

#mainList, #panelList { background: transparent; }

QScrollArea { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 4px 2px; }
QScrollBar::handle:vertical {
    background: rgba(255, 255, 255, 0.18); border-radius: 4px; min-height: 30px;
}
QScrollBar::handle:vertical:hover { background: rgba(255, 255, 255, 0.30); }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }

QLineEdit, QPlainTextEdit {
    background-color: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 8px; padding: 8px 10px;
    selection-background-color: #5b7fff;
}
QLineEdit:focus, QPlainTextEdit:focus { border: 1px solid #5b7fff; }

QMenu {
    background-color: rgba(30, 32, 38, 0.98);
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 8px; padding: 4px;
}
QMenu::item { padding: 6px 24px; border-radius: 5px; }
QMenu::item:selected { background-color: rgba(91, 127, 255, 0.35); }

QMessageBox { background-color: #1c1e24; }
QMessageBox QLabel { color: #e6e8ee; }

QToolTip {
    background-color: rgba(30, 32, 38, 0.98); color: #dfe3ec;
    border: 1px solid rgba(255, 255, 255, 0.12); padding: 4px 8px;
}
"""


# ---------------------------------------------------------------- 工具函数
def ellipsize(text, limit):
    """长文本截断：换行折叠为空格，超长加省略号。"""
    text = (text or "").replace("\r", " ").replace("\n", " ")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def make_separator():
    """条目之间的细分隔线（QFrame.HLine 样式的 1px 暗线）。"""
    line = QFrame()
    line.setObjectName("separator")
    line.setFrameShape(QFrame.HLine)
    line.setFixedHeight(1)
    return line


def make_shadow(blur=24, y_offset=4):
    effect = QGraphicsDropShadowEffect()
    effect.setBlurRadius(blur)
    effect.setOffset(0, y_offset)
    effect.setColor(QColor(0, 0, 0, 140))
    return effect


def resource_path(name):
    """资源文件路径：兼容 PyInstaller 单文件打包后的临时解压目录。"""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def load_app_icon():
    """应用图标（app.png 由 make_icon.py 生成，并随 spec 打进 exe）。"""
    return QIcon(resource_path("app.png"))


# ---------------------------------------------------------------- 开机自启
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
AUTOSTART_NAME = "QuickCopy"


def _autostart_command():
    """写进注册表的启动命令：打包 exe 直接启动；源码运行用 pythonw 无窗启动。"""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    pythonw = sys.executable.replace("python.exe", "pythonw.exe")
    return f'"{pythonw}" "{os.path.abspath(__file__)}"'


def get_autostart(name=AUTOSTART_NAME):
    """当前用户是否已注册开机自启。"""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, name)
        return bool(value)
    except OSError:
        return False


def set_autostart(enabled, name=AUTOSTART_NAME):
    """写入 / 删除当前用户的开机自启注册表项（HKCU，无需管理员权限）。"""
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                        winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ,
                              _autostart_command())
        else:
            try:
                winreg.DeleteValue(key, name)
            except FileNotFoundError:
                pass


# ---------------------------------------------------------------- 条目卡片
class EntryCard(QFrame):
    """单个 Key-Value 条目卡片：Key 加粗在上，Value 灰字在下。"""

    clicked = Signal(str)

    def __init__(self, key, value, parent=None):
        super().__init__(parent)
        self.key = key
        self.setObjectName("entryCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(50)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 7, 10, 7)
        lay.setSpacing(2)

        key_label = QLabel(ellipsize(key, 28), self)
        key_label.setObjectName("keyLabel")
        value_label = QLabel(ellipsize(value, 42) if value.strip() else "（空）", self)
        value_label.setObjectName("valueLabel")
        if value.strip():
            value_label.setToolTip(value)

        lay.addWidget(key_label)
        lay.addWidget(value_label)

    def setSelected(self, on):
        self.setProperty("selected", on)
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.key)
        super().mousePressEvent(event)


# ---------------------------------------------------------------- 标题栏
class TitleBar(QFrame):
    """无边框窗口的自定义标题栏：拖拽移动 + 最小化 / 关闭按钮。"""

    def __init__(self, title, on_minimize, on_close, parent=None):
        super().__init__(parent)
        self._drag_pos = None

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 8, 2)
        lay.setSpacing(4)

        name = QLabel(title, self)
        name.setObjectName("titleLabel")
        lay.addWidget(name)
        lay.addStretch(1)

        btn_min = QPushButton("–", self)
        btn_min.setObjectName("titleBtn")
        btn_min.setFixedSize(30, 26)
        btn_min.setToolTip("最小化到托盘")
        btn_min.clicked.connect(on_minimize)
        lay.addWidget(btn_min)

        btn_close = QPushButton("✕", self)
        btn_close.setObjectName("titleCloseBtn")
        btn_close.setFixedSize(30, 26)
        btn_close.setToolTip("隐藏到托盘（不退出）")
        btn_close.clicked.connect(on_close)
        lay.addWidget(btn_close)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = (event.globalPosition().toPoint()
                              - self.window().frameGeometry().topLeft())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)


# ---------------------------------------------------------------- 添加/编辑对话框
class EntryDialog(QDialog):
    """添加 / 编辑对话框：Key 单行输入，Value 多行输入（支持换行、JSON 块）。"""

    def __init__(self, parent, title, key="", value=""):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)
        self._drag_pos = None

        container = QFrame(self)
        container.setObjectName("dialogContainer")
        container.setGraphicsEffect(make_shadow())
        lay = QVBoxLayout(container)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(8)

        title_label = QLabel(title, container)
        title_label.setObjectName("dialogTitle")
        lay.addWidget(title_label)

        self.key_edit = QLineEdit(key, container)
        self.key_edit.setPlaceholderText("Key（名称，例如：工作邮箱）")
        self.key_edit.setMaxLength(60)
        lay.addWidget(self.key_edit)

        self.value_edit = QPlainTextEdit(container)
        self.value_edit.setPlaceholderText(
            "Value（点击时要复制的内容，支持换行 / JSON 块等任意文本）")
        self.value_edit.setPlainText(value)
        self.value_edit.setMinimumHeight(120)
        lay.addWidget(self.value_edit, 1)

        self.warn_label = QLabel("", container)
        self.warn_label.setObjectName("warnLabel")
        self.warn_label.hide()
        lay.addWidget(self.warn_label)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        hint = QLabel("Ctrl+Enter 保存", container)
        hint.setObjectName("hintLabel")
        btn_row.addWidget(hint)
        btn_row.addStretch(1)
        btn_cancel = QPushButton("取消", container)
        btn_cancel.setObjectName("actionBtn")
        btn_cancel.setFixedWidth(88)
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("保存", container)
        btn_save.setObjectName("primaryBtn")
        btn_save.setFixedWidth(88)
        btn_save.setDefault(True)
        btn_save.clicked.connect(self._on_save)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)
        lay.addLayout(btn_row)

        # 多行输入框里 Enter 用于换行，用 Ctrl+Enter 快捷保存
        shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        shortcut.setContext(Qt.WindowShortcut)
        shortcut.activated.connect(self._on_save)

        root = QVBoxLayout(self)
        root.setContentsMargins(WINDOW_MARGIN, WINDOW_MARGIN,
                                WINDOW_MARGIN, WINDOW_MARGIN)
        root.addWidget(container)
        self.resize(420, 320)
        self.key_edit.setFocus()

    def key(self):
        return self.key_edit.text().strip()

    def value(self):
        return self.value_edit.toPlainText()

    def _on_save(self):
        if not self.key():
            self.warn_label.setText("Key 不能为空")
            self.warn_label.show()
            self.key_edit.setFocus()
            return
        self.accept()

    # 无边框对话框支持拖拽移动
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = (event.globalPosition().toPoint()
                              - self.frameGeometry().topLeft())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)


# ---------------------------------------------------------------- 浮动面板
class FloatingPanel(QWidget):
    """右上角悬停唤出的速览面板：展示全部 Key-Value，点击复制，滚轮翻页。"""

    copyRequested = Signal(str)

    def __init__(self, cfg):
        super().__init__(None, Qt.FramelessWindowHint
                         | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.cfg = cfg
        self._hiding = False
        self._fade = None
        self._search_text = ""

        # 鼠标移出后的 0.3s 短延时定时器（单次触发）
        self._leave_timer = QTimer(self)
        self._leave_timer.setSingleShot(True)
        self._leave_timer.setInterval(LEAVE_DELAY)
        self._leave_timer.timeout.connect(self._on_leave_timeout)

        self.container = QFrame(self)
        self.container.setObjectName("panelContainer")
        self.container.setGraphicsEffect(make_shadow())
        lay = QVBoxLayout(self.container)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(4)

        header = QLabel("QuickCopy 速览（点击条目复制）", self.container)
        header.setObjectName("panelHeader")
        lay.addWidget(header)

        self.search_edit = QLineEdit(self.container)
        self.search_edit.setPlaceholderText("搜索 Key…")
        self.search_edit.setClearButtonEnabled(True)
        # 仅点击获取焦点：面板弹出时若自动聚焦搜索框，
        # 「焦点期间不自动隐藏」的保护会让面板永远不消失
        self.search_edit.setFocusPolicy(Qt.ClickFocus)
        self.search_edit.textChanged.connect(self._on_search_changed)
        lay.addWidget(self.search_edit)

        self.scroll = QScrollArea(self.container)
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_widget = QWidget()
        self.list_widget.setObjectName("panelList")
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setContentsMargins(2, 0, 2, 4)
        self.list_layout.setSpacing(2)
        self.scroll.setWidget(self.list_widget)
        lay.addWidget(self.scroll)

        root = QVBoxLayout(self)
        root.setContentsMargins(WINDOW_MARGIN, WINDOW_MARGIN,
                                WINDOW_MARGIN, WINDOW_MARGIN)
        root.addWidget(self.container)
        self.setFixedWidth(PANEL_VISUAL_WIDTH + WINDOW_MARGIN * 2)
        self.hide()

    # ------------------------------------------------------ 内容
    def _filtered_items(self):
        """按搜索框文本过滤（不区分大小写的 Key 子串匹配）。"""
        items = self.cfg.items()
        text = self._search_text.strip().lower()
        if not text:
            return items
        return [(k, v) for k, v in items if text in k.lower()]

    def _on_search_changed(self, text):
        self._search_text = text
        self.refresh()

    def refresh(self):
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        items = self._filtered_items()
        if not items:
            tip = "无匹配条目" if self._search_text.strip() else "暂无条目"
            empty = QLabel(tip, self.list_widget)
            empty.setObjectName("emptyLabel")
            empty.setAlignment(Qt.AlignCenter)
            self.list_layout.addWidget(empty)
        for i, (k, v) in enumerate(items):
            card = EntryCard(k, v, self.list_widget)
            card.clicked.connect(self.copyRequested.emit)
            self.list_layout.addWidget(card)
            if i < len(items) - 1:
                self.list_layout.addWidget(make_separator())
        self.list_layout.addStretch(1)

    # ------------------------------------------------------ 显示 / 隐藏
    def show_on_screen(self, screen):
        """在指定屏幕的右上角弹出（带淡入），高度自适应但不超屏幕 60%。"""
        # 速览面板每次唤出都是全新视图，不残留上次的搜索词
        self.search_edit.clear()
        self.search_edit.clearFocus()
        self.refresh()
        g = screen.geometry()
        n = max(1, len(self._filtered_items()))
        content_h = 82 + n * 58  # 估算：头部 + 搜索框 + 每个条目约 58px
        h = max(170, min(content_h + WINDOW_MARGIN * 2, int(g.height() * 0.6)))
        x = g.right() - self.width() - 4
        y = g.top()
        self.setGeometry(x, y, self.width(), h)

        self.cancel_auto_hide()
        self._hiding = False
        self.setWindowOpacity(0.0)
        self.show()
        self._animate_opacity(0.0, 1.0, 180)

    def fade_out(self, duration=PANEL_LEAVE_FADE_MS):
        """透明度动画淡出后完全隐藏。"""
        if self._hiding or not self.isVisible():
            return
        self._hiding = True
        self._leave_timer.stop()

        def _done():
            self.hide()
            self.setWindowOpacity(1.0)
            self._hiding = False

        self._animate_opacity(self.windowOpacity(), 0.0, duration, _done)

    def is_hiding(self):
        return self._hiding

    def _animate_opacity(self, start, end, duration, on_finished=None):
        if self._fade is not None:
            self._fade.stop()
        anim = QPropertyAnimation(self, b"windowOpacity", self)
        anim.setDuration(duration)
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.setEasingCurve(QEasingCurve.InOutQuad)
        if on_finished is not None:
            anim.finished.connect(on_finished)
        # 不用 DeleteWhenStopped：动画以 self 为父对象随控件销毁，
        # 避免 self._fade 指向已删除的 C++ 对象
        anim.start()
        self._fade = anim

    # ------------------------------------------------------ 自动消失逻辑
    def schedule_auto_hide(self):
        """鼠标在面板外：启动 0.3s 延时（若鼠标及时回来则会被取消）。

        搜索框获得焦点时不隐藏——用户在打字时鼠标通常在面板外，
        此时隐藏会打断输入；焦点转移（点击别处）后下一轮轮询即恢复。
        """
        if self.search_edit.hasFocus():
            return
        if not self._hiding and not self._leave_timer.isActive():
            self._leave_timer.start()

    def cancel_auto_hide(self):
        self._leave_timer.stop()

    def _on_leave_timeout(self):
        self.fade_out(PANEL_LEAVE_FADE_MS)

    def visual_rect(self):
        """面板的可视区域（不含四周透明阴影边距），全局坐标。"""
        top_left = self.container.mapToGlobal(QPoint(0, 0))
        return QRect(top_left, self.container.size())

    def covers(self, pos):
        """判断光标是否应视为「在面板内」。

        除面板可视区域外，还把面板正上方到屏幕右上角的热区条带算进来，
        避免光标停在屏幕最角落时面板反复闪现。
        """
        if not self.isVisible():
            return False
        vr = self.visual_rect()
        if vr.contains(pos):
            return True
        screen = QGuiApplication.screenAt(pos) or QGuiApplication.primaryScreen()
        g = screen.geometry()
        corner_strip = QRect(vr.left(), g.top(),
                             g.right() - vr.left() + 1,
                             vr.bottom() - g.top() + 1)
        return corner_strip.contains(pos)


# ---------------------------------------------------------------- 主窗口
class MainWindow(QWidget):
    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("QuickCopy")

        self.cfg = ConfigManager()
        if not self.cfg.existed and not self.cfg.items():
            # 首次运行给一条示例，便于理解用法
            self.cfg.set("示例 Key（点击即复制）",
                         "这是一条示例 Value，可在列表中编辑或删除")

        self._selected_key = None
        self._cards = []
        self._tray_tip_shown = False
        self._search_text = ""

        # ---- 界面骨架 ----
        container = QFrame(self)
        container.setObjectName("appContainer")
        container.setGraphicsEffect(make_shadow())
        lay = QVBoxLayout(container)
        lay.setContentsMargins(10, 4, 10, 10)
        lay.setSpacing(6)

        lay.addWidget(TitleBar("QuickCopy", self.hide_to_tray,
                               self.hide_to_tray, container))

        self.search_edit = QLineEdit(container)
        self.search_edit.setPlaceholderText("搜索 Key…")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._on_search_changed)
        lay.addWidget(self.search_edit)

        self.scroll = QScrollArea(container)
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_widget = QWidget()
        self.list_widget.setObjectName("mainList")
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setContentsMargins(2, 0, 2, 4)
        self.list_layout.setSpacing(2)
        self.scroll.setWidget(self.list_widget)
        lay.addWidget(self.scroll, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.btn_add = QPushButton("添加", container)
        self.btn_add.setObjectName("primaryBtn")
        self.btn_add.clicked.connect(self.add_entry)
        self.btn_edit = QPushButton("编辑", container)
        self.btn_edit.setObjectName("actionBtn")
        self.btn_edit.clicked.connect(lambda: self.edit_entry())
        self.btn_del = QPushButton("删除", container)
        self.btn_del.setObjectName("actionBtn")
        self.btn_del.clicked.connect(self.delete_entry)
        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_edit)
        btn_row.addWidget(self.btn_del)
        lay.addLayout(btn_row)

        root = QVBoxLayout(self)
        root.setContentsMargins(WINDOW_MARGIN, WINDOW_MARGIN,
                                WINDOW_MARGIN, WINDOW_MARGIN)
        root.addWidget(container)
        self.resize(340, 460)

        # ---- 浮动面板 ----
        self.panel = FloatingPanel(self.cfg)
        self.panel.copyRequested.connect(self.copy_value)

        # ---- 系统托盘 ----
        self.tray = QSystemTrayIcon(load_app_icon(), self)
        self.tray.setToolTip("QuickCopy")
        tray_menu = QMenu()
        act_show = tray_menu.addAction("显示主界面")
        act_show.triggered.connect(self.show_main)
        self.act_autostart = tray_menu.addAction("开机自启")
        self.act_autostart.setCheckable(True)
        self.act_autostart.setChecked(get_autostart())
        # 勾选状态以注册表为准，连接 toggled 要在 setChecked 之后，
        # 避免初始化时被当成一次用户勾选
        self.act_autostart.toggled.connect(set_autostart)
        tray_menu.addSeparator()
        act_quit = tray_menu.addAction("退出 QuickCopy")
        act_quit.triggered.connect(self.quit_app)
        self.tray.setContextMenu(tray_menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

        # exe 被移动过会导致注册表里的自启路径失效，启动时按当前路径重写一遍
        if get_autostart():
            set_autostart(True)

        # ---- 鼠标位置轮询（右上角热区唤醒 + 面板自动消失）----
        self.mouse_timer = QTimer(self)
        self.mouse_timer.setInterval(POLL_INTERVAL)
        self.mouse_timer.timeout.connect(self._poll_mouse)
        self.mouse_timer.start()

        # 初始居中
        g = QGuiApplication.primaryScreen().availableGeometry()
        self.move(g.center() - self.rect().center())

        self.refresh_list()

    # ------------------------------------------------------ 列表
    def _filtered_items(self):
        """按搜索框文本过滤（不区分大小写的 Key 子串匹配）。"""
        items = self.cfg.items()
        text = self._search_text.strip().lower()
        if not text:
            return items
        return [(k, v) for k, v in items if text in k.lower()]

    def _on_search_changed(self, text):
        self._search_text = text
        self.refresh_list()

    def refresh_list(self):
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._cards = []

        items = self._filtered_items()
        if not items:
            if self._search_text.strip():
                tip = "无匹配条目"
            else:
                tip = "暂无条目\n点击下方「添加」创建第一条"
            empty = QLabel(tip, self.list_widget)
            empty.setObjectName("emptyLabel")
            empty.setAlignment(Qt.AlignCenter)
            self.list_layout.addWidget(empty)
        for i, (k, v) in enumerate(items):
            card = EntryCard(k, v, self.list_widget)
            card.clicked.connect(self._on_card_clicked)
            if k == self._selected_key:
                card.setSelected(True)
            self.list_layout.addWidget(card)
            self._cards.append(card)
            if i < len(items) - 1:
                self.list_layout.addWidget(make_separator())
        self.list_layout.addStretch(1)

    def _select(self, key):
        self._selected_key = key
        for card in self._cards:
            card.setSelected(card.key == key)

    # ------------------------------------------------------ 复制
    def _on_card_clicked(self, key):
        self._select(key)
        self.copy_value(key)

    def copy_value(self, key):
        """复制 Value -> 剪贴板，该 Key 置顶，面板 1s 内淡出。"""
        value = self.cfg.get(key)
        if value is None:
            return
        QGuiApplication.clipboard().setText(value)
        # 最近使用的 Key 置顶显示，方便下次快速找到
        self.cfg.move_to_top(key)
        self.refresh_list()
        self.scroll.verticalScrollBar().setValue(0)
        if self.panel.isVisible() and not self.panel.is_hiding():
            self.panel.fade_out(PANEL_COPY_FADE_MS)

    # ------------------------------------------------------ 增删改
    def add_entry(self):
        dlg = EntryDialog(self, "添加条目")
        if dlg.exec() == QDialog.Accepted:
            key, value = dlg.key(), dlg.value()
            if self.cfg.contains(key):
                QMessageBox.warning(self, "提示",
                                    f"Key「{key}」已存在，其 Value 已被覆盖。")
            self.cfg.set(key, value)
            self.refresh_list()
            self._select(key)

    def edit_entry(self, key=None):
        key = key or self._selected_key
        if not key or not self.cfg.contains(key):
            QMessageBox.information(self, "提示", "请先点击选择一个条目")
            return
        dlg = EntryDialog(self, "编辑条目", key, self.cfg.get(key) or "")
        if dlg.exec() == QDialog.Accepted:
            new_key, new_value = dlg.key(), dlg.value()
            if new_key != key:
                self.cfg.delete(key)
                if self.cfg.contains(new_key):
                    QMessageBox.warning(self, "提示",
                                        f"Key「{new_key}」已存在，其 Value 已被覆盖。")
            self.cfg.set(new_key, new_value)
            self.refresh_list()
            self._select(new_key)

    def delete_entry(self, key=None):
        key = key or self._selected_key
        if not key or not self.cfg.contains(key):
            QMessageBox.information(self, "提示", "请先点击选择一个条目")
            return
        ret = QMessageBox.question(
            self, "删除确认", f"确定删除「{key}」吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ret == QMessageBox.Yes:
            self.cfg.delete(key)
            if self._selected_key == key:
                self._selected_key = None
            self.refresh_list()

    # ------------------------------------------------------ 托盘与显隐
    def hide_to_tray(self):
        self.hide()
        if not self._tray_tip_shown:
            self._tray_tip_shown = True
            self.tray.showMessage(
                "QuickCopy", "已隐藏到系统托盘。\n鼠标移至屏幕最右上角可唤出速览面板。",
                QSystemTrayIcon.Information, 2500)

    def show_main(self):
        if self.panel.isVisible():
            self.panel.fade_out(200)
        self.show()
        self.raise_()
        self.activateWindow()

    def quit_app(self):
        self.tray.hide()
        self.panel.hide()
        QApplication.instance().quit()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_main()

    def closeEvent(self, event):
        # 关闭 = 隐藏到托盘，程序不退出（从托盘菜单「退出」才真正退出）
        event.ignore()
        self.hide_to_tray()

    # ------------------------------------------------------ 鼠标轮询
    def _poll_mouse(self):
        pos = QCursor.pos()
        screen = QGuiApplication.screenAt(pos) or QGuiApplication.primaryScreen()
        g = screen.geometry()

        # 主窗口隐藏时，光标进入屏幕最右上角热区 -> 唤出浮动面板
        if (not self.isVisible()
                and not self.panel.isVisible()
                and not self.panel.is_hiding()):
            if pos.x() >= g.right() - HOT_CORNER and pos.y() <= g.top() + HOT_CORNER:
                self.panel.show_on_screen(screen)

        # 面板展开中：光标离开面板 -> 0.3s 延时后自动淡出；回来则取消
        if self.panel.isVisible() and not self.panel.is_hiding():
            if self.panel.covers(pos):
                self.panel.cancel_auto_hide()
            else:
                self.panel.schedule_auto_hide()


# ---------------------------------------------------------------- 入口
def main():
    # 任务栏图标按 AppUserModelID 归组，不设置会回退到 python.exe 的图标
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("QuickCopy")

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # 关闭主窗口不退出，驻留托盘
    app.setApplicationName("QuickCopy")
    app.setStyleSheet(APP_QSS)
    app.setWindowIcon(load_app_icon())

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
