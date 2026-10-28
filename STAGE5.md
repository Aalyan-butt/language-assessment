# Stage 5 — Google Sheets, Drive, audio and Docs

Stage 5 is implemented in `app/workspace.py` and the Google-backed path in
`app/main.py`. Local development continues to use temporary in-memory records;
Google artefacts are created when all `GOOGLE_*` environment variables are set.

## Submission transaction

1. Authenticate the student and verify the remaining attempt.
2. Validate all three MP3 payloads (type, signature and 6 MB limit each).
3. Run deterministic writing and transcript checks.
4. Validate browser-calculated recording evidence (duration, RMS audibility,
   silence ratio and clipping ratio).
5. Find or create the student's private Drive folder and submission subfolder.
6. Upload or replace the three named MP3 files.
7. Generate a Google Doc by converting a structured HTML report.
8. Share the submission folder with every active administrator email.
9. Append the complete Results row and one Errors row per issue.
10. Add `HYPERLINK` formula cells for all three recordings.
11. Increment the student's used-attempt count only after persistence succeeds.

The submission ID is stored as a Drive `appProperty`, making retries idempotent.
If Google storage fails, the attempt is not consumed and the student receives a
clear retry message. The failure is recorded in `Jobs`.

## Generated Google Doc

Each report contains:

- student details and score table;
- explainable formula and task-completion feedback;
- original writing exactly as typed;
- corrected view with red errors and green suggestions;
- mistake/correction/explanation table;
- three personalised fixed lessons;
- links to all three Drive recordings;
- deterministic recording evidence and its limitations;
- teacher fluency, pronunciation, length and relevance checklist;
- teacher notes and final-placement area.

## One-time activation

The actual Google files cannot be created until the owner authorises the app.
During deployment, run:

```powershell
python scripts/setup_google.py --client-secrets client_secret.json
```

The script creates the Drive root folder, moves the master Sheet into it,
creates and headers all tabs, hides `Users` and `Sessions`, loads Settings and
25 Lessons, creates the initial administrator, and prints the five secret
environment values that must be entered in Render. The OAuth JSON and refresh
token must never be committed to GitHub.
