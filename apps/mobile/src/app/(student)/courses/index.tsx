import { useMemo } from 'react';

import { CourseScreen } from '../../../features/courses/screens/CourseScreen';
import { useAuth } from '../../../features/auth/context/AuthContext';
import { CoreApiCourseService } from '../../../features/courses/services/coreApiCourseService';
import { CoreApiClient } from '../../../services/api/coreApiClient';

export default function StudentCoursesRoute() {
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
