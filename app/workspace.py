"""Google Drive/Docs artefact generation for accepted submissions."""
from __future__ import annotations

import html
import io
import json
import re
from dataclasses import dataclass
from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

from .config import Settings
from .store import Store


@dataclass
class GoogleWorkspaceArtifacts:
    settings: Settings
    store: Store

    def __post_init__(self) -> None:
        credentials = Credentials(
            token=None, refresh_token=self.settings.google_refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.settings.google_client_id,
            client_secret=self.settings.google_client_secret,
            scopes=["https://www.googleapis.com/auth/spreadsheets",
                    "https://www.googleapis.com/auth/drive"],
        )
        self.drive = build("drive", "v3", credentials=credentials, cache_discovery=False)

    def create_submission(self, *, submission_id: str, user: dict[str, str],
                          writing: str, transcripts: list[str], recordings: list[bytes],
                          report: dict[str, Any], speaking: dict[str, Any]) -> dict[str, Any]:
        student_folder = self._folder(
            parent=self.settings.google_drive_folder_id,
            name=f"{user['name']} — {user['email']}",
            property_name="student_user_id", property_value=user["user_id"],
        )
        attempt_folder = self._folder(
            parent=student_folder, name=f"Submission — {submission_id}",
            property_name="submission_id", property_value=submission_id,
        )
        audio = []
        for number, content in enumerate(recordings, 1):
            audio.append(self._upload_mp3(attempt_folder, f"Speaking answer {number}.mp3", content))
        doc = self._create_doc(attempt_folder, submission_id, user, writing, transcripts,
                               report, speaking, audio)
        self._share_with_admins(attempt_folder)
        return {
            "audio_folder_url": f"https://drive.google.com/drive/folders/{attempt_folder}",
            "doc_url": doc["webViewLink"], "audio_urls": [item["webViewLink"] for item in audio],
        }

    def export_report_pdf(self, doc_url: str) -> bytes:
        """Export one private Google Doc as a PDF for an authorised admin."""
        match = re.search(r"/document/d/([A-Za-z0-9_-]+)", doc_url or "")
        if not match:
            raise ValueError("This submission does not have an exportable Google Doc.")
        output = io.BytesIO()
        request = self.drive.files().export_media(
            fileId=match.group(1), mimeType="application/pdf"
        )
        downloader = MediaIoBaseDownload(output, request)
        done = False
        while not done:
            _, done = downloader.next_chunk(num_retries=2)
        return output.getvalue()

    def download_recording(self, audio_url: str) -> bytes:
        """Download one private Drive MP3 for an authenticated admin."""
        match = re.search(r"/file/d/([A-Za-z0-9_-]+)", audio_url or "")
        if not match:
            raise ValueError("This recording does not have a valid Google Drive link.")
        output = io.BytesIO()
        request = self.drive.files().get_media(fileId=match.group(1))
        downloader = MediaIoBaseDownload(output, request)
        done = False
        while not done:
            _, done = downloader.next_chunk(num_retries=2)
        return output.getvalue()

    def share_existing_with_admin(self, email: str) -> None:
        for result in self.store.all("Results"):
            url = result.get("audio_folder_url", "")
            match = re.search(r"/folders/([A-Za-z0-9_-]+)", url)
            if not match:
                continue
            try:
                self.drive.permissions().create(
                    fileId=match.group(1),
                    body={"type": "user", "role": "reader", "emailAddress": email},
                    sendNotificationEmail=False, fields="id",
                ).execute()
            except Exception:
                continue

    def _folder(self, *, parent: str, name: str, property_name: str, property_value: str) -> str:
        safe_value = property_value.replace("'", "\\'")
        query = (f"'{parent}' in parents and trashed=false and "
                 f"mimeType='application/vnd.google-apps.folder' and "
                 f"appProperties has {{ key='{property_name}' and value='{safe_value}' }}")
        found = self.drive.files().list(q=query, fields="files(id)", pageSize=1).execute().get("files", [])
        if found:
            return found[0]["id"]
        created = self.drive.files().create(body={
            "name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent],
            "appProperties": {property_name: property_value},
        }, fields="id").execute()
        return created["id"]

    def _upload_mp3(self, parent: str, name: str, content: bytes) -> dict[str, str]:
        escaped = name.replace("'", "\\'")
        found = self.drive.files().list(
            q=f"'{parent}' in parents and trashed=false and name='{escaped}'",
            fields="files(id,webViewLink)", pageSize=1,
        ).execute().get("files", [])
        media = MediaIoBaseUpload(io.BytesIO(content), mimetype="audio/mpeg", resumable=False)
        if found:
            return self.drive.files().update(fileId=found[0]["id"], media_body=media,
                                             fields="id,webViewLink").execute()
        return self.drive.files().create(
            body={"name": name, "parents": [parent], "appProperties": {"kind": "speaking-audio"}},
            media_body=media, fields="id,webViewLink",
        ).execute()

    def _create_doc(self, parent: str, submission_id: str, user: dict[str, str], writing: str,
                    transcripts: list[str], report: dict[str, Any], speaking: dict[str, Any],
                    audio: list[dict[str, str]]) -> dict[str, str]:
        name = f"Kaplan Placement Report — {user['name']}"
        query = (f"'{parent}' in parents and trashed=false and "
                 "mimeType='application/vnd.google-apps.document'")
        found = self.drive.files().list(q=query, fields="files(id,webViewLink)", pageSize=1).execute().get("files", [])
        if found:
            return found[0]
        body = self._report_html(user, writing, transcripts, report, speaking, audio)
        media = MediaIoBaseUpload(io.BytesIO(body.encode("utf-8")), mimetype="text/html", resumable=False)
        return self.drive.files().create(body={
            "name": name, "mimeType": "application/vnd.google-apps.document", "parents": [parent],
            "appProperties": {"submission_id": submission_id},
        }, media_body=media, fields="id,webViewLink").execute()

    def _share_with_admins(self, folder_id: str) -> None:
        for admin in self.store.all("Users"):
            if admin.get("role") != "admin" or admin.get("status") != "active":
                continue
            try:
                self.drive.permissions().create(
                    fileId=folder_id,
                    body={"type": "user", "role": "reader", "emailAddress": admin["email"]},
                    sendNotificationEmail=False, fields="id",
                ).execute()
            except Exception:
                # The owner may already have permission or a domain policy may block
                # sharing. Dashboard access remains role-protected and the audit/job
                # layer records generation failures elsewhere.
                continue

    def _report_html(self, user: dict[str, str], writing: str, transcripts: list[str],
                     report: dict[str, Any], speaking: dict[str, Any],
                     audio: list[dict[str, str]]) -> str:
        scores = report["scores"]
        corrected = _corrected_html(writing, report["issues"])
        issue_rows = "".join(
            f"<tr><td>{html.escape(i['category'])}</td><td style='color:#a32636'>{html.escape(i['original'])}</td>"
            f"<td style='color:#207044'>{html.escape(i['correction'] or '—')}</td>"
            f"<td>{html.escape(i['explanation'])}</td></tr>" for i in report["issues"]
        ) or "<tr><td colspan='4'>No rule-based issues found.</td></tr>"
        lessons = "".join(
            f"<h3>{html.escape(x['title'])}</h3><p>{html.escape(x['rule'])}</p>"
            f"<p><b>Examples:</b> {html.escape(x['examples'])}<br><b>Common mistake:</b> {html.escape(x['mistake'])}</p>"
            f"<p><b>Your example:</b> {html.escape(x['student_example']['original'])} → "
            f"{html.escape(x['student_example']['correction'] or 'review')}</p>" for x in report["lessons"]
        ) or "<p>No specific mini-lessons were selected.</p>"
        speak_parts = []
        for index, transcript in enumerate(transcripts):
            evidence = speaking["answers"][index]
            feedback = " ".join(evidence["feedback"])
            speak_parts.append(
                f"<h3>Answer {index+1}</h3><p><a href='{html.escape(audio[index]['webViewLink'])}'>Listen to answer {index+1}</a>"
                f" — {evidence['duration_seconds']} seconds — recording evidence {evidence['automated_recording_score']}/5</p>"
                f"<p>{html.escape(feedback)}</p><p><b>Typed transcript:</b> "
                f"{html.escape(transcript) if transcript else 'Not supplied; teacher must listen to assess language content.'}</p>"
            )
        feedback_items = "".join(f"<li>{html.escape(x)}</li>" for x in report["task_feedback"])
        return f"""<!doctype html><html><head><meta charset='utf-8'><style>
        body{{font-family:Arial,sans-serif;color:#272124;line-height:1.55}}h1,h2,h3{{color:#731f35}}
        table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ddd;padding:8px;text-align:left}}
        .box{{background:#f7f2f3;padding:14px;border-left:4px solid #731f35;white-space:pre-wrap}}
        .notice{{background:#fff3d8;padding:12px}}del{{color:#a32636}}ins{{color:#207044;text-decoration:none;font-weight:bold}}
        </style></head><body><h1>Kaplan English Placement Report</h1>
        <p><b>Student:</b> {html.escape(user['name'])}<br><b>Email:</b> {html.escape(user['email'])}</p>
        <p class='notice'><b>Automated first-pass check—teacher to confirm.</b> This system does not use AI. It can miss errors or flag correct text. Relevance, coherence, natural style and pronunciation require a teacher.</p>
        <h2>Score summary</h2><table><tr><th>Grammar</th><th>Spelling & punctuation</th><th>Vocabulary</th><th>Task & length</th><th>Total</th><th>Suggested level</th></tr>
        <tr><td>{scores['grammar']}/5</td><td>{scores['spelling_punctuation']}/5</td><td>{scores['vocabulary']}/5</td><td>{scores['task_length']}/5</td><td>{report['total']}/20</td><td>{html.escape(report['level'])}</td></tr></table>
        <p><b>Formula:</b> {html.escape(report['formula'])}</p><h2>Task-completion feedback</h2><ul>{feedback_items}</ul>
        <h2>Original writing answer</h2><div class='box'>{html.escape(writing)}</div>
        <h2>Corrected view</h2><div class='box'>{corrected}</div>
        <h2>Mistakes and corrections</h2><table><tr><th>Category</th><th>Original</th><th>Correction</th><th>Why</th></tr>{issue_rows}</table>
        <h2>Personal learning guidelines</h2>{lessons}<h2>Speaking evidence</h2>{''.join(speak_parts)}
        <h2>Teacher speaking checklist</h2><table><tr><th>Area</th><th>Score /5</th><th>Notes</th></tr>
        <tr><td>Fluency</td><td></td><td></td></tr><tr><td>Pronunciation and word accuracy</td><td></td><td></td></tr>
        <tr><td>Length and development</td><td></td><td></td></tr><tr><td>Relevance</td><td></td><td></td></tr></table>
        <h2>Final placement</h2><p>Teacher level: ____________________</p><p>Teacher notes:</p><p><br><br></p></body></html>"""


def _corrected_html(text: str, issues: list[dict[str, Any]]) -> str:
    output=[]; position=0
    for issue in sorted(issues, key=lambda item:(item["start"], item["end"])):
        start,end=issue["start"],issue["end"]
        if start < position or start > len(text):
            continue
        output.append(html.escape(text[position:start]))
        if issue["original"] == "end of answer":
            output.append(f"<ins>{html.escape(issue['correction'])}</ins>")
            position=start
            continue
        output.append(f"<del>{html.escape(text[start:end])}</del>")
        if issue["correction"]:
            output.append(f" <ins>{html.escape(issue['correction'])}</ins>")
        position=end
    output.append(html.escape(text[position:]))
    return "".join(output).replace("\n","<br>")
