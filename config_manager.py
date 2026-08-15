# -*- coding: utf-8 -*-
"""
QuickCopy 数据层：负责 Key-Value 的本地 JSON 持久化。

数据文件默认保存在程序（或 exe）同目录下的 quickcopy_data.json，
采用「先写临时文件再替换」的方式写入，避免中途断电导致文件损坏。
"""

import json
import os
import sys


class ConfigManager:
    def __init__(self, path=None):
        if path is None:
            # 打包成 exe 后，数据文件放到 exe 所在目录，便于迁移
            if getattr(sys, "frozen", False):
                base = os.path.dirname(sys.executable)
            else:
                base = os.path.dirname(os.path.abspath(__file__))
            path = os.path.join(base, "quickcopy_data.json")
        self.path = path
        self.existed = os.path.exists(self.path)
        self._items = []  # list[[key, value]]，用列表保证顺序稳定
        self.load()

    # ---------------------------------------------------------- 持久化
    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            raw = data.get("items", []) if isinstance(data, dict) else data
            self._items = [[str(k), str(v)] for k, v in raw]
        except FileNotFoundError:
            self._items = []
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            # 文件损坏：备份旧文件后从空数据重新开始，保证程序可启动
            try:
                os.replace(self.path, self.path + ".bak")
            except OSError:
                pass
            self._items = []

    def save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"items": self._items}, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)
        self.existed = True

    # ---------------------------------------------------------- 增删改查
    def keys(self):
        return [k for k, _ in self._items]

    def items(self):
        return [(k, v) for k, v in self._items]

    def contains(self, key):
        return any(k == key for k, _ in self._items)

    def get(self, key):
        for k, v in self._items:
            if k == key:
                return v
        return None

    def set(self, key, value):
        """新增或覆盖（同 Key 覆盖原 Value，保持原位置）。"""
        for pair in self._items:
            if pair[0] == key:
                pair[1] = value
                break
        else:
            self._items.append([key, value])
        self.save()

    def delete(self, key):
        self._items = [p for p in self._items if p[0] != key]
        self.save()

    def move_to_top(self, key):
        """把指定 Key 移到列表首位（复制后置顶），已在首位则不落盘。"""
        for i, (k, _) in enumerate(self._items):
            if k == key:
                if i != 0:
                    self._items.insert(0, self._items.pop(i))
                    self.save()
                return
