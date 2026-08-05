import {
  describe,
  expect,
  test,
} from '@jest/globals';

import { MockDashboardService } from '../services/mockDashboardService';

describe('MockDashboardService', () => {
  test('should successfully return an array of upcoming lectures', async () => {
    // 1. Arrange
    const service = new MockDashboardService();

    // 2. Act
    const lectures = await service.getUpcomingLectures();

    // 3. Assert
    expect(Array.isArray(lectures)).toBe(true);
  });

  test('should return an empty array when the state is set to empty', async () => {
    // 1. Arrange - we pass 'empty' to the constructor to simulate an empty state
    const service = new MockDashboardService('empty');

    // 2. Act
    const lectures = await service.getUpcomingLectures();

    // 3. Assert
    expect(lectures).toEqual([]);
  });

  test('should throw an error when the state is set to error', async () => {
    // 1. Arrange - we pass 'error' to the constructor to simulate an error state
    const service = new MockDashboardService('error');

    // 2 & 3. Act and Assert
    await expect(service.getUpcomingLectures()).rejects.toThrow('Failed to fetch dashboard data');
  });
});
