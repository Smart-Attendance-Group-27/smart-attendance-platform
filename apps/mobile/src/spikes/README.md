# S1 — Android ML Kit camera spike

Tested on a WOD-LX2 (Android 14) with Expo 57.0.9 / React Native 0.86.2 on 2026-09-21.

## Result

- Candidate: `react-native-vision-camera@4.7.3` with `react-native-vision-camera-face-detector@1.10.2` and `react-native-worklets-core@1.6.3`.
- Android development APK: builds and installs successfully. Worklets Core 1.6.3 is needed for the Hermes CMake target used by RN 0.86.
- Runtime: opening `/s1-camera-spike` fails during Vision Camera device enumeration with `NoClassDefFoundError: androidx.camera.camera2.internal.Camera2CameraInfoImpl` at `CameraDeviceDetails.kt:67`.
- Gradle resolves CameraX 1.6.0 from `expo-camera@57.0.3`. Vision Camera v4.7.3 requests CameraX 1.5.0-alpha03 and references that internal class. This combination is not usable without a native compatibility patch or changing the CameraX dependency graph.
- The spike route loads lazily, so normal UniAttend startup remains available.

## Device observations

No frame reached ML Kit. Face count, front-camera yaw sign, eye-open probabilities, blink reliability, tracking ID stability, processing rate, and practical thresholds are **unmeasured**. The requested straight/left/right, open/blink/held-closed, and near/far actions could not be evaluated.

## Vision Camera decision

Use the development plan's `expo-camera` stills + ML Kit still-image detection fallback. No ML Kit frame processor is selected for this Expo 57 build.

## Expo Camera fallback

- Candidate: existing `expo-camera` front camera with `@react-native-ml-kit/face-detection@2.0.1`.
- Route: `/s1-camera-spike` in an Android development build.
- Captures are processed sequentially and deleted after detection.
- The route reports face count, yaw, eye-open probabilities, face bounds and area, capture time, detection time, and total capture-to-result time.
- Android build: clean ARM64 development APK built successfully without an additional Expo config plugin or native patch.
- Fallback device: Samsung SM-A346E on 2026-09-21.

### Fallback measurements

| Test | Observation |
| --- | --- |
| Straight / eyes open | Yaw was -2.1 to +2.2 degrees in the controlled eyes-open run. Stable eye-open probabilities were 0.99 to 1.00. |
| Turn left | The front camera reported positive yaw. Observed samples were +39.6 and +53.7 degrees. |
| Turn right | The front camera reported negative yaw. Detected samples ranged from -42.9 to -20.3 degrees; one of four stills missed the face. |
| Normal blink | Repeated normal blinking produced three detected faces and one missed face. No still captured both eyes closed; detected eye minima were 0.73 and 0.99. Normal blinks are not reliable with this sampling method. |
| Eyes closed and held | Five consecutive samples reported left-eye probability 0.007 to 0.075 and right-eye probability 0.005 to 0.025. |
| Near | Five of six stills detected a face at 29.8% to 33.3% image area. The initially closest pose missed once. |
| Far | Five of five stills detected a face at 7.45% to 8.12% image area. |
| Timing | Capture usually took 0.9 to 1.1 seconds and ML Kit usually took 0.9 to 1.0 seconds. Total capture-to-result time was usually 1.8 to 2.0 seconds, with an observed maximum of 2.74 seconds. |

### S1 conclusion

1. Selected camera library: existing `expo-camera` with repeated front-camera still captures.
2. Selected detector: `@react-native-ml-kit/face-detection@2.0.1`.
3. Compatibility: the fallback builds and runs with Expo 57.0.9 / React Native 0.86.2 in a real Android development build.
4. Blink reliability: ordinary blinks are not reliable because capture and detection take about 1.8 to 2.0 seconds per result.
5. Tracking ID: not used for independent still images and therefore unavailable as continuous liveness evidence.
6. Front-camera yaw sign: the user's left is positive; the user's right is negative.
7. Initial practical thresholds from this device: `turn_left >= +25` degrees, `turn_right <= -25` degrees, both eye-open probabilities `< 0.10` for held closed, and face area `>= 7%`. Around 10% to 30% face area is a practical target range; the closest pose around 30% missed once.
8. Decision: keep the Expo Camera fallback for this project. Restrict supported challenges to `turn_left`, `turn_right`, and `eyes_closed_hold`. Do not support a normal-blink challenge with still-image sampling.

This spike contains no liveness state machine, identity submission, backend request, or evidence payload.
