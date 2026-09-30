"""Session-wide verification overrides (currently: waiving geofence).

A waiver changes what the session requires, not what the students proved.
Failed geofence readings stay failed; ``EffectiveVerificationPolicy`` is what
tells check-in that the step no longer has to pass.
"""
