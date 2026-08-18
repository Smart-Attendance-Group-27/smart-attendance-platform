import React, { useState } from 'react';
import { useRouter } from 'expo-router';

import { CourseListScreen } from './CourseListScreen';
import { CourseDetailsScreen } from './CourseDetailsScreen';

export function CourseScreen() {
  const router = useRouter();
  const [selectedCourseId, setSelectedCourseId] = useState<string | null>(null);

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

  if (selectedCourseId) {
    return (
      <CourseDetailsScreen
        courseId={selectedCourseId}
        onBack={handleBackFromDetails}
      />
    );
  }

  return (
    <CourseListScreen
      onSelectCourse={handleSelectCourse}
      onBackPress={handleBackFromList}
    />
  );
}

export default CourseScreen;
