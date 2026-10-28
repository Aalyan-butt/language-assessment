from __future__ import annotations

import uuid
import json
import csv
import io
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse
from fastapi.responses import StreamingResponse

from .config import get_settings
from .checker import analyse_submission
from .constants import RESULT_HEADERS
from .models import (
    AttemptsRequest, BulkUsersRequest, ChangePasswordRequest, CreateUserRequest,
    LoginRequest, ResetPasswordRequest, StatusRequest,
    UpdateUserRequest,
    TeacherOverrideRequest,
)
from .security import iso, password_hash, validate_password_strength
from .service import AccountService, public_user
from .store import GoogleSheetStore, MemoryStore
from .workspace import GoogleWorkspaceArtifacts

settings = get_settings()
PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAX_AUDIO_BYTES = 6 * 1024 * 1024
MAX_REQUEST_BYTES = 20 * 1024 * 1024


def speaking_recording_assessment(raw: str) -> dict:
    try:
        metrics = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid speaking recording metrics.")
    if not isinstance(metrics, list) or len(metrics) != 3:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Three speaking metric records are required.")
    answers = []
    for number, item in enumerate(metrics, 1):
        try:
            duration = max(0.0, min(90.0, float(item["duration"])))
            rms = max(0.0, min(1.0, float(item["rms"])))
            silence = max(0.0, min(1.0, float(item["silence_ratio"])))
            clipping = max(0.0, min(1.0, float(item["clipping_ratio"])))
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                f"Speaking answer {number} has invalid recording metrics.") from exc
        length_score = 5 if 20 <= duration <= 90 else 3 if duration >= 10 else 1
        audibility_score = 5 if .025 <= rms <= .35 else 3 if .012 <= rms <= .5 else 1
        continuity_score = 5 if silence <= .35 else 3 if silence <= .55 else 1
        quality_score = 5 if clipping < .01 else 3 if clipping < .05 else 1
        automated = round((length_score + audibility_score + continuity_score + quality_score) / 4, 1)
        feedback = []
        if duration < 20: feedback.append("The answer is short; give a fuller spoken response.")
        if rms < .025: feedback.append("The recording is quiet; speak closer to the microphone.")
        if silence > .35: feedback.append("There are frequent or long pauses for the recording length.")
        if clipping >= .01: feedback.append("The audio peaks or distorts; move slightly away from the microphone.")
        if not feedback: feedback.append("Recording length, continuity and signal quality are suitable for teacher review.")
        answers.append({"answer": number, "duration_seconds": round(duration, 1),
                        "rms": round(rms, 4), "silence_ratio": round(silence, 3),
                        "clipping_ratio": round(clipping, 4), "length_score": length_score,
                        "audibility_score": audibility_score, "continuity_score": continuity_score,
                        "recording_quality_score": quality_score,
                        "automated_recording_score": automated, "feedback": feedback})
    overall = round(sum(item["automated_recording_score"] for item in answers) / 3, 1)
    return {"overall_recording_score": overall, "answers": answers,
            "manual_required": ["fluency", "pronunciation", "word accuracy", "relevance", "natural speech"],
            "notice": "This automated score measures recording evidence only (length, audibility, pauses and clipping). It does not measure pronunciation or understand spoken words. A teacher must score the language."}


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not hasattr(app.state, "store"):
        if not settings.google_ready:
            raise RuntimeError("Google configuration is incomplete. Run scripts/setup_google.py first.")
        app.state.store = GoogleSheetStore(settings)
    yield


app = FastAPI(title="Kaplan English Placement API", version="0.2.0", lifespan=lifespan,
              docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))[:100]
    request.state.request_id = request_id
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > MAX_REQUEST_BYTES:
        return JSONResponse(status_code=413, content={"error": {
            "message": "Request is larger than the 20 MB safety limit.", "request_id": request_id,
        }})
    try:
        response = await call_next(request)
    except Exception:
        raise
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Permissions-Policy"] = "microphone=(self), camera=(), geolocation=()"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    return response


