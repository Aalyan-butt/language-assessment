from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_test_app
from app.main import speaking_recording_assessment
from app.service import AccountService
from app.store import MemoryStore


def client_with_admin():
    store = MemoryStore()
    svc = AccountService(store, get_settings())
    svc.create_user(name="Main Admin", email="admin@example.com",
                    temporary_password="Strong!Pass1", role="admin",
                    attempts_allowed=1, actor=None)
    return TestClient(create_test_app(store)), store


def login(client, email="admin@example.com", password="Strong!Pass1"):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    body = response.json()
    return {"Authorization": f"Bearer {body['token']}", "X-CSRF-Token": body["csrf_token"]}


def test_login_allows_admin_actions_without_forced_password_change():
    client, _ = client_with_admin()
    headers = login(client)
    created = client.post("/api/v1/admin/users", headers=headers, json={
        "name": "Student One", "email": "student@example.com",
        "temporary_password": "Student!Pass1", "role": "student", "attempts_allowed": 1,
    })
    assert created.status_code == 201
    changed = client.post("/api/v1/auth/change-password", headers=headers, json={
        "current_password": "Strong!Pass1", "new_password": "NewStrong!Pass2"
    })
    assert changed.status_code == 200


def test_admin_create_and_student_cannot_list_users():
    client, _ = client_with_admin()
    headers = login(client)
    client.post("/api/v1/auth/change-password", headers=headers, json={
        "current_password": "Strong!Pass1", "new_password": "NewStrong!Pass2"
    })
    response = client.post("/api/v1/admin/users", headers=headers, json={
        "name": "Student One", "email": "student@example.com",
        "temporary_password": "Student!Pass1", "role": "student", "attempts_allowed": 1,
    })
    assert response.status_code == 201
    student_headers = login(client, "student@example.com", "Student!Pass1")
    forbidden = client.get("/api/v1/admin/users", headers=student_headers)
    assert forbidden.status_code == 403


def test_five_bad_logins_lock_student_but_never_admin():
    client, store = client_with_admin()
    service = AccountService(store, get_settings())
    service.create_user(
        name="Locked Student", email="locked@example.com",
        temporary_password="Student!Pass1", role="student",
        attempts_allowed=1, actor=None,
    )
    service.create_user(
        name="Unaffected Student", email="unaffected@example.com",
        temporary_password="Student!Pass1", role="student",
        attempts_allowed=1, actor=None,
    )
    for _ in range(5):
        client.post("/api/v1/auth/login", json={"email": "admin@example.com", "password": "wrong"})
    admin_login = client.post("/api/v1/auth/login", json={
        "email": "admin@example.com", "password": "Strong!Pass1"
    })
    assert admin_login.status_code == 200
    for _ in range(5):
        client.post("/api/v1/auth/login", json={"email": "locked@example.com", "password": "wrong"})
    locked = client.post("/api/v1/auth/login", json={
        "email": "locked@example.com", "password": "Student!Pass1"
    })
    assert locked.status_code == 423
    assert "Other accounts can still sign in" in locked.json()["error"]["message"]
    unaffected = client.post("/api/v1/auth/login", json={
        "email": "unaffected@example.com", "password": "Student!Pass1"
    })
    assert unaffected.status_code == 200


def test_student_submission_requires_three_mp3_files_and_blocks_second_attempt():
    client, store = client_with_admin()
    svc = AccountService(store, get_settings())
    svc.create_user(name="Student One", email="student@example.com",
                    temporary_password="Student!Pass1", role="student",
                    attempts_allowed=1, actor=None)
    headers = login(client, "student@example.com", "Student!Pass1")
    changed = client.post("/api/v1/auth/change-password", headers=headers, json={
        "current_password": "Student!Pass1", "new_password": "NewStudent!Pass2"
    })
    assert changed.status_code == 200
    mp3 = b"ID3" + (b"\x00" * 100)
    form = {
        "submission_id": "11111111-1111-4111-8111-111111111111",
        "started_at": "2026-10-28T10:00:00+00:00", "time_seconds": "300",
        "paste_flag": "false", "paste_events": "0",
        "writing_answer": "This is my own memorable day answer with enough words for the minimum validation rule.",
        "speaking_transcript_1": "", "speaking_transcript_2": "", "speaking_transcript_3": "",
        "speaking_metrics": '[{"duration":30,"rms":0.08,"silence_ratio":0.2,"clipping_ratio":0.001},{"duration":35,"rms":0.07,"silence_ratio":0.25,"clipping_ratio":0.001},{"duration":28,"rms":0.09,"silence_ratio":0.18,"clipping_ratio":0.002}]',
    }
    files = {f"audio_{i}": (f"answer-{i}.mp3", mp3, "audio/mpeg") for i in range(1, 4)}
    accepted = client.post("/api/v1/student/submissions", headers=headers, data=form, files=files)
    assert accepted.status_code == 201
    assert accepted.json()["duplicate"] is False
    form["submission_id"] = "22222222-2222-4222-8222-222222222222"
    rejected = client.post("/api/v1/student/submissions", headers=headers, data=form, files=files)
    assert rejected.status_code == 409


