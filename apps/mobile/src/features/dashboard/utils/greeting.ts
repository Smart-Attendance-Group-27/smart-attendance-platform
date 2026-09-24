export function getGreeting(date: Date = new Date()): string {
  const hour = date.getHours();

  if (hour >= 5 && hour < 12) {
    return 'Good morning';
  }
  if (hour >= 12 && hour < 17) {
    return 'Good afternoon';
  }
  if (hour >= 17 && hour < 21) {
    return 'Good evening';
  }
  return 'Good night';
}

export function formatGreeting(name: string | undefined, date: Date = new Date()): string {
  const greeting = getGreeting(date);
  const trimmed = name?.trim();

  return trimmed ? `${greeting}, ${trimmed}` : greeting;
}