def service(request: Request) -> AccountService:
    return AccountService(request.app.state.store, settings)


def current_context(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> tuple[dict[str, str], dict[str, str]]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required.")
    return service(request).authenticate(authorization[7:])


def current_user(context=Depends(current_context)) -> dict[str, str]:
    return context[0]


def mutation_context(
    context=Depends(current_context),
    csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> tuple[dict[str, str], dict[str, str]]:
    if not csrf_token or csrf_token != context[1].get("csrf_nonce"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Request verification failed.")
    return context


def admin_user(context=Depends(mutation_context)) -> dict[str, str]:
    user = context[0]
    if user.get("role") != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator access required.")
    return user


@app.get("/health")
def health():
    return {"status": "ok", "service": "kaplan-placement-api"}


@app.get("/", include_in_schema=False)
def local_frontend():
    return FileResponse(PROJECT_ROOT / "index.html")


@app.get("/kaplan.png", include_in_schema=False)
def local_logo():
    return FileResponse(PROJECT_ROOT / "kaplan.png", media_type="image/png")


@app.get("/config.js", include_in_schema=False)
def local_frontend_config():
    return FileResponse(PROJECT_ROOT / "config.js", media_type="application/javascript")


@app.post("/api/v1/auth/login")
def login(payload: LoginRequest, request: Request):
    return service(request).login(str(payload.email), payload.password,
                                  request.headers.get("User-Agent", ""), request.state.request_id)


@app.get("/api/v1/auth/me")
def me(user=Depends(current_user)):
    return {"user": public_user(user)}


@app.post("/api/v1/auth/change-password")
def change_password(payload: ChangePasswordRequest, request: Request,
                    context=Depends(mutation_context)):
    service(request).change_password(context[0], payload.current_password, payload.new_password)
    for session in request.app.state.store.all("Sessions"):
        if (session.get("user_id") == context[0]["user_id"] and
                session.get("session_id") != context[1]["session_id"] and
                not session.get("revoked_at")):
            request.app.state.store.update("Sessions", "session_id", session["session_id"],
                                           {"revoked_at": iso()})
    return {"ok": True}


@app.post("/api/v1/auth/logout")
def logout(request: Request, context=Depends(mutation_context)):
    request.app.state.store.update("Sessions", "session_id", context[1]["session_id"],
                                   {"revoked_at": iso()})
    service(request).audit("LOGOUT", context[0], context[0])
    return {"ok": True}


@app.get("/api/v1/admin/users")
def list_users(request: Request, user=Depends(admin_user)):
    users = [public_user(item) for item in request.app.state.store.all("Users")]
    return {"users": sorted(users, key=lambda item: (item["role"] != "admin", item["name"].casefold()))}


@app.post("/api/v1/admin/users", status_code=201)
def create_user(payload: CreateUserRequest, request: Request, actor=Depends(admin_user)):
    user = service(request).create_user(name=payload.name, email=str(payload.email),
        temporary_password=payload.temporary_password, role=payload.role,
        attempts_allowed=payload.attempts_allowed, actor=actor)
    if payload.role == "admin" and isinstance(request.app.state.store, GoogleSheetStore):
        GoogleWorkspaceArtifacts(settings, request.app.state.store).share_existing_with_admin(str(payload.email))
    return {"user": user, "temporary_password_shown_once": True}


@app.post("/api/v1/admin/users/bulk", status_code=201)
def bulk_create(payload: BulkUsersRequest, request: Request, actor=Depends(admin_user)):
    created, rejected = [], []
    for item in payload.users:
        try:
            created.append(service(request).create_user(name=item.name, email=str(item.email),
                temporary_password=item.temporary_password, role="student",
                attempts_allowed=item.attempts_allowed, actor=actor))
        except HTTPException as exc:
            rejected.append({"email": str(item.email), "reason": exc.detail})
    return {"created": created, "rejected": rejected, "temporary_passwords_shown_once": True}


def target_user(request: Request, user_id: str) -> dict[str, str]:
    found = request.app.state.store.find("Users", "user_id", user_id)
    if not found:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Account not found.")
    return found


@app.patch("/api/v1/admin/users/{user_id}/status")
def set_status(user_id: str, payload: StatusRequest, request: Request, actor=Depends(admin_user)):
    target = target_user(request, user_id)
    if target["user_id"] == actor["user_id"] and payload.status == "disabled":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot disable your own account.")
    if target.get("role") == "admin" and payload.status == "disabled":
        active_admins = [item for item in request.app.state.store.all("Users")
                         if item.get("role") == "admin" and item.get("status") == "active"]
        if len(active_admins) <= 1:
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                "The final active administrator cannot be disabled.")
    request.app.state.store.update("Users", "user_id", user_id,
        {"status": payload.status, "updated_at": iso()})
    service(request).audit("USER_STATUS_CHANGED", actor, target, details={"status": payload.status})
    return {"ok": True}


@app.patch("/api/v1/admin/users/{user_id}")
def update_user(user_id: str, payload: UpdateUserRequest, request: Request,
                actor=Depends(admin_user)):
    target = target_user(request, user_id)
    changes = {"updated_at": iso()}
    if payload.name is not None:
        changes["name"] = payload.name
    if payload.email is not None:
        new_email = str(payload.email).casefold()
        existing = request.app.state.store.find("Users", "email", new_email)
        if existing and existing["user_id"] != user_id:
            raise HTTPException(status.HTTP_409_CONFLICT, "That email address is already in use.")
        changes["email"] = new_email
    if payload.role is not None:
        if target["user_id"] == actor["user_id"] and payload.role != "admin":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot remove your own administrator role.")
        changes["role"] = payload.role
    request.app.state.store.update("Users", "user_id", user_id, changes)
    service(request).audit("USER_UPDATED", actor, target,
                           details={k: v for k, v in changes.items() if k != "updated_at"})
    if payload.role == "admin" and target.get("role") != "admin" and isinstance(request.app.state.store, GoogleSheetStore):
        GoogleWorkspaceArtifacts(settings, request.app.state.store).share_existing_with_admin(
            changes.get("email", target["email"]))
    return {"user": public_user(request.app.state.store.find("Users", "user_id", user_id))}


@app.patch("/api/v1/admin/users/{user_id}/password")
def reset_password(user_id: str, payload: ResetPasswordRequest, request: Request,
                   actor=Depends(admin_user)):
    target = target_user(request, user_id)
    try:
        validate_password_strength(payload.temporary_password)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    encoded, salt = password_hash(payload.temporary_password)
    request.app.state.store.update("Users", "user_id", user_id, {
        "password_hash": encoded, "password_salt": salt,
        "password_version": int(target.get("password_version") or 1) + 1,
        "must_change_password": False, "failed_login_count": 0, "locked_until": "",
        "updated_at": iso(),
    })
    for session in request.app.state.store.all("Sessions"):
        if session.get("user_id") == user_id and not session.get("revoked_at"):
            request.app.state.store.update("Sessions", "session_id", session["session_id"],
                                           {"revoked_at": iso()})
    service(request).audit("PASSWORD_RESET", actor, target)
    return {"ok": True, "temporary_password_shown_once": True}


@app.patch("/api/v1/admin/users/{user_id}/attempts")
def set_attempts(user_id: str, payload: AttemptsRequest, request: Request,
                 actor=Depends(admin_user)):
    target = target_user(request, user_id)
    if target.get("role") != "student":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Attempts apply only to students.")
    request.app.state.store.update("Users", "user_id", user_id,
        {"attempts_allowed": payload.attempts_allowed, "updated_at": iso()})
    service(request).audit("ATTEMPTS_CHANGED", actor, target,
                           details={"attempts_allowed": payload.attempts_allowed})
    return {"ok": True}


def student_for_submission(context=Depends(mutation_context)) -> dict[str, str]:
    user = context[0]
    if user.get("role") != "student":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Student access required.")
    return user


async def valid_mp3(upload: UploadFile, label: str) -> bytes:
    if upload.content_type not in {"audio/mpeg", "audio/mp3", "application/octet-stream"}:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, f"{label} must be an MP3 file.")
    content = await upload.read(MAX_AUDIO_BYTES + 1)
    if not content or len(content) > MAX_AUDIO_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            f"{label} must be between 1 byte and 6 MB.")
    is_mp3 = content.startswith(b"ID3") or (len(content) > 1 and content[0] == 0xFF and content[1] & 0xE0 == 0xE0)
    if not is_mp3:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"{label} is not a valid MP3 recording.")
    return content


