"""Finalizes a student's attendance once every verification requirement the
session actually turned on (geofence, face, QR) has genuinely passed —
checked server-side against the same attempt tables geofence/face/qr already
write to. This is the step that was previously missing entirely: nothing
else in the codebase ever writes attendance_verification.attendance_records
on a successful pass, only the lecturer manual-review approve path does, and
only for attempts that already failed.
"""
