import type { LocationValidationResult } from '../types/locationValidation';
import type { LocationService } from './locationService';

export type MockLocationServiceOptions = {
  readonly result: LocationValidationResult;
};

export class MockLocationService implements LocationService {
  private readonly result: LocationValidationResult;

  constructor({ result }: MockLocationServiceOptions) {
    this.result = result;
  }

  async validateLocation(
    _sessionId: string,
  ): Promise<LocationValidationResult> {
    return this.result;
  }
}
