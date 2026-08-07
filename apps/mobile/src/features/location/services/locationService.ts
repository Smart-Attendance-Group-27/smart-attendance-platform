import type { LocationValidationResult } from '../types/locationValidation';

export interface LocationService {
  validateLocation(
    sessionId: string,
  ): Promise<LocationValidationResult>;
}
