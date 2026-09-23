import { File } from 'expo-file-system';

import type { CoreApiClient } from '../../../services/api/coreApiClient';
import type {
  FaceVerificationRequest,
  FaceVerificationResult,
} from '../types/faceVerification';
import type { FaceVerificationService } from './faceVerificationService';


type AttendanceFaceVerificationResponse = {
  readonly status?: unknown;
  readonly attemptNumber?: unknown;
  readonly canRetry?: unknown;
};

type AttendanceFaceProgressResponse = {
  readonly status?: unknown;
};

export type AttendanceFaceProgress =
  | 'passed'
  | 'required'
  | 'unavailable';

const supportedStatuses = new Set([
  'success',
  'face_not_detected',
  'multiple_faces',
  'verification_failure',
]);

export class CoreApiAttendanceFaceVerificationService
  implements FaceVerificationService
{
  constructor(private readonly coreApiClient: CoreApiClient) {}

  async getProgress(sessionId: string): Promise<AttendanceFaceProgress> {
    const result = await this.coreApiClient.get<unknown>(
      `/api/v1/attendance-sessions/${encodeURIComponent(
        sessionId,
      )}/face-verifications`,
    );

    if (result.status !== 'ok' || !result.data || typeof result.data !== 'object') {
      return 'unavailable';
    }

    const response = result.data as AttendanceFaceProgressResponse;
    return response.status === 'passed' || response.status === 'required'
      ? response.status
      : 'unavailable';
  }

  async verifyFace(
    request: FaceVerificationRequest,
  ): Promise<FaceVerificationResult> {
    const formData = new FormData();
    formData.append('image', new File(request.capture.uri));
    if (request.livenessEvidence) {
      formData.append(
        'liveness',
        JSON.stringify(request.livenessEvidence),
      );
    }

    const result = await this.coreApiClient.postFormData<unknown>(
      `/api/v1/attendance-sessions/${encodeURIComponent(
        request.sessionId,
      )}/face-verifications`,
      formData,
    );

    if (result.status !== 'ok') {
      if (
        result.status === 'invalid-request' &&
        result.errorCode === 'FACE_VERIFICATION_INVALID_REQUEST'
      ) {
        return { status: 'liveness_failure', canRetry: true };
      }

      if (
        result.status === 'server-error' &&
        result.errorCode === 'FACE_VERIFICATION_SERVICE_ERROR'
      ) {
        return { status: 'service_unavailable', canRetry: true };
      }

      return {
        status: 'verification_failure',
        canRetry: result.status !== 'conflict',
      };
    }

    return toFaceVerificationResult(result.data);
  }
}

function toFaceVerificationResult(value: unknown): FaceVerificationResult {
  if (!value || typeof value !== 'object') {
    return { status: 'verification_failure', canRetry: true };
  }

  const response = value as AttendanceFaceVerificationResponse;
  if (
    typeof response.status !== 'string' ||
    !supportedStatuses.has(response.status) ||
    typeof response.attemptNumber !== 'number' ||
    !Number.isInteger(response.attemptNumber) ||
    response.attemptNumber < 1 ||
    typeof response.canRetry !== 'boolean'
  ) {
    return { status: 'verification_failure', canRetry: true };
  }

  if (response.status === 'success') {
    return { status: 'success' };
  }
  if (response.status === 'face_not_detected') {
    return {
      status: 'face_not_detected',
      canRetry: response.canRetry,
    };
  }
  if (response.status === 'multiple_faces') {
    return {
      status: 'multiple_faces',
      canRetry: response.canRetry,
    };
  }
  return {
    status: 'verification_failure',
    canRetry: response.canRetry,
  };
}
