"""石灰熟化池业务规则。"""

from __future__ import annotations

from sqlalchemy import update

from app.extensions import db
from app.models import Pond, SlakeBatch
from app.services.draw_acl import user_can_mark_drawn

MIN_PEAK_TEMP_FOR_DRAWN = 60.0


class RuleError(ValueError):
    """业务规则校验失败。"""


def latest_batch_for_pond(pond: Pond) -> SlakeBatch | None:
    if not pond.batches:
        return None
    return max(pond.batches, key=lambda b: b.started_at)


def can_mark_pond_drawn(pond: Pond) -> tuple[bool, str]:
    """
    熟化池转为「已出灰」(drawn) 的前提：
    最近一条熟化批次的峰值温度已记录，且 >= 60℃。
    """
    latest = latest_batch_for_pond(pond)
    if latest is None:
        return False, "该池尚无熟化批次，不能标记为已出灰"
    if latest.peak_temp_c is None:
        return False, "最近批次尚未记录峰值温度，不能标记为已出灰"
    if latest.peak_temp_c < MIN_PEAK_TEMP_FOR_DRAWN:
        return (
            False,
            f"最近批次峰值温度 {latest.peak_temp_c}℃ 低于 {MIN_PEAK_TEMP_FOR_DRAWN:.0f}℃，不能标记为已出灰",
        )
    return True, ""


def assert_can_set_pond_status(pond: Pond, new_status: str) -> None:
    if new_status not in Pond.STATUS_CHOICES:
        raise RuleError(f"无效状态：{new_status}")
    if new_status == Pond.STATUS_DRAWN:
        ok, msg = can_mark_pond_drawn(pond)
        if not ok:
            raise RuleError(msg)


def set_pond_status(pond: Pond, new_status: str, user=None) -> None:
    """
    改池态的唯一落库入口，抽屉与台账共用，校验顺序固定：

    1. 转「已出灰」先看权限——仅管理员，操作工一律中文挡下（库不动）；
    2. 再走峰值门槛（最近批次峰值已记录且 >= 60℃），旧门槛不放宽；
    3. 出灰用条件更新：只有当前状态不是 drawn 才写得进去，
       两名管理员抢同一池时数据库层只放行一笔，第二笔报重复。

    成功只改状态并 flush，不代调用方 commit，以便与同一表单里的
    峰值/备注修改同事务提交或一起回滚。
    """
    if new_status not in Pond.STATUS_CHOICES:
        raise RuleError(f"无效状态：{new_status}")

    if new_status == Pond.STATUS_DRAWN:
        # 已是已出灰：任何人重存（补备注等）幂等放行，不触发出灰授权；
        # 操作工借此也无法把非已出灰的池推成已出灰（下面的跳变才校验）。
        if pond.status == Pond.STATUS_DRAWN:
            return
        if not user_can_mark_drawn(user):
            raise RuleError("只有管理员才能标记为已出灰")
        ok, msg = can_mark_pond_drawn(pond)
        if not ok:
            raise RuleError(msg)
        result = db.session.execute(
            update(Pond)
            .where(Pond.id == pond.id, Pond.status != Pond.STATUS_DRAWN)
            .values(status=Pond.STATUS_DRAWN)
        )
        if result.rowcount == 0:
            # 并发下另一笔已先出灰：双管理员抢点只许一笔成功。
            db.session.rollback()
            raise RuleError("该池刚已被标记为已出灰，请勿重复操作")
        pond.status = Pond.STATUS_DRAWN
        return

    pond.status = new_status
