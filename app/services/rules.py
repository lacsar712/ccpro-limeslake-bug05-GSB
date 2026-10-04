"""石灰熟化池业务规则。"""

from __future__ import annotations

from sqlalchemy import update

from app.extensions import db
from app.models import Pond, SlakeBatch

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


def transition_pond_to_drawn(pond_id: int) -> bool:
    """
    原子地把池状态改为「已出灰」。

    UPDATE 的 WHERE 带上「当前不是已出灰」条件，数据库层面
    只放行第一笔并发事务；其余事务更新 0 行，返回 False。
    """
    result = db.session.execute(
        update(Pond)
        .where(Pond.id == pond_id, Pond.status != Pond.STATUS_DRAWN)
        .values(status=Pond.STATUS_DRAWN)
    )
    return result.rowcount == 1


def apply_pond_status(pond: Pond, new_status: str) -> None:
    """
    校验并应用池状态。

    「已出灰」只能成功一笔：并发抢点靠数据库原子更新挡，
    已出灰后的重复标记直接拒绝。其余状态直接赋值。
    """
    assert_can_set_pond_status(pond, new_status)
    if new_status == Pond.STATUS_DRAWN:
        if pond.status == Pond.STATUS_DRAWN:
            raise RuleError("该池已是已出灰状态，请勿重复标记")
        if not transition_pond_to_drawn(pond.id):
            raise RuleError("该池刚被其他人标记为已出灰，请刷新查看最新状态")
    else:
        pond.status = new_status
