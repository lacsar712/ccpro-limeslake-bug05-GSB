from math import isfinite

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Plant, Pond
from app.services.draw_acl import drawer_shows_drawn_option
from app.services.rules import RuleError, latest_batch_for_pond, set_pond_status

bp = Blueprint("board", __name__, url_prefix="/board")

STATUS_LABELS = {
    Pond.STATUS_FILLING: "注水中",
    Pond.STATUS_SLAKING: "熟化中",
    Pond.STATUS_DRAWN: "已出灰",
}


@bp.route("/")
@login_required
def floor_plan():
    plants = Plant.query.order_by(Plant.name).all()
    plant_id_raw = request.args.get("plant_id", "").strip()
    active_plant = None
    if plant_id_raw.isdigit():
        active_plant = db.session.get(Plant, int(plant_id_raw))
    if active_plant is None and plants:
        active_plant = plants[0]

    ponds = []
    if active_plant:
        ponds = (
            Pond.query.filter_by(plant_id=active_plant.id)
            .order_by(Pond.code)
            .all()
        )

    pond_cards = []
    for pond in ponds:
        batch = latest_batch_for_pond(pond)
        pond_cards.append({"pond": pond, "batch": batch})

    selected_id = request.args.get("pond", type=int)
    selected = None
    selected_batch = None
    if selected_id:
        selected = next((c["pond"] for c in pond_cards if c["pond"].id == selected_id), None)
        if selected:
            selected_batch = latest_batch_for_pond(selected)

    return render_template(
        "board/floor.html",
        plants=plants,
        active_plant=active_plant,
        pond_cards=pond_cards,
        selected=selected,
        selected_batch=selected_batch,
        status_labels=STATUS_LABELS,
        drawer_can_pick_drawn=drawer_shows_drawn_option(current_user),
    )


@bp.route("/ponds/<int:pond_id>/ops", methods=["POST"])
@login_required
def pond_ops(pond_id: int):
    pond = Pond.query.get_or_404(pond_id)
    status = request.form.get("status") or pond.status
    peak_raw = (request.form.get("peak_temp_c") or "").strip()
    notes = (request.form.get("batch_notes") or "").strip()

    redirect_kw = {"plant_id": pond.plant_id, "pond": pond.id}

    batch = latest_batch_for_pond(pond)
    if batch is None:
        flash("该池尚无熟化批次，无法登记峰值或出灰", "error")
        return redirect(url_for("board.floor_plan", **redirect_kw))

    try:
        # 峰值/备注与改态在同一事务：任何一环不通过都整笔回滚，
        # 绝不允许出现“提示失败但库已改 / 提示成功却没改”。
        if peak_raw:
            try:
                peak_value = float(peak_raw)
            except ValueError:
                raise RuleError("峰值温度格式无效")
            if not isfinite(peak_value):
                raise RuleError("峰值温度格式无效")
            batch.peak_temp_c = peak_value
        batch.notes = notes

        before_status = pond.status
        set_pond_status(pond, status, current_user)
        db.session.commit()
    except RuleError as exc:
        db.session.rollback()
        flash(str(exc), "error")
        return redirect(url_for("board.floor_plan", **redirect_kw))

    if status == Pond.STATUS_DRAWN and before_status != Pond.STATUS_DRAWN:
        flash(f"{pond.code} 已出灰", "ok")
    else:
        flash(f"{pond.code} 作业记录已保存", "ok")
    return redirect(url_for("board.floor_plan", **redirect_kw))
