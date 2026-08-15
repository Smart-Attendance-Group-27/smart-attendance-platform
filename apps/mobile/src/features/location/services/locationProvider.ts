import type { FreshLocationResult } from '../types/locationReading';

export interface LocationProvider {
  captureFreshLocation(): Promise<FreshLocationResult>;
}
