"""生产邀请码管理接口：仅管理员或服务令牌可用。"""


def test_admin_invite_requires_auth(api_client):
    response = api_client.post("/api/v1/admin/invites", json={"count": 1})
    assert response.status_code == 401


def test_regular_user_cannot_create_invites(auth_client):
    response = auth_client.post("/api/v1/admin/invites", json={"count": 1})
    assert response.status_code == 403


def test_service_can_create_and_revoke_invite(api_client, service_auth):
    created = api_client.post(
        "/api/v1/admin/invites",
        json={"count": 2, "note": "线上首批"},
        headers=service_auth,
    )
    assert created.status_code == 200
    codes = created.json()["codes"]
    assert len(codes) == 2
    assert all(code.startswith("IT-") for code in codes)

    revoked = api_client.post(
        "/api/v1/admin/invites/revoke",
        json={"invite_code": codes[0]},
        headers=service_auth,
    )
    assert revoked.status_code == 200
    rejected = api_client.post(
        "/api/v1/auth/invite",
        json={"invite_code": codes[0], "nickname": "不应登录"},
    )
    assert rejected.status_code == 400

    accepted = api_client.post(
        "/api/v1/auth/invite",
        json={"invite_code": codes[1], "nickname": "线上用户"},
    )
    assert accepted.status_code == 200
