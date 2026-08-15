export type FreshLocationReading = {
  readonly latitude: number;
  readonly longitude: number;
  readonly accuracyM: number | null;
  readonly capturedAt: string;
  readonly mocked: boolean;
};

export type FreshLocationResult =
  | { readonly status: 'captured'; readonly reading: FreshLocationReading }
  | { readonly status: 'permission_denied' }
  | { readonly status: 'services_disabled' }
  | { readonly status: 'unavailable' };