def test_rule_based_speaking_evidence_flags_short_quiet_paused_audio():
    report = speaking_recording_assessment(
        '[{"duration":5,"rms":0.005,"silence_ratio":0.8,"clipping_ratio":0},'
        '{"duration":30,"rms":0.08,"silence_ratio":0.2,"clipping_ratio":0.001},'
        '{"duration":30,"rms":0.7,"silence_ratio":0.1,"clipping_ratio":0.2}]'
    )
    assert len(report["answers"]) == 3
    assert report["answers"][0]["automated_recording_score"] < 3
    assert "pronunciation" in report["manual_required"]
    assert "does not measure pronunciation" in report["notice"]


def test_admin_can_edit_account_and_password_hash_is_never_returned():
    client, store = client_with_admin()
    headers = login(client)
    created = client.post("/api/v1/admin/users", headers=headers, json={
        "name": "Original Name", "email": "original@example.com",
        "temporary_password": "Student!Pass1", "role": "student", "attempts_allowed": 1,
    })
    user_id = created.json()["user"]["user_id"]
    updated = client.patch(f"/api/v1/admin/users/{user_id}", headers=headers, json={
        "name": "Updated Name", "email": "updated@example.com", "role": "student"
    })
    assert updated.status_code == 200
    listed = client.get("/api/v1/admin/users", headers=headers)
    account = next(item for item in listed.json()["users"] if item["user_id"] == user_id)
    assert account["name"] == "Updated Name"
    assert "password_hash" not in account and "password_salt" not in account


def test_teacher_override_csv_export_and_security_headers():
    client, store = client_with_admin()
    admin_headers = login(client)
    student = AccountService(store, get_settings()).create_user(
        name="CSV Student", email="csv@example.com", temporary_password="Student!Pass1",
        role="student", attempts_allowed=1, actor=None)
    store.append("Results", {
        "submission_id": "33333333-3333-4333-8333-333333333333",
        "user_id": student["user_id"], "name": "CSV Student", "email": "csv@example.com",
        "writing_answer": "=DANGEROUS()", "total_score": 12, "suggested_level": "A2",
    })
    override = client.patch(
        "/api/v1/admin/results/33333333-3333-4333-8333-333333333333/override",
        headers=admin_headers, json={"teacher_level": "B1", "teacher_notes": "Confirmed manually."},
    )
    assert override.status_code == 200
    assert store.find("Results", "submission_id", "33333333-3333-4333-8333-333333333333")["teacher_level"] == "B1"
    exported = client.get("/api/v1/admin/exports/results.csv", headers=admin_headers)
    assert exported.status_code == 200
    assert "'=DANGEROUS()" in exported.text
    health = client.get("/health")
    assert health.headers["x-frame-options"] == "DENY"
    assert "microphone=(self)" in health.headers["permissions-policy"]


def test_student_cannot_read_results_or_export():
    client, store = client_with_admin()
    AccountService(store, get_settings()).create_user(
        name="Student", email="student2@example.com", temporary_password="Student!Pass1",
        role="student", attempts_allowed=1, actor=None)
    headers = login(client, "student2@example.com", "Student!Pass1")
    assert client.get("/api/v1/admin/results", headers=headers).status_code == 403
    assert client.get("/api/v1/admin/exports/results.csv", headers=headers).status_code == 403
