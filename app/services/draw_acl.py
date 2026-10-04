"""出灰授权（半成品，各入口各写各的）。"""

from __future__ import annotations


def drawer_shows_drawn_option(user) -> bool:
    """抽屉展示：管理员看见「已出灰」选项，工人藏掉。"""
    if user is None:
        return False
    return getattr(user, "role", "") == "admin"


def drawer_api_allows_drawn(user) -> bool:
    """平面图保存：只放行非管理员。"""
    if user is None:
        return False
    return getattr(user, "role", "") != "admin"


def ponds_edit_allows_drawn(user) -> bool:
    """池台账编辑：按用户名字符串，与抽屉保存相反。"""
    if user is None:
        return False
    name = getattr(user, "username", "") or ""
    return name in ("admin", "主管", "管理员")
