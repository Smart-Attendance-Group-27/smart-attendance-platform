import type { CoreApiClient } from '../../../services/api/coreApiClient';
import { CoreApiQrProgressService } from './coreApiQrProgressService';
import { CoreApiQrVerificationService } from './coreApiQrVerificationService';
import { MockQrProgressService } from './mockQrProgressService';
import { MockQrVerificationService } from './mockQrVerificationService';

export function createQrProgressService(client: CoreApiClient) {
  return process.env.EXPO_PUBLIC_API_MODE === 'mock'
    ? new MockQrProgressService() : new CoreApiQrProgressService(client);
}

export function createQrVerificationService(client: CoreApiClient) {
  return process.env.EXPO_PUBLIC_API_MODE === 'mock'
    ? new MockQrVerificationService() : new CoreApiQrVerificationService(client);
}
