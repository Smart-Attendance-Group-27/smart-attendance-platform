import FaceDetection, {
  type Face,
  type FaceDetectionOptions,
} from '@react-native-ml-kit/face-detection';
import { CameraView, useCameraPermissions } from 'expo-camera';
import * as FileSystem from 'expo-file-system/legacy';
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

const SAMPLE_DELAY_MS = 900;

const DETECTOR_OPTIONS: FaceDetectionOptions = {
  performanceMode: 'fast',
  landmarkMode: 'all',
  contourMode: 'none',
  classificationMode: 'all',
  minFaceSize: 0.1,
  trackingEnabled: false,
};

const ACTIONS = [
  'straight',
  'turn_left',
  'turn_right',
  'eyes_open',
  'blink',
  'eyes_closed_hold',
  'near',
  'far',
] as const;

type TestAction = (typeof ACTIONS)[number];

type Measurements = {
  action: TestAction;
  attempts: number;
  detectedSamples: number;
  missedSamples: number;
  faceCount: number;
  face: Face | null;
  imageWidth: number;
  imageHeight: number;
  captureMs: number;
  detectionMs: number;
  totalMs: number;
  minYaw: number | null;
  maxYaw: number | null;
  minLeftEye: number | null;
  maxLeftEye: number | null;
  minRightEye: number | null;
  maxRightEye: number | null;
  minFaceAreaPercent: number | null;
  maxFaceAreaPercent: number | null;
};

function createMeasurements(action: TestAction): Measurements {
  return {
    action,
    attempts: 0,
    detectedSamples: 0,
    missedSamples: 0,
    faceCount: 0,
    face: null,
    imageWidth: 0,
    imageHeight: 0,
    captureMs: 0,
    detectionMs: 0,
    totalMs: 0,
    minYaw: null,
    maxYaw: null,
    minLeftEye: null,
    maxLeftEye: null,
    minRightEye: null,
    maxRightEye: null,
    minFaceAreaPercent: null,
    maxFaceAreaPercent: null,
  };
}

function minValue(previous: number | null, current: number | undefined) {
  return typeof current === 'number'
    ? Math.min(previous ?? current, current)
    : previous;
}

function maxValue(previous: number | null, current: number | undefined) {
  return typeof current === 'number'
    ? Math.max(previous ?? current, current)
    : previous;
}

function format(value: number | null | undefined, digits = 1) {
  return typeof value === 'number' && Number.isFinite(value)
    ? value.toFixed(digits)
    : '--';
}

