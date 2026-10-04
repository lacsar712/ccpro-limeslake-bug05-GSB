"""出灰授权：全系统统一口径，仅管理员（role == "admin"）可出灰。

抽屉是否展示「已出灰」、平面图抽屉保存、池台账编辑保存三个入口
都必须走同一个判断，避免各入口各写各的导致权限漂移。
"""

from __future__ import annotations

ADMIN_ROLE = "admin"


def user_can_mark_drawn(user) -> bool:
    """是否允许将池标记为「已出灰」：仅管理员。"""
    if user is None:
        return False
    if not getattr(user, "is_authenticated", False):
        return False
    return getattr(user, "role", "") == ADMIN_ROLE


# 三个入口共用同一判断，保留语义化别名以免调用方各写一套。
def drawer_shows_drawn_option(user) -> bool:
    """抽屉展示：管理员看见「已出灰」选项，操作工藏掉。"""
    return user_can_mark_drawn(user)


def drawer_api_allows_drawn(user) -> bool:
    """平面图抽屉保存：仅管理员。"""
    return user_can_mark_drawn(user)


def ponds_edit_allows_drawn(user) -> bool:
    """池台账编辑保存：仅管理员。"""
    return user_can_mark_drawn(user)