@app.post("/api/v1/student/submissions", status_code=201)
async def create_submission(
    request: Request,
    submission_id: Annotated[str, Form(min_length=36, max_length=36)],
    started_at: Annotated[str, Form(max_length=40)],
    time_seconds: Annotated[int, Form(ge=1, le=14400)],
    paste_flag: Annotated[bool, Form()],
    paste_events: Annotated[int, Form(ge=0, le=1000)],
    writing_answer: Annotated[str, Form(min_length=20, max_length=5000)],
    speaking_transcript_1: Annotated[str, Form(max_length=3000)] = "",
    speaking_transcript_2: Annotated[str, Form(max_length=3000)] = "",
    speaking_transcript_3: Annotated[str, Form(max_length=3000)] = "",
    speaking_metrics: Annotated[str, Form(max_length=2000)] = "[]",
    audio_1: UploadFile = File(...),
    audio_2: UploadFile = File(...),
    audio_3: UploadFile = File(...),
    user=Depends(student_for_submission),
):
    try:
        uuid.UUID(submission_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid submission identifier.") from exc
    store = request.app.state.store
    existing = store.find("Results", "submission_id", submission_id)
    if existing:
        return {"ok": True, "submission_id": submission_id, "duplicate": True}
    allowed = int(user.get("attempts_allowed") or 1)
    used = int(user.get("attempts_used") or 0)
    if used >= allowed:
        raise HTTPException(status.HTTP_409_CONFLICT, "No test attempts remain for this account.")
    recordings = [
        await valid_mp3(audio_1, "Speaking answer 1"),
        await valid_mp3(audio_2, "Speaking answer 2"),
        await valid_mp3(audio_3, "Speaking answer 3"),
    ]
    words = len(writing_answer.split())
    submitted_at = iso()
    report = analyse_submission(writing_answer, [
        speaking_transcript_1, speaking_transcript_2, speaking_transcript_3,
    ])
    writing_report = report["writing"]
    speaking_assessment = speaking_recording_assessment(speaking_metrics)
    metrics = writing_report["metrics"]
    scores = writing_report["scores"]
    artifacts = {"audio_folder_url": "", "doc_url": "", "audio_urls": ["", "", ""]}
    if isinstance(store, GoogleSheetStore):
        try:
            artifacts = GoogleWorkspaceArtifacts(settings, store).create_submission(
                submission_id=submission_id, user=user, writing=writing_answer,
                transcripts=[speaking_transcript_1, speaking_transcript_2, speaking_transcript_3],
                recordings=recordings, report=writing_report, speaking=speaking_assessment,
            )
        except Exception as exc:
            store.append("Jobs", {
                "job_id": str(uuid.uuid4()), "submission_id": submission_id,
                "job_type": "submission_upload_retry_required", "status": "failed",
                "attempt_count": 1, "next_attempt_at": "", "last_error": str(exc)[:500],
                "created_at": submitted_at, "updated_at": submitted_at,
            })
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                                "Google storage is temporarily unavailable. Your attempt was not used; please submit again.") from exc
    store.append("Results", {
        "submission_id": submission_id, "user_id": user["user_id"], "name": user["name"],
        "email": user["email"], "started_at": started_at, "submitted_at": submitted_at,
        "time_seconds": time_seconds, "paste_flag": paste_flag, "paste_events": paste_events,
        "writing_answer": writing_answer, "speaking_transcript_1": speaking_transcript_1,
        "speaking_transcript_2": speaking_transcript_2,
        "speaking_transcript_3": speaking_transcript_3, "word_count": metrics["word_count"],
        "sentence_count": metrics["sentence_count"],
        "average_sentence_length": metrics["average_sentence_length"],
        "unique_word_ratio": metrics["unique_word_ratio"],
        "grammar_score": scores["grammar"],
        "spelling_punctuation_score": scores["spelling_punctuation"],
        "vocabulary_score": scores["vocabulary"], "task_length_score": scores["task_length"],
        "total_score": writing_report["total"], "suggested_level": writing_report["level"],
        "formula_version": writing_report["formula_version"],
        "error_count": len(writing_report["issues"]),
        "errors_per_100_words": writing_report["errors_per_100_words"],
        "topic_flag": writing_report["topic_flag"], "check_status": "complete",
        "report_status": "pending_document", "speaking_auto_score": speaking_assessment["overall_recording_score"],
        "speaking_audio_feedback": " | ".join(
            f"Answer {item['answer']}: {' '.join(item['feedback'])}" for item in speaking_assessment["answers"]),
        "speaking_metrics_json": json.dumps(speaking_assessment, separators=(",", ":")),
        "report_json": json.dumps({**writing_report, "speaking_recording": speaking_assessment},
                                  ensure_ascii=False, separators=(",", ":")),
        "doc_url": artifacts["doc_url"], "audio_folder_url": artifacts["audio_folder_url"],
        "audio_1_url": artifacts["audio_urls"][0], "audio_2_url": artifacts["audio_urls"][1],
        "audio_3_url": artifacts["audio_urls"][2],
    })
    error_rows = []
    all_reports = [writing_report] + [item for item in report["speaking"] if item]
    for checked in all_reports:
        for issue in checked["issues"]:
            error_rows.append({
                "error_id": str(uuid.uuid4()), "submission_id": submission_id,
                "user_id": user["user_id"], "student_email": user["email"],
                "answer_section": issue["section"], "category": issue["category"],
                "original_text": issue["original"], "start_position": issue["start"],
                "end_position": issue["end"], "suggested_correction": issue["correction"],
                "explanation": issue["explanation"], "rule_id": issue["rule_id"],
                "checker_version": checked["checker_version"],
            })
    store.append_many("Errors", error_rows)
    # Stage 3 validates the complete MP3 payload. Stage 5 replaces this temporary
    # local preview storage with immediate private Google Drive uploads.
    if isinstance(store, MemoryStore):
        preview = PROJECT_ROOT / ".local-audio" / submission_id
        preview.mkdir(parents=True, exist_ok=True)
        for number, content in enumerate(recordings, start=1):
            (preview / f"answer-{number}.mp3").write_bytes(content)
    else:
        store.set_result_hyperlinks(submission_id, artifacts["audio_urls"])
    store.update("Users", "user_id", user["user_id"], {
        "attempts_used": used + 1, "updated_at": submitted_at,
    })
    service(request).audit("TEST_SUBMITTED", user, user,
                           details={"submission_id": submission_id, "word_count": words})
    return {"ok": True, "submission_id": submission_id, "duplicate": False}


