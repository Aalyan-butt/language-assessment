# Acceptance and release checklist

## Automated

Run:

```powershell
python -m pytest -q
```

All tests must pass before deployment.

## Authentication and roles

- [ ] Five incorrect student passwords lock only that account for 120 seconds.
- [ ] Session expires after two hours of inactivity.
- [ ] Student receives HTTP 403 from users, results, exports and overrides.
- [ ] Disabled users cannot log in.
- [ ] Resetting a password revokes existing sessions.
- [ ] No users API response contains a password hash, salt or plaintext.

## Accounts

- [ ] Create one student and one administrator.
- [ ] Bulk import 30 valid students.
- [ ] Duplicate emails are rejected without changing existing accounts.
- [ ] Edit name and email, reset password and allow a retake.
- [ ] The final active administrator cannot be disabled.

## Student assessment

- [ ] Writing word counter works and paste events are recorded.
- [ ] Three recordings are mandatory.
- [ ] Record, stop, play and re-record work on phone and laptop.
- [ ] Each recording stops at about 90 seconds and submits as MP3.
- [ ] Double-clicking submit creates only one submission.
- [ ] A used single-attempt account cannot submit again.

## Checker

- [ ] `I buyed a gift yesterday and i go to park` identifies buyed→bought,
  i→I, go→went, park→the park and missing final punctuation.
- [ ] Polished unrelated pasted content is `Teacher review required`.
- [ ] Task feedback lists missing who/where/when/why/past evidence.
- [ ] Formula, metrics, mistakes and three lessons appear.
- [ ] Speaking evidence flags short, quiet, paused or clipped recordings.
- [ ] Reports state that pronunciation and language require a teacher.

## Google outputs

- [ ] Results and Errors rows are complete.
- [ ] Three Sheet audio links open Drive playback.
- [ ] Student attempt folder contains exactly three current MP3s and one Doc.
- [ ] Doc preserves original text and shows red/green corrected text.
- [ ] Doc includes mistake table, lessons, speaking links and teacher checklist.
- [ ] Active administrators can open private folders; students cannot.

## Browsers and accessibility

- [ ] Chrome and Edge desktop.
- [ ] Chrome Android and Safari iPhone if available.
- [ ] Keyboard focus is visible and forms have labels.
- [ ] Microphone works only on HTTPS production URL.
- [ ] Layout works at 360 px width without hidden controls.
