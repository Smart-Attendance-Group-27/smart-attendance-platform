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

  async verifyFace(
    request: FaceVerificationRequest,
  ): Promise<FaceVerificationResult> {
    const formData = new FormData();
    formData.append('image', new File(request.capture.uri));

    const result = await this.coreApiClient.postFormData<unknown>(
      `/api/v1/attendance-sessions/${encodeURIComponent(
        request.sessionId,
      )}/face-verifications`,
      formData,
    );

    if (result.status !== 'ok') {
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
