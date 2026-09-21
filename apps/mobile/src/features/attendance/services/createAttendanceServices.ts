import type { CoreApiClient } from '../../../services/api/coreApiClient';
import type { AttendanceService } from './attendanceService';
import { CoreApiAttendanceService } from './coreApiAttendanceService';
import { MockAttendanceService } from './mockAttendanceService';

export function createAttendanceServices(coreApiClient: CoreApiClient): AttendanceService {
  return process.env.EXPO_PUBLIC_API_MODE === 'mock'
    ? new MockAttendanceService()
    : new CoreApiAttendanceService(coreApiClient);
}
