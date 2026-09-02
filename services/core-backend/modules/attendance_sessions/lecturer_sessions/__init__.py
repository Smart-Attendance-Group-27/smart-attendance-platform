"""Lecturer-scoped attendance session lifecycle: create, list, view, activate,
close, and the live per-student verification monitor for one session.

Creation is deliberately not a freeform "make any session" endpoint — a new
session must be instantiated from one of the lecturer's own, already-approved
academic.timetable_entries rows (POST reads course_offering_id and the
classroom's geofence straight from that entry). This keeps the original
ownership model intact: a lecturer can only start sessions for slots they are
already assigned to teach, not arbitrary courses or classrooms.
"""
