"""出灰授权：全应用唯一判断入口。

无论抽屉展示、抽屉保存还是池台账编辑，都走同一个
``can_mark_drawn``，避免各入口各写各的导致权限互相矛盾。
"""

from __future__ import annotations

ROLE_ADMIN = "admin"


def can_mark_drawn(user) -> bool:
    """仅管理员（role == "admin"）可将池标记为「已出灰」。"""
    if user is None:
        return False
    return getattr(user, "role", "") == ROLE_ADMIN
