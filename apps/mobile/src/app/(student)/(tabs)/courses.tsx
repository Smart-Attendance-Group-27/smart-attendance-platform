import { useMemo } from 'react';

import { CoreApiClient } from '../../../services/api/coreApiClient';
import { useAuth } from '../../../features/auth/context/AuthContext';
import { CourseScreen } from '../../../features/courses/screens/CourseScreen';
import { CoreApiCourseService } from '../../../features/courses/services/coreApiCourseService';

export default function StudentCoursesTabRoute() {
  const { session } = useAuth();
  const accessToken =
    session.status === 'authenticated' ? session.accessToken : undefined;
  const courseService = useMemo(
    () =>
      new CoreApiCourseService(
        new CoreApiClient({ getAccessToken: () => accessToken }),
      ),
    [accessToken],
  );

  if (session.status !== 'authenticated') {
    return null;
  }

  return <CourseScreen courseService={courseService} />;
}
