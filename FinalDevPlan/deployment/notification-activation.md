# Android notification activation

**Owner:** Manushan
**Prepared:** 2026-09-25
**Status:** Code review in progress; push and reminders remain off on the VPS.

## Current state

The application already writes in-app notifications and push delivery attempts
when attendance sessions open, QR batches activate, attendance is finalized or
changed, and sessions are cancelled. The deployed schema includes the retry
column and reminder deduplication index. The live VPS has
`PUSH_WORKER_ENABLED=false` and `REMINDER_SCHEDULER_ENABLED=false`.

On 2026-09-25, Manushan authorized retirement of historical queued attempts.
Exactly **62 queued delivery attempts** were deleted in one transaction;
**72 in-app notification records** remained. New attendance events continue to
create queued attempts until the worker is enabled. Retire those older than the
activation cutoff again before starting delivery.

The mobile Firebase client configuration now targets project `uniattend-1a701`
for Android package `com.group27.uniattend`. Its project ID matches the local
Firebase service-account JSON supplied for EAS. The service-account JSON is a
private credential and stays outside this repository. Verify the FCM V1 key
uploaded to EAS belongs to the same Firebase project. The EAS mobile project
is owned by `manushanhasanka` after PR #103.

## After this PR is merged, before enabling delivery

1. Build a new internal EAS APK from the merged commit. The Firebase client
   configuration and the new mobile code require an installed APK update.
2. On a physical Android phone, sign in as a mock student, grant notifications,
   and confirm the Notifications tab says the device is registered. Confirm the
   backend has an active token for that student's user ID. Never paste or log
   the Expo token.
3. Review the read-only queue summary in
   `deployment/notification-status.sql`. Run
   `deployment/retire-queued-pushes.sql` with a UTC cutoff immediately before
   activation. Keep the in-app rows. Record the deletion count.
4. Enable `PUSH_WORKER_ENABLED=true` on the VPS and restart only Core. Check
   startup logs for schema preflight and worker startup, then create one new
   pilot attendance event. Verify a new queued attempt becomes `sent` and then
   `delivered` by checking Expo receipts and the SQL summary. An Expo delivery
   receipt confirms FCM accepted the message; confirm phone display separately.
5. Test a push while the app is open, in the background, and after a cold
   start. A session/QR/result tap should open attendance progress; a
   cancellation tap should open Notifications. Check the inbox refresh, unread
   badge, read-all action, and preference switches.
6. Enable `REMINDER_SCHEDULER_ENABLED=true` only after push passes. Create one
   scheduled session inside the lead window and verify one `UPCOMING_CLASS`
   notification per student and session across repeated scheduler cycles.
7. Watch queued age and failed deliveries using the SQL summary and worker
   logs. If incorrect or repeated notifications occur, disable the worker and
   scheduler while retaining the attempt rows for investigation.

## Scope

The pilot supports Android push and student notifications. iOS push requires
Apple credentials and backend iOS token support. `ATTENDANCE_RISK` and
`GENERAL` are reserved notification types; no attendance event currently
produces them. A risk trigger needs a separate rule defining the threshold,
when it is evaluated, and how repeats are suppressed.
