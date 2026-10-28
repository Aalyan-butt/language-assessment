USER_HEADERS = [
    "user_id", "email", "name", "role", "password_hash", "password_salt",
    "password_version", "must_change_password", "status", "attempts_allowed",
    "attempts_used", "failed_login_count", "locked_until", "created_at",
    "created_by", "last_login_at", "updated_at",
]

SESSION_HEADERS = [
    "session_id", "user_id", "token_hash", "csrf_nonce", "created_at",
    "last_activity_at", "expires_at", "revoked_at", "user_agent",
]

RESULT_HEADERS = [
    "submission_id", "user_id", "name", "email", "started_at", "submitted_at",
    "time_seconds", "paste_flag", "paste_events", "writing_answer",
    "speaking_transcript_1", "speaking_transcript_2", "speaking_transcript_3",
    "word_count", "sentence_count", "average_sentence_length", "unique_word_ratio",
    "grammar_score", "spelling_punctuation_score", "vocabulary_score",
    "task_length_score", "total_score", "suggested_level", "formula_version",
    "error_count", "errors_per_100_words", "topic_flag", "check_status",
    "report_status", "doc_url", "audio_folder_url", "audio_1_url", "audio_2_url",
    "audio_3_url", "teacher_level", "fluency_score", "pronunciation_score",
    "speaking_length_score", "speaking_relevance_score", "teacher_notes",
    "override_by", "override_at", "speaking_auto_score", "speaking_audio_feedback",
    "speaking_metrics_json", "report_json", "audio_1_play", "audio_2_play", "audio_3_play",
]

ERROR_HEADERS = [
    "error_id", "submission_id", "user_id", "student_email", "answer_section",
    "category", "original_text", "start_position", "end_position",
    "suggested_correction", "explanation", "rule_id", "checker_version",
]

SETTING_HEADERS = ["key", "value", "value_type", "description", "updated_at", "updated_by"]
LESSON_HEADERS = [
    "lesson_id", "category", "title", "rule", "correct_examples",
    "common_mistake", "display_order", "enabled",
]
AUDIT_HEADERS = [
    "timestamp", "actor_user_id", "actor_email", "action", "target_user_id",
    "target_email", "success", "details", "request_id", "user_agent",
]
JOB_HEADERS = [
    "job_id", "submission_id", "job_type", "status", "attempt_count",
    "next_attempt_at", "last_error", "created_at", "updated_at",
]

SHEET_HEADERS = {
    "Users": USER_HEADERS,
    "Sessions": SESSION_HEADERS,
    "Results": RESULT_HEADERS,
    "Errors": ERROR_HEADERS,
    "Settings": SETTING_HEADERS,
    "Lessons": LESSON_HEADERS,
    "Audit": AUDIT_HEADERS,
    "Jobs": JOB_HEADERS,
}
