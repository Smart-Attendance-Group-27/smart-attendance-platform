export type CourseSummary = {
  code: string;
  title: string;
  lecturer: string;
  attendancePercentage: number;
  upcomingSessions: number;
  color: string;
};

export type UpcomingAttendance = {
  id: string;
  day: string;
  month: string;
  course: string;
  time: string;
  location: string;
};

export const courseSummaries: CourseSummary[] = [
  {
    code: 'CS3203',
    title: 'Software Engineering Project',
    lecturer: 'Dr. N. Perera',
    attendancePercentage: 86,
    upcomingSessions: 3,
    color: '#173B7A',
  },
  {
    code: 'MA3030',
    title: 'Operational Research',
    lecturer: 'Prof. S. Fernando',
    attendancePercentage: 80,
    upcomingSessions: 2,
    color: '#1D4ED8',
  },
  {
    code: 'CS3052',
    title: 'Computer Security',
    lecturer: 'Dr. R. Silva',
    attendancePercentage: 78,
    upcomingSessions: 1,
    color: '#254E9A',
  },
  {
    code: 'EC2010',
    title: 'Digital Systems',
    lecturer: 'Prof. K. Senaratne',
    attendancePercentage: 92,
    upcomingSessions: 0,
    color: '#0F4C81',
  },
  {
    code: 'CS2101',
    title: 'Data Structures',
    lecturer: 'Dr. W. Perera',
    attendancePercentage: 88,
    upcomingSessions: 2,
    color: '#1E3A8A',
  },
];

export const upcomingAttendance: UpcomingAttendance[] = [
  {
    id: 'ma3030-23-jul',
    day: '23',
    month: 'JUL',
    course: 'MA3030 — Operational Research',
    time: '13:00',
    location: 'Room B4',
  },
  {
    id: 'cs3052-24-jul',
    day: '24',
    month: 'JUL',
    course: 'CS3052 — Computer Security',
    time: '08:00',
    location: 'Lab 3',
  },
  {
    id: 'cs3203-27-jul',
    day: '27',
    month: 'JUL',
    course: 'CS3203 — Software Eng. Project',
    time: '10:00',
    location: 'Hall 02',
  },
  {
    id: 'cs2101-28-jul',
    day: '28',
    month: 'JUL',
    course: 'CS2101 — Data Structures',
    time: '09:00',
    location: 'Room C1',
  },
  {
    id: 'ec2010-29-jul',
    day: '29',
    month: 'JUL',
    course: 'EC2010 — Digital Systems',
    time: '11:00',
    location: 'Lab 7',
  },
  {
    id: 'cs3203-30-jul',
    day: '30',
    month: 'JUL',
    course: 'CS3203 — Software Eng. Project',
    time: '14:00',
    location: 'Hall 02',
  },
];
