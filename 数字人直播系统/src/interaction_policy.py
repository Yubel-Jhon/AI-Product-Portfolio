"""interaction_policy.py — 互动决策层（v0.2 自研两块之一）

决定「现在该说什么、带什么情绪」，是「主播感」的来源。
及格版：事件优先级 + 冷却（说话时不打断）+ 定时主动引导循环文案。
开场白从语料库读（loop_lines），切换语料时 set_loop_lines() 更新。
"""
import time
from dataclasses import dataclass

# 优先级：数字越小越优先（对齐 spec §4.2）。本地 mock 阶段只有 comment 用得到。
PRIORITY = {"sc": 0, "gift": 1, "comment": 2, "enter": 3, "follow": 4}

DEFAULT_LOOP_LINES = ["欢迎来到直播间，点个关注不迷路～"]


@dataclass
class Event:
    type: str          # comment / enter / follow / gift / sc
    user: str
    content: str = ""


class InteractionPolicy:
    def __init__(self, cooldown=4.0, loop_interval=30.0, loop_lines=None):
        self.cooldown = cooldown
        self.loop_interval = loop_interval
        self._loop_lines = list(loop_lines or DEFAULT_LOOP_LINES)
        self._queue = []
        self._last_spoke = 0.0
        self._loop_at = time.time() + loop_interval
        self._loop_idx = 0

    def set_loop_lines(self, loop_lines):
        """切换语料时更新开场白。"""
        if loop_lines:
            self._loop_lines = list(loop_lines)
            self._loop_idx = 0

    def push(self, event: Event):
        self._queue.append(event)
        self._queue.sort(key=lambda e: PRIORITY.get(e.type, 9))

    def next_event(self):
        """队首事件出列；冷却中（刚说完）返回 None，不打断。"""
        if not self._queue:
            return None
        if time.time() - self._last_spoke < self.cooldown:
            return None
        self._last_spoke = time.time()
        return self._queue.pop(0)

    def loop_line(self):
        """空闲且到点 → 返回一条主动引导文案；否则 None。"""
        if self._queue:
            return None
        if time.time() - self._last_spoke < self.cooldown:
            return None
        if time.time() < self._loop_at:
            return None
        self._loop_at = time.time() + self.loop_interval
        self._last_spoke = time.time()
        line = self._loop_lines[self._loop_idx % len(self._loop_lines)]
        self._loop_idx += 1
        return line
