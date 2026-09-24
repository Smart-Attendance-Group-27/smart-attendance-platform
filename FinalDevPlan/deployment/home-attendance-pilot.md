# Physical attendance pilot without face verification

**Owner:** Manushan  
**Prepared:** 2026-09-24  
**Status:** Course and classroom ready; Manushan creates and runs the sessions

## Prepared test data

The live Supabase database has a dedicated active pilot site and classroom
`PILOT-01` at the privately supplied test location. Its geofence radius is
100 m; a session also snapshots the backend's 10 m accuracy buffer and 50 m
maximum location error. The precise coordinates are kept in the protected
administrator setup record rather than repeated in this repository.

| Item | Live value |
| --- | --- |
| Course | `PILOT101` — Attendance Pilot |
| Offering | 2026 semester 1, batch 2023, lecture |
| Lecturer | `lecutere01@lectuere.uniattend.test` |
| Enrolled student | `230737r@student.uniattend.test` |
| Timetable | Thursday 08:00–20:00, `PILOT-01`, valid through 2026-12-20 |
| Starting sessions | None; the lecturer creates the first one |

Both mock lecturer accounts now have empty attendance-session lists. A
verified encrypted Supabase archive was made immediately before removing the
20 historical sessions of MOCK401, MOCK402, and MOCK403. Their dependent
attendance, verification, geofence, and QR rows were removed in the same
transaction. The original mock courses and enrollment data remain available;
the pilot course is separate. Historical audit logs were retained. The
recovery archive and the exact removed IDs are in the administrator's
protected `C:\Users\LOQ\.uniattend-backups` directory.

## Run the first check-in yourself

1. Be at the supplied test location. Turn on the phone's Location service and
   allow precise location for UniAttend. A view of the sky or a window may
   be needed for a reading with at most 50 m reported error. The app rejects
   simulated locations.
2. On the computer, open
   <https://app.152-53-33-198.sslip.io/login> and sign in as
   `lecutere01@lectuere.uniattend.test`. Its password is in the protected
   `pilot-logins.txt` file on the administrator's workstation.
3. Open **Lecturer → Attendance sessions → Create session**. Select the
   `PILOT101` timetable slot at `PILOT-01`. Enter a title and a start and
   end time around the actual test. Leave **Require face verification** off.
   For the first run, leave **Enable QR checks** off as well. Geofence is
   required automatically.
4. Open the new session and **Activate** it. Check that the check-in window
   is open before using the phone.
5. On the physical phone, sign in as
   `230737r@student.uniattend.test`, open the active `PILOT101` session, and
   start attendance. Allow precise location. A successful reading should
   display **Inside classroom area** and then **Initial check-in complete**
   on attendance progress.
6. On the lecturer's live session monitor, confirm **Checked in 1 / 1**.
   Close the session. Confirm **Final present 1 / 1** on the lecturer view and
   **Final: Present** in the student's attendance progress. Record any actual
   error message if a step fails.

## Optional second run with QR

Create another `PILOT101` session and turn on **Enable QR checks** while
keeping face verification off. After the student completes geofence check-in,
use **Manage QR batches** on the lecturer's session page to start a required
QR batch. On the phone's attendance progress, choose **Scan QR** and scan the
lecturer's displayed code. Confirm the required batch passed, then close the
session and check the final attendance. This tests the full non-face path
with both location and QR.

## Limits and cleanup

The pilot course is real shared test data. Use only these mock accounts; no
student photos or embeddings are needed. Face attendance remains disabled
while liveness work continues. Cancel a mistaken session through the lecturer
page with a reason; close a completed session to finalize attendance. The
pilot classroom and course can be retired after testing. Changing a
classroom's coordinates later does not change the geofence snapshot of an
already created session.

The administrator academic-options endpoint had a separate schema mismatch:
it filtered lecturer and student profiles by `status`, while both tables use
`profile_status`. The companion code change fixes that endpoint so future
course management through the admin UI can load the lecturer and student
choices. It does not affect the already prepared pilot data.
