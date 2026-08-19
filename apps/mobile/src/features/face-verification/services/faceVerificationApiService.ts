import { File } from 'expo-file-system';

import {
  CoreApiClient,
  type AccessTokenProvider,
} from '../../../services/api/coreApiClient';
import type {
  FaceReadiness,
  FaceReadinessResult,
  FaceReadinessStatus,
} from '../types/readinessStatus';
import type { FaceVerificationResult } from '../types/faceVerification';

const defaultFaceVerificationApiBaseUrl = 'http://10.0.2.2:8001';
const defaultFaceVerificationRequestTimeoutMs = 5_000;
const readinessStatusPath = '/api/v1/face-verification/readiness/status';
const readinessVerificationPath = '/api/v1/face-verification/readiness';

const readinessStatuses = new Set<FaceReadinessStatus>([
  'not_checked',
  'passed',
  'failed',
  'expired',
  'profile_not_enrolled',
]);

type ReadinessStatusResponse = {
  readonly status?: unknown;
  readonly requiresReadinessCheck?: unknown;
  readonly checkedAt?: unknown;
};

type ReadinessVerificationResponse = {
  readonly status?: unknown;
};

export type FaceVerificationApiServiceOptions = {
  readonly getAccessToken: AccessTokenProvider;
  readonly baseUrl?: string;
  readonly timeoutMs?: number;
};

export function resolveFaceVerificationApiBaseUrl(): string {
  const configuredBaseUrl =
    process.env.EXPO_PUBLIC_FACE_VERIFICATION_API_URL?.trim();

  return stripTrailingSlash(
    configuredBaseUrl || defaultFaceVerificationApiBaseUrl,
  );
}

/**
 * Authenticated client for the separately deployed face-verification service.
 * The current access token is requested immediately before every API call.
 */
export class FaceVerificationApiService {
  private readonly apiClient: CoreApiClient;

  constructor({
    getAccessToken,
    baseUrl,
    timeoutMs = defaultFaceVerificationRequestTimeoutMs,
  }: FaceVerificationApiServiceOptions) {
    this.apiClient = new CoreApiClient({
      baseUrl: baseUrl
        ? stripTrailingSlash(baseUrl)
        : resolveFaceVerificationApiBaseUrl(),
      getAccessToken,
      timeoutMs,
    });
  }

  async getReadinessStatus(): Promise<FaceReadinessResult> {
    const result = await this.apiClient.get<unknown>(readinessStatusPath);

    if (result.status !== 'ok') {
      return { status: result.status };
    }

    const readiness = toFaceReadiness(result.data);
    return readiness
      ? { status: 'loaded', readiness }
      : { status: 'server-error' };
  }

  async verifyReadiness(captureUri: string): Promise<FaceVerificationResult> {
    const formData = new FormData();
    const captureFile = new File(captureUri);
    formData.append('image', captureFile);

    const result = await this.apiClient.postFormData<unknown>(
      readinessVerificationPath,
      formData,
    );

    if (result.status !== 'ok') {
      return { status: 'verification_failure' };
    }

    return toFaceVerificationResult(result.data);
  }
}

function toFaceVerificationResult(value: unknown): FaceVerificationResult {
  if (!value || typeof value !== 'object') {
    return { status: 'verification_failure' };
  }

  const response = value as ReadinessVerificationResponse;

  if (response.status === 'passed') {
    return { status: 'success' };
  }

  if (response.status === 'no_face') {
    return { status: 'face_not_detected' };
  }

  if (response.status === 'multiple_faces') {
    return { status: 'multiple_faces' };
  }

  return { status: 'verification_failure' };
}

function toFaceReadiness(
  value: unknown,
): FaceReadiness | null {
  if (!value || typeof value !== 'object') {
    return null;
  }

  const response = value as ReadinessStatusResponse;

  if (
    typeof response.status !== 'string' ||
    !readinessStatuses.has(response.status as FaceReadinessStatus) ||
    typeof response.requiresReadinessCheck !== 'boolean' ||
    !isNullableDateTime(response.checkedAt)
  ) {
    return null;
  }

  return {
    status: response.status as FaceReadinessStatus,
    requiresReadinessCheck: response.requiresReadinessCheck,
    checkedAt: response.checkedAt,
  };
}

function isNullableDateTime(value: unknown): value is string | null {
  return (
    value === null ||
    (typeof value === 'string' && Number.isFinite(Date.parse(value)))
  );
}

function stripTrailingSlash(url: string): string {
  return url.replace(/\/+$/, '');
}
