"""今日卡片测试。"""
from app.services.dashboard import get_dashboard, onboard_day
from app.services.invite import create_invites, redeem


def test_get_dashboard():
    code = create_invites(1)[0]
    user_id = redeem(code, "小明")["user"]["id"]

    dash = get_dashboard(user_id)
    assert dash["onboard_day"] >= 1
    assert dash["todo_total"] == 7  # 自动 seed 的默认待办
    assert dash["suggestion"]


def test_onboard_day_min_one():
    assert onboard_day(999999) == 1  # 用户不存在时兜底为 1
