"""Compatibility shim for the deprecated ``complete-check-in`` endpoint.

The logic that used to live here now lives in
``modules.attendance_verification.check_in``. What remains is a route that
translates the initial check-in into the response shape the already-shipped
mobile build parses, so upgrading the backend does not require upgrading every
phone on the same day.

This package is deleted by INT-5, once the clients have moved to
``POST /attendance-sessions/{session_id}/check-in``. Nothing new should import
from it.
"""
