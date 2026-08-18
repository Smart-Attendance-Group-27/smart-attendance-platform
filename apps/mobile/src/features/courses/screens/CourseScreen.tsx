import React, { useEffect, useState } from 'react';
import { useRouter } from 'expo-router';
import { ActivityIndicator, Text, View } from 'react-native';

import { AppButton, ScreenContainer } from '../../../components/ui';
import { spacing } from '../../../theme';
import { mockCourses, type Course } from '../mockCoursesData';
import type { CourseService } from '../services/courseService';
import { CourseListScreen } from './CourseListScreen';
import { CourseDetailsScreen } from './CourseDetailsScreen';

type CourseScreenProps = {
  courseService?: CourseService;
};

type CourseScreenState =
  | { status: 'loading' }
  | { status: 'ready'; courses: Course[] }
  | { status: 'error'; message: string };

export function CourseScreen({ courseService }: CourseScreenProps = {}) {
  const router = useRouter();
  const [selectedCourseId, setSelectedCourseId] = useState<string | null>(null);
  const [requestNumber, setRequestNumber] = useState(0);
  const [state, setState] = useState<CourseScreenState>(
    courseService
      ? { status: 'loading' }
      : { status: 'ready', courses: mockCourses },
  );

  useEffect(() => {
    if (!courseService) {
      setState({ status: 'ready', courses: mockCourses });
      return;
    }

    let mounted = true;
    setState({ status: 'loading' });

    courseService
      .listMyCourses()
      .then((result) => {
        if (!mounted) {
          return;
        }

        if (result.status === 'loaded') {
          setState({ status: 'ready', courses: result.courses });
          return;
        }

        setState({
          status: 'error',
          message: `Courses request failed: ${result.status}`,
        });
      })
      .catch(() => {
        if (mounted) {
          setState({
            status: 'error',
            message: 'Courses request failed unexpectedly.',
          });
        }
      });

    return () => {
      mounted = false;
    };
  }, [courseService, requestNumber]);

  const handleBackFromList = () => {
    // If they click back on the root course list, send them back to the Home tab
    router.replace('/(student)/(tabs)');
  };

  const handleSelectCourse = (courseId: string) => {
    setSelectedCourseId(courseId);
  };

  const handleBackFromDetails = () => {
    setSelectedCourseId(null);
  };

  if (state.status === 'loading') {
    return (
      <ScreenContainer>
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
          <ActivityIndicator />
          <Text style={{ marginTop: spacing.sm }}>Loading courses...</Text>
        </View>
      </ScreenContainer>
    );
  }

  if (state.status === 'error') {
    return (
      <ScreenContainer>
        <View style={{ flex: 1, justifyContent: 'center' }}>
          <Text>{state.message}</Text>
          <AppButton
            onPress={() => setRequestNumber((value) => value + 1)}
            style={{ marginTop: spacing.md }}
            title="Retry"
          />
        </View>
      </ScreenContainer>
    );
  }

  if (selectedCourseId) {
    return (
      <CourseDetailsScreen
        courses={state.courses}
        courseId={selectedCourseId}
        onBack={handleBackFromDetails}
      />
    );
  }

  return (
    <CourseListScreen
      courses={state.courses}
      onSelectCourse={handleSelectCourse}
      onBackPress={handleBackFromList}
    />
  );
}

export default CourseScreen;
