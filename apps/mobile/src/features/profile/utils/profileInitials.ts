export function getProfileInitials(fullName: string): string {
  const nameParts = fullName.trim().split(/\s+/).filter(Boolean);

  if (nameParts.length === 0) {
    return '';
  }

  const firstInitial = nameParts[0][0]?.toUpperCase() ?? '';
  const lastInitial =
    nameParts.length > 1
      ? (nameParts[nameParts.length - 1][0]?.toUpperCase() ?? '')
      : '';

  return `${firstInitial}${lastInitial}`;
}
