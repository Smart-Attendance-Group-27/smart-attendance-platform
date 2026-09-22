"""Push delivery state machine.

Delivery attempts use one vocabulary throughout the producer and worker:

    queued -> in_flight -> sent -> delivered
                    |-> queued (retry with backoff)
                    |-> failed (terminal)

``attempt_number`` is incremented when a queued attempt is claimed. A claim
stores its lease timestamp in ``attempted_at``; stale ``in_flight`` claims are
eligible for reclamation after the configured timeout. ``next_attempt_at``
keeps retries out of the ready queue until their backoff expires.

Expo accepting a message produces a ticket and moves the attempt to ``sent``.
The later Expo receipt moves it to ``delivered`` or back through retry handling.
The legacy ``pending`` state is migrated to ``queued`` and is never written by
application code.

The worker provides at-least-once delivery. A process crash after Expo accepts
a message but before its ticket is persisted can cause one duplicate delivery;
the stale claim is intentionally reclaimed so a notification is never lost.
"""

DELIVERY_STATUS_QUEUED = "queued"
DELIVERY_STATUS_IN_FLIGHT = "in_flight"
DELIVERY_STATUS_SENT = "sent"
DELIVERY_STATUS_DELIVERED = "delivered"
DELIVERY_STATUS_FAILED = "failed"

TERMINAL_DELIVERY_STATUSES = frozenset(
    {DELIVERY_STATUS_DELIVERED, DELIVERY_STATUS_FAILED}
)
