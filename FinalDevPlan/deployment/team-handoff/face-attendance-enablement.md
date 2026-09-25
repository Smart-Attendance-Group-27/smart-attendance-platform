# Face attendance enablement

**Owner:** Manushan  
**Prepared:** 2026-09-25  
**Status:** Deployed; physical-device attendance acceptance pending

## Scope

The next release removes the global pilot block on face-required attendance
sessions. The switch applies to every course and timetable entry; it is not
specific to `PILOT101`.

Production keeps an emergency switch in the protected environment:

```text
PILOT_DISABLE_FACE_ATTENDANCE=false
```

Set it to `true` and recreate Core to stop new face-required sessions and
attendance face requests without stopping the separate Face service.

## Verified prerequisites

A read-only audit of the live deployment on 2026-09-25 found:

- the Face container healthy with the `buffalo_l` model cache;
- Core connected to Face over the private `uniattend-services` network;
- one active verification configuration with similarity threshold `0.50000`;
- three generated profiles with encrypted 512-dimensional embeddings;
- all three embeddings decryptable to finite 512-dimensional values with the
  currently deployed encryption key;
- the `PILOT101` student profile generated and readiness-passed with model
  `buffalo_l`, version `1`.

No embedding values, encryption keys, images, or tokens were printed or added
to Git during this audit.

## Attendance flow after release

1. A lecturer can create and activate a session with face verification.
2. The student starts attendance and passes the session geofence when it is
   required.
3. The Android app performs two distinct on-device ML Kit challenges and
   captures the final face image.
4. The app submits the image and fresh liveness evidence to Core using the
   student's access token.
5. Core validates the student token and forwards the request over the private
   Docker network to Face Verification.
6. Face Verification validates the liveness evidence, active session,
   enrollment, check-in window, geofence state, attempt limit, reference
   profile, model metadata, and active threshold.
7. Face Verification decrypts the reference embedding in memory, generates a
   capture embedding with `buffalo_l`, compares them, and records the result.
8. On a match, Core completes the initial check-in. Session closure later
   calculates the final attendance outcome using the recorded requirements.

Raw captures and decrypted embeddings are not persisted by this flow.

## Students without embeddings

Session creation does not require every enrolled student to have a face
profile. A student without a generated encrypted profile cannot pass a
face-required session. The service returns a controlled unavailable result and
does not create a false match or check the student in. Enroll the student's
approved reference image and complete readiness before using such a session.

## Pilot limitation

The current liveness flow is an on-device challenge check whose evidence is
validated by the server for shape, supported challenges, success, and age.
The evidence is not a server-issued, cryptographically bound challenge. This
is adequate for the planned supervised university pilot, but it is not yet
evidence of production-grade presentation-attack resistance.

## Release acceptance

After deploying the exact merged SHA:

1. **Passed:** Core reports `PILOT_DISABLE_FACE_ATTENDANCE=false` without printing
   other environment values.
2. **Passed:** Core, Face, Web, Keycloak, Redis, and both databases are healthy.
3. **Pending:** Create and activate a short `PILOT101` face-required session.
4. On the physical Android APK, pass geofence and both liveness challenges.
5. Verify the enrolled pilot student matches and receives initial check-in.
6. Confirm the face attempt records liveness passed, biometric match, config,
   and attempt number without storing the image.
7. Close the session and confirm final Present.
8. Test one safe failure, such as a student without a profile or an invalid
   liveness payload, and confirm no check-in is created.

The deployed release is
`5cb1ca71369184cd85776750b14084f779887a50`. Public HTTPS checks passed,
private Core and Face routes remained unavailable through Caddy, and the Face
container loaded `buffalo_l` successfully. Steps 3-8 require a supervised
physical-device session and must not be marked complete from configuration or
readiness evidence alone.