@app.get("/api/v1/admin/results")
def list_results(request: Request, actor=Depends(admin_user)):
    rows = request.app.state.store.all("Results")
    safe = []
    for row in rows:
        safe.append({key: value for key, value in row.items()
                     if key not in {"report_json", "writing_answer", "speaking_transcript_1",
                                    "speaking_transcript_2", "speaking_transcript_3"}})
    safe.sort(key=lambda item: item.get("submitted_at", ""), reverse=True)
    return {"results": safe}


@app.get("/api/v1/admin/results/{submission_id}")
def result_detail(submission_id: str, request: Request, actor=Depends(admin_user)):
    row = request.app.state.store.find("Results", "submission_id", submission_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Submission not found.")
    try:
        report = json.loads(row.get("report_json") or "{}")
    except json.JSONDecodeError:
        report = {}
    errors = [item for item in request.app.state.store.all("Errors")
              if item.get("submission_id") == submission_id]
    return {"result": {k: v for k, v in row.items() if k != "report_json"},
            "report": {"writing": report}, "errors": errors}


@app.get("/api/v1/admin/results/{submission_id}/pdf")
def download_result_pdf(submission_id: str, request: Request, actor=Depends(admin_user)):
    row = request.app.state.store.find("Results", "submission_id", submission_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Submission not found.")
    if not isinstance(request.app.state.store, GoogleSheetStore):
        raise HTTPException(status.HTTP_409_CONFLICT, "PDF export requires Google storage.")
    try:
        content = GoogleWorkspaceArtifacts(settings, request.app.state.store).export_report_pdf(
            row.get("doc_url", "")
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "The PDF could not be exported from Google Drive. Try again.") from exc
    filename = "".join(c if c.isalnum() or c in "-_" else "-" for c in row.get("name", "student"))
    service(request).audit("REPORT_PDF_DOWNLOADED", actor, details={"submission_id": submission_id})
    return StreamingResponse(iter([content]), media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="Kaplan-{filename or "student"}-report.pdf"'
    })


@app.get("/api/v1/admin/results/{submission_id}/audio/{answer_number}")
def stream_result_audio(submission_id: str, answer_number: int, request: Request,
                        download: bool = False, actor=Depends(admin_user)):
    if answer_number not in {1, 2, 3}:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recording not found.")
    row = request.app.state.store.find("Results", "submission_id", submission_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Submission not found.")
    if not isinstance(request.app.state.store, GoogleSheetStore):
        raise HTTPException(status.HTTP_409_CONFLICT, "Audio streaming requires Google storage.")
    try:
        content = GoogleWorkspaceArtifacts(settings, request.app.state.store).download_recording(
            row.get(f"audio_{answer_number}_url", "")
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "The recording could not be loaded from Google Drive.") from exc
    disposition = "attachment" if download else "inline"
    return StreamingResponse(iter([content]), media_type="audio/mpeg", headers={
        "Content-Disposition": f'{disposition}; filename="answer-{answer_number}.mp3"',
        "Cache-Control": "private, max-age=300",
    })


@app.patch("/api/v1/admin/results/{submission_id}/override")
def save_teacher_override(submission_id: str, payload: TeacherOverrideRequest,
                          request: Request, actor=Depends(admin_user)):
    row = request.app.state.store.find("Results", "submission_id", submission_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Submission not found.")
    changes = {"teacher_level": payload.teacher_level, "teacher_notes": payload.teacher_notes,
               "override_by": actor["email"], "override_at": iso()}
    request.app.state.store.update("Results", "submission_id", submission_id, changes)
    service(request).audit("RESULT_OVERRIDE_SAVED", actor,
                           {"user_id": row.get("user_id", ""), "email": row.get("email", "")},
                           details={"submission_id": submission_id,
                                    "teacher_level": payload.teacher_level})
    return {"ok": True, **changes}


@app.get("/api/v1/admin/exports/results.csv")
def export_results_csv(request: Request, actor=Depends(admin_user)):
    excluded = {"report_json", "speaking_metrics_json"}
    headers = [name for name in RESULT_HEADERS if name not in excluded]
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(headers)
    for row in request.app.state.store.all("Results"):
        writer.writerow([csv_safe(row.get(name, "")) for name in headers])
    service(request).audit("RESULTS_EXPORTED", actor, details={"format": "csv"})
    return StreamingResponse(iter([stream.getvalue()]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": "attachment; filename=kaplan-results.csv"})


def csv_safe(value: str) -> str:
    text = str(value or "")
    return "'" + text if text[:1] in {"=", "+", "-", "@"} else text


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code,
                        content={"error": {"message": exc.detail, "request_id": request.state.request_id}})


def create_test_app(store: MemoryStore) -> FastAPI:
    """Attach an isolated store before TestClient starts the normal app lifespan."""
    app.state.store = store
    return app
