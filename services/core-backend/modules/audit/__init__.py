"""Shared audit-log writer for audit.audit_logs.

Any module recording a sensitive lecturer/administrator action (manual review
decisions, session lifecycle changes, future classroom/geofence/policy/user
writes) should call `write_audit_log` inside the same transaction as the
change it's recording, rather than writing to audit.audit_logs directly.
"""
