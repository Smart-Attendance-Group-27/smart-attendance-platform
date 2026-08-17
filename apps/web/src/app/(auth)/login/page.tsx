const ERROR_MESSAGES: Record<string, string> = {
  invalid_state: "Your sign-in attempt expired or was tampered with. Please try again.",
  token_exchange_failed: "Keycloak could not complete sign-in. Please try again.",
  invalid_id_token: "Keycloak returned an invalid sign-in token. Please try again.",
  no_web_role: "Your account does not have lecturer or administrator access to this dashboard.",
  access_denied: "Sign-in was cancelled.",
};

function errorMessageFor(code: string | undefined): string | null {
  if (!code) return null;
  return ERROR_MESSAGES[code] ?? "Something went wrong signing you in. Please try again.";
}

export default async function LoginPage(props: PageProps<"/login">) {
  const searchParams = await props.searchParams;
  const errorParam = typeof searchParams.error === "string" ? searchParams.error : undefined;
  const errorMessage = errorMessageFor(errorParam);

  return (
    <main className="flex min-h-screen items-center justify-center bg-[var(--page)] px-4 py-10">
      <div className="w-full max-w-md border border-[var(--line)] bg-[var(--surface)] shadow-[var(--shadow)]">
        <div className="border-b-[3px] border-[var(--uom-gold)] bg-[var(--uom-blue)] px-6 py-5 text-white">
          <p className="text-xs uppercase tracking-wide text-[#dceaf4]">UniAttend</p>
          <h1 className="mt-1 text-lg font-semibold">Smart Attendance Dashboard</h1>
        </div>

        <div className="p-6">
          <p className="mb-4 text-xs leading-relaxed text-[var(--muted)]">
            Sign in with your university account. Lecturer and administrator access is issued through
            Keycloak — this dashboard has no separate password of its own.
          </p>

          {errorMessage ? (
            <p role="alert" className="mb-4 border border-[#e5bcbc] bg-[var(--danger-bg)] p-3 text-xs text-[var(--danger)]">
              {errorMessage}
            </p>
          ) : null}

          <a
            href="/api/auth/login"
            className="flex w-full items-center justify-center gap-2 border border-[var(--uom-blue)] bg-[var(--uom-blue)] px-4 py-3 text-sm font-semibold text-white hover:bg-[var(--uom-blue-dark)]"
          >
            Sign in with Keycloak
          </a>
        </div>
      </div>
    </main>
  );
}
