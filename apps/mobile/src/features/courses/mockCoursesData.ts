export interface Session {
  id: string;
  title: string;
  timeText: string; // e.g., "Today · 10:00–12:00 · Lecture Hall 02 · Lecture"
  type: 'Lecture' | 'Lab' | 'Workshop';
  status: 'active' | 'upcoming' | 'waiting_qr' | 'marked' | 'missed' | 'closed';
  recordedTime?: string; // e.g. "Recorded at 08:06"
  weekHeader?: string; // e.g., "This week", "13–19 July", "6–12 July"
}

export interface AttendanceRecord {
  id: string;
  day: string; // "16"
  month: string; // "JUL"
  title: string; // "Lecture 05"
  recordedText: string; // "Recorded at 08:06" or "No record found"
  status: 'Present' | 'Absent';
}

export interface Course {
  id: string;
  code: string;
  title: string;
  lecturer: string;
  semester: string;
  attendedSessions: number;
  totalSessions: number;
  attendancePercentage: number;
  sessions: Session[];
  attendanceRecords: AttendanceRecord[];
}

export const mockCourses: Course[] = [
  {
    id: 'cs3203',
    code: 'CS3203',
    title: 'Software Engineering Project',
    lecturer: 'Dr. N. Perera',
    semester: 'Sem 1',
    attendedSessions: 9,
    totalSessions: 11,
    attendancePercentage: 82,
    sessions: [
      {
        id: 's1',
        title: 'Architecture Review Lecture',
        timeText: 'Today · 10:00–12:00 · Lecture Hall 02 · Lecture',
        type: 'Lecture',
        status: 'active',
        weekHeader: 'This week',
      },
      {
        id: 's2',
        title: 'Sprint Planning Lab',
        timeText: 'Fri · 14:00–16:00 · Lab 3 · Lab',
        type: 'Lab',
        status: 'upcoming',
        weekHeader: 'This week',
      },
      {
        id: 's3',
        title: 'Requirements Workshop',
        timeText: '16 Jul · 08:00–10:00 · Room B4 · Lecture',
        type: 'Lecture',
        status: 'marked',
        recordedTime: 'Recorded at 08:06',
        weekHeader: '13–19 July',
      },
      {
        id: 's4',
        title: 'Team Standup Review',
        timeText: '14 Jul · 09:00–10:00 · Lab 3 · Lab',
        type: 'Lab',
        status: 'missed',
        weekHeader: '13–19 July',
      },
      {
        id: 's5',
        title: 'Project Kickoff',
        timeText: '9 Jul · 10:00–12:00 · Lecture Hall 02 · Lecture',
        type: 'Lecture',
        status: 'closed',
        weekHeader: '6–12 July',
      },
    ],
    attendanceRecords: [
      {
        id: 'r1',
        day: '16',
        month: 'JUL',
        title: 'Lecture 05',
        recordedText: 'Recorded at 08:06',
        status: 'Present',
      },
      {
        id: 'r2',
        day: '14',
        month: 'JUL',
        title: 'Lab Session 04',
        recordedText: 'No record found',
        status: 'Absent',
      },
      {
        id: 'r3',
        day: '09',
        month: 'JUL',
        title: 'Lecture 04',
        recordedText: 'Recorded at 09:58',
        status: 'Present',
      },
      {
        id: 'r4',
        day: '02',
        month: 'JUL',
        title: 'Lecture 03',
        recordedText: 'Recorded at 10:03',
        status: 'Present',
      },
    ],
  },
  {
    id: 'ma3030',
    code: 'MA3030',
    title: 'Operational Research',
    lecturer: 'Prof. S. Fernando',
    semester: 'Sem 1',
    attendedSessions: 8,
    totalSessions: 10,
    attendancePercentage: 80,
    sessions: [
      {
        id: 'ma-s1',
        title: 'Linear Programming Formulation',
        timeText: 'Today · 13:00–15:00 · Room B4 · Lecture',
        type: 'Lecture',
        status: 'active',
        weekHeader: 'This week',
      },
      {
        id: 'ma-s2',
        title: 'Simplex Method Lab',
        timeText: 'Fri · 08:00–10:00 · Lab 2 · Lab',
        type: 'Lab',
        status: 'upcoming',
        weekHeader: 'This week',
      },
      {
        id: 'ma-s3',
        title: 'Duality and Sensitivity Analysis',
        timeText: '15 Jul · 13:00–15:00 · Room B4 · Lecture',
        type: 'Lecture',
        status: 'marked',
        recordedTime: 'Recorded at 13:05',
        weekHeader: '13–19 July',
      },
    ],
    attendanceRecords: [
      {
        id: 'ma-r1',
        day: '15',
        month: 'JUL',
        title: 'Lecture 05',
        recordedText: 'Recorded at 13:05',
        status: 'Present',
      },
      {
        id: 'ma-r2',
        day: '08',
        month: 'JUL',
        title: 'Lecture 04',
        recordedText: 'Recorded at 13:01',
        status: 'Present',
      },
    ],
  },
  {
    id: 'cs3052',
    code: 'CS3052',
    title: 'Computer Security',
    lecturer: 'Dr. K. Jayasinghe',
    semester: 'Sem 1',
    attendedSessions: 10,
    totalSessions: 10,
    attendancePercentage: 100,
    sessions: [
      {
        id: 'sec-s1',
        title: 'Cryptography Fundamentals',
        timeText: 'Tomorrow · 08:00–10:00 · Lab 3 · Lecture',
        type: 'Lecture',
        status: 'upcoming',
        weekHeader: 'This week',
      },
      {
        id: 'sec-s2',
        title: 'Symmetric Encryption Practice',
        timeText: '17 Jul · 08:00–10:00 · Lab 3 · Lab',
        type: 'Lab',
        status: 'marked',
        recordedTime: 'Recorded at 08:01',
        weekHeader: '13–19 July',
      },
    ],
    attendanceRecords: [
      {
        id: 'sec-r1',
        day: '17',
        month: 'JUL',
        title: 'Lab 03',
        recordedText: 'Recorded at 08:01',
        status: 'Present',
      },
      {
        id: 'sec-r2',
        day: '10',
        month: 'JUL',
        title: 'Lecture 03',
        recordedText: 'Recorded at 08:03',
        status: 'Present',
      },
    ],
  },
  {
    id: 'en3204',
    code: 'EN3204',
    title: 'Engineering Mathematics',
    lecturer: 'Dr. R. Silva',
    semester: 'Sem 1',
    attendedSessions: 6,
    totalSessions: 9,
    attendancePercentage: 67,
    sessions: [
      {
        id: 'math-s1',
        title: 'Fourier Analysis Introduction',
        timeText: 'Today · 15:30–17:30 · Room C1 · Lecture',
        type: 'Lecture',
        status: 'upcoming',
        weekHeader: 'This week',
      },
      {
        id: 'math-s2',
        title: 'Complex Analysis Workshop',
        timeText: '18 Jul · 10:00–12:00 · Room C1 · Workshop',
        type: 'Workshop',
        status: 'marked',
        recordedTime: 'Recorded at 10:10',
        weekHeader: '13–19 July',
      },
      {
        id: 'math-s3',
        title: 'Partial Differential Equations',
        timeText: '11 Jul · 10:00–12:00 · Room C1 · Lecture',
        type: 'Lecture',
        status: 'missed',
        weekHeader: '6–12 July',
      },
    ],
    attendanceRecords: [
      {
        id: 'math-r1',
        day: '18',
        month: 'JUL',
        title: 'Workshop 03',
        recordedText: 'Recorded at 10:10',
        status: 'Present',
      },
      {
        id: 'math-r2',
        day: '11',
        month: 'JUL',
        title: 'Lecture 02',
        recordedText: 'No record found',
        status: 'Absent',
      },
    ],
  },
];
