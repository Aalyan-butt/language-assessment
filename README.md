# Kaplan English Placement Assessment

A no-AI, deterministic English placement system for writing and speaking
evidence. The frontend is plain HTML/CSS/JavaScript. The backend is FastAPI.
Google Sheets is the persistent record store; private Drive folders contain MP3
recordings and generated Google Docs.

## Current features

- student and administrator roles with Argon2 password hashes;
- two-hour inactivity sessions and five-failure account locking;
- responsive writing and three-question speaking assessment;
- browser MP3 encoding, paste detection and attempt enforcement;
- deterministic British-English rules, scores and 25 fixed lessons;
- off-topic/task-evidence warning without AI relevance claims;
- recording evidence for duration, audibility, pauses and clipping;
- private Google Sheet, Drive folders, MP3s and Docs;
- administrator search, filters, CSV, printing and teacher overrides;
- account creation, bulk import, editing, reset and enable/disable controls.

## Important assessment limits

Automated checking is a first pass. It can miss mistakes or flag correct text.
It does not judge coherence, natural style or semantic relevance reliably.
Audio signal measurements do not understand speech. A teacher must listen and
score fluency, pronunciation, word accuracy and relevance.

## Documentation

- [Deployment and Google setup](DEPLOYMENT.md)
- [Administrator guide](ADMIN_GUIDE.md)
- [Acceptance test checklist](TEST_CHECKLIST.md)
- [Security review](SECURITY_REVIEW.md)
- [Stage 5 technical notes](STAGE5.md)

## Local development

Install dependencies and run the temporary local version:

```powershell
python -m pip install -r requirements.txt
python scripts/run_local.py
```

Open `http://127.0.0.1:8000/`. Local development data is discarded when the
process stops. For persistent Google storage, complete `DEPLOYMENT.md`.