export default function S1CameraSpikeRoute() {
  const [permission, requestPermission] = useCameraPermissions();
  const cameraRef = useRef<CameraView>(null);
  const mountedRef = useRef(true);
  const samplingRef = useRef(false);
  const busyRef = useRef(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const handledSampleRequestRef = useRef(0);
  const measurementsRef = useRef(createMeasurements('straight'));
  const [cameraReady, setCameraReady] = useState(false);
  const [sampling, setSampling] = useState(false);
  const [sampleRequest, setSampleRequest] = useState(0);
  const [measurements, setMeasurements] = useState(() =>
    createMeasurements('straight'),
  );
  const [error, setError] = useState<string | null>(null);

  const stopSampling = useCallback(() => {
    samplingRef.current = false;
    setSampling(false);
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  useEffect(() => {
    return () => {
      mountedRef.current = false;
      samplingRef.current = false;
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  useEffect(() => {
    const shouldCaptureSingleSample = sampleRequest > handledSampleRequestRef.current;
    if ((!sampling && !shouldCaptureSingleSample) || !cameraReady) return;
    if (shouldCaptureSingleSample) handledSampleRequestRef.current = sampleRequest;

    async function captureSample() {
      if (busyRef.current || !cameraRef.current) return;

      busyRef.current = true;
      setError(null);
      const startedAt = Date.now();
      let imageUri: string | null = null;

      try {
        const capturedAt = Date.now();
        const image = await cameraRef.current.takePictureAsync({ quality: 0.45 });
        imageUri = image.uri;
        const detectedAt = Date.now();
        const faces = await FaceDetection.detect(image.uri, DETECTOR_OPTIONS);
        const finishedAt = Date.now();
        const face = faces.length === 1 ? faces[0] : null;
        const faceAreaPercent = face && image.width > 0 && image.height > 0
          ? (100 * face.frame.width * face.frame.height) / (image.width * image.height)
          : null;
        const previous = measurementsRef.current;
        const next: Measurements = {
          ...previous,
          attempts: previous.attempts + 1,
          detectedSamples: previous.detectedSamples + (face ? 1 : 0),
          missedSamples: previous.missedSamples + (face ? 0 : 1),
          faceCount: faces.length,
          face,
          imageWidth: image.width,
          imageHeight: image.height,
          captureMs: detectedAt - capturedAt,
          detectionMs: finishedAt - detectedAt,
          totalMs: finishedAt - startedAt,
          minYaw: minValue(previous.minYaw, face?.rotationY),
          maxYaw: maxValue(previous.maxYaw, face?.rotationY),
          minLeftEye: minValue(previous.minLeftEye, face?.leftEyeOpenProbability),
          maxLeftEye: maxValue(previous.maxLeftEye, face?.leftEyeOpenProbability),
          minRightEye: minValue(previous.minRightEye, face?.rightEyeOpenProbability),
          maxRightEye: maxValue(previous.maxRightEye, face?.rightEyeOpenProbability),
          minFaceAreaPercent: minValue(previous.minFaceAreaPercent, faceAreaPercent ?? undefined),
          maxFaceAreaPercent: maxValue(previous.maxFaceAreaPercent, faceAreaPercent ?? undefined),
        };

        measurementsRef.current = next;
        if (mountedRef.current) setMeasurements(next);
        console.log('[S1 Expo Camera fallback]', {
          action: next.action,
          attempt: next.attempts,
          faces: faces.length,
          yaw: face?.rotationY,
          leftEye: face?.leftEyeOpenProbability,
          rightEye: face?.rightEyeOpenProbability,
          frame: face?.frame,
          faceAreaPercent,
          captureMs: next.captureMs,
          detectionMs: next.detectionMs,
          totalMs: next.totalMs,
        });
      } catch (caughtError) {
        const message = caughtError instanceof Error
          ? caughtError.message
          : 'Capture or face detection failed.';
        if (mountedRef.current) setError(message);
        console.error('[S1 Expo Camera fallback]', caughtError);
        stopSampling();
      } finally {
        if (imageUri) {
          await FileSystem.deleteAsync(imageUri, { idempotent: true }).catch(() => undefined);
        }
        busyRef.current = false;
        if (samplingRef.current && mountedRef.current) {
          timerRef.current = setTimeout(() => void captureSample(), SAMPLE_DELAY_MS);
        }
      }
    }

    void captureSample();
  }, [cameraReady, sampleRequest, sampling, stopSampling]);

  const startSampling = () => {
    if (!cameraReady) return;
    samplingRef.current = true;
    setSampling(true);
  };

  const selectAction = (action: TestAction) => {
    stopSampling();
    const next = createMeasurements(action);
    measurementsRef.current = next;
    setMeasurements(next);
    setError(null);
  };

  if (Platform.OS !== 'android' || !__DEV__) {
    return <View style={styles.container}><Text style={styles.text}>Android development build only.</Text></View>;
  }

  if (!permission) {
    return <View style={styles.container}><Text style={styles.text}>Loading camera permission...</Text></View>;
  }

  if (!permission.granted) {
    return (
      <View style={styles.centered}>
        <Text style={styles.text}>Camera permission is required for the S1 spike.</Text>
        <Pressable onPress={() => void requestPermission()} style={styles.button}>
          <Text style={styles.buttonText}>Grant camera permission</Text>
        </Pressable>
      </View>
    );
  }

  const face = measurements.face;
  const frame = face?.frame;
  const currentArea = face && measurements.imageWidth > 0 && measurements.imageHeight > 0
    ? (100 * face.frame.width * face.frame.height) /
      (measurements.imageWidth * measurements.imageHeight)
    : null;

  return (
    <SafeAreaView style={styles.container}>
      <Text style={styles.title}>S1 Expo Camera fallback</Text>
      <Text style={styles.subtitle}>Still-image ML Kit measurements only</Text>

      <View style={styles.preview}>
        <CameraView
          facing="front"
          mode="picture"
          onCameraReady={() => setCameraReady(true)}
          onMountError={(event) => setError(event.message)}
          ref={cameraRef}
          style={StyleSheet.absoluteFill}
        />
      </View>

      <ScrollView contentContainerStyle={styles.measurements}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false}>
          <View style={styles.actionRow}>
            {ACTIONS.map((action) => (
              <Pressable
                key={action}
                onPress={() => selectAction(action)}
                style={[styles.actionButton, measurements.action === action && styles.selectedAction]}
              >
                <Text style={styles.buttonText}>{action}</Text>
              </Pressable>
            ))}
          </View>
        </ScrollView>

        <Text style={styles.section}>Action: {measurements.action}</Text>
        <Text style={styles.text}>Attempts: {measurements.attempts} | Detected: {measurements.detectedSamples} | Missed: {measurements.missedSamples}</Text>
        <Text style={styles.text}>Faces: {measurements.faceCount}</Text>
        <Text style={styles.text}>Yaw Y: {format(face?.rotationY)} deg | Range: {format(measurements.minYaw)} to {format(measurements.maxYaw)}</Text>
        <Text style={styles.text}>Left eye: {format(face?.leftEyeOpenProbability, 2)} | Range: {format(measurements.minLeftEye, 2)} to {format(measurements.maxLeftEye, 2)}</Text>
        <Text style={styles.text}>Right eye: {format(face?.rightEyeOpenProbability, 2)} | Range: {format(measurements.minRightEye, 2)} to {format(measurements.maxRightEye, 2)}</Text>
        <Text style={styles.text}>Box left/top/w/h: {frame ? `${frame.left} / ${frame.top} / ${frame.width} / ${frame.height}` : '--'}</Text>
        <Text style={styles.text}>Face area: {format(currentArea)}% | Range: {format(measurements.minFaceAreaPercent)}% to {format(measurements.maxFaceAreaPercent)}%</Text>
        <Text style={styles.text}>Image: {measurements.imageWidth} x {measurements.imageHeight}</Text>
        <Text style={styles.text}>Capture: {measurements.captureMs} ms | ML Kit: {measurements.detectionMs} ms | Total: {measurements.totalMs} ms</Text>

        {error ? <Text style={styles.error}>Error: {error}</Text> : null}

        <View style={styles.controlRow}>
          <Pressable
            disabled={!cameraReady}
            onPress={sampling ? stopSampling : startSampling}
            style={[styles.button, !cameraReady && styles.disabledButton]}
          >
            <Text style={styles.buttonText}>{sampling ? 'Stop sampling' : 'Start sampling'}</Text>
          </Pressable>
          <Pressable
            disabled={!cameraReady || sampling}
            onPress={() => setSampleRequest((request) => request + 1)}
            style={[styles.button, (!cameraReady || sampling) && styles.disabledButton]}
          >
            <Text style={styles.buttonText}>One sample</Text>
          </Pressable>
        </View>

        <Text style={styles.hint}>Select an action to reset its measurements, then start sampling. Hold each pose long enough for several still captures.</Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#101820', paddingHorizontal: 16 },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 16, backgroundColor: '#101820', padding: 24 },
  title: { color: 'white', fontSize: 22, fontWeight: '700', marginTop: 8 },
  subtitle: { color: '#BCC9D1', marginBottom: 12 },
  preview: { height: '34%', overflow: 'hidden', borderRadius: 12, backgroundColor: '#233342' },
  measurements: { paddingVertical: 14, gap: 7, paddingBottom: 28 },
  actionRow: { flexDirection: 'row', gap: 7, paddingBottom: 4 },
  actionButton: { backgroundColor: '#42576A', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 8 },
  selectedAction: { backgroundColor: '#208AEF' },
  section: { color: 'white', fontSize: 16, fontWeight: '700', marginTop: 2 },
  text: { color: 'white', fontSize: 14 },
  controlRow: { flexDirection: 'row', gap: 10, marginTop: 5 },
  button: { backgroundColor: '#208AEF', borderRadius: 8, paddingHorizontal: 12, paddingVertical: 11 },
  disabledButton: { opacity: 0.45 },
  buttonText: { color: 'white', fontWeight: '700' },
  error: { color: '#FF9C9C', marginTop: 4 },
  hint: { color: '#BCC9D1', fontSize: 12, marginTop: 4 },
});
