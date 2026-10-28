# Beginner deployment guide

This deployment has two public parts:

- **GitHub Pages** serves `index.html`, `config.js` and `kaplan.png` over HTTPS.
- **Render** runs the Python/FastAPI backend and securely talks to Google.

Google credentials belong only in Render environment variables. Never put them
in `index.html`, `config.js`, GitHub, screenshots or messages.

## 1. Complete Google authorisation

In Google Cloud, enable **Google Sheets API** and **Google Drive API**. Create a
Desktop OAuth client and download its JSON into this folder. Run:

```powershell
python scripts/setup_google.py --client-secrets "your-desktop-client.json"
```

Sign in using the Google account that will own the school data. Enter the first
administrator password when prompted. The script creates:

- `Kaplan English Placement Test` Drive folder;
- master Google Sheet inside that folder;
- Users, Sessions, Results, Errors, Settings, Lessons, Audit and Jobs tabs;
- 25 fixed lessons and default settings;
- the first administrator.

Copy the five values printed at the end into a private password manager. Do not
close the terminal until they are saved.

If the OAuth consent screen is in **Testing**, add the owner email as a test
user. Google testing authorisations can expire, so production use should move
the consent screen to Production when Google permits it.

## 2. Create a local `.env` for live verification

Copy `.env.example` to `.env` and fill in:

```env
FRONTEND_ORIGIN=http://127.0.0.1:8000
APP_SECRET=generate-a-long-random-value
GOOGLE_CLIENT_ID=value-from-setup
GOOGLE_CLIENT_SECRET=value-from-setup
GOOGLE_REFRESH_TOKEN=value-from-setup
GOOGLE_SPREADSHEET_ID=value-from-setup
GOOGLE_DRIVE_FOLDER_ID=value-from-setup
```

Generate `APP_SECRET` with:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Run the Google-backed application:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Submit one test student and confirm the Sheet row, three Drive MP3s and Google
Doc before public deployment.

## 3. Upload safely to GitHub

Create a repository named `kaplan-placement` under the GitHub account
`Aalyan-butt`. Ensure `.gitignore` excludes `.env`, OAuth JSON and token files.

Before every push, check that these are absent:

```powershell
git status --short
git ls-files | Select-String -Pattern "client_secret|\.env$|token.*json"
```

Then commit and push the project to the `main` branch. Never force-add ignored
credential files.

## 4. Deploy the Python backend on Render

1. Sign in to Render and connect the GitHub account.
2. Select **New → Blueprint** and choose the repository. `render.yaml` supplies
   the Python build, start command, health path and free plan.
3. In the Render service, open **Environment**.
4. Add the five `GOOGLE_*` values printed by setup.
5. Set `APP_SECRET` to a fresh random value.
6. Initially set `FRONTEND_ORIGIN` to `https://aalyan-butt.github.io`.
7. Deploy and wait for the health check to succeed.
8. Open `https://YOUR-SERVICE.onrender.com/health`; it should return `status: ok`.

Do not upload `.env` to Render as a public file. Use its Environment page.

## 5. Connect GitHub Pages to Render

Edit `config.js` and replace the placeholder with the exact HTTPS Render URL:

```javascript
window.KAPLAN_API_URL = window.location.hostname.endsWith("github.io")
  ? "https://YOUR-SERVICE.onrender.com"
  : "";
```

Commit and push this safe public URL.

In GitHub:

1. Open repository **Settings → Pages**.
2. Under **Build and deployment**, choose **Deploy from a branch**.
3. Select branch `main` and folder `/ (root)`.
4. Save and wait for the Pages deployment.
5. Open the resulting HTTPS URL and test login and microphone access.

## 6. Final production test

Use a newly created student account and complete all three recordings. Confirm:

- only one Results row was created;
- Errors contains one row per detected issue;
- the student folder has three playable MP3 files;
- the Google Doc opens and contains coloured corrections and lessons;
- an administrator can open the report and save a final placement;
- a student receives 403 for administrator endpoints;
- CSV export and printing work.

## Free-service limitations

Render's free service sleeps after inactivity and may take roughly a minute to
wake. Its local disk is temporary, which is why all permanent information goes
to Google. Google and Render quotas can change. Keep recordings under 90 seconds
and schedule large groups in waves when possible.
