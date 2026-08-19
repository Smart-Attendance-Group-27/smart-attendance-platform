import Image from "next/image";
import loginBackground from "../../../../assests/background.jpg";
import uniLogo from "../../../../assests/Uni.jpg";

const ERROR_MESSAGES: Record<string, string> = {
  invalid_state:
    "Your sign-in attempt expired or was tampered with. Please try again.",
  token_exchange_failed:
    "Keycloak could not complete sign-in. Please try again.",
  invalid_id_token:
    "Keycloak returned an invalid sign-in token. Please try again.",
  no_web_role:
    "Your account does not have lecturer or administrator access to this dashboard.",
  access_denied: "Sign-in was cancelled.",
};

function errorMessageFor(code: string | undefined): string | null {
  if (!code) return null;
  return (
    ERROR_MESSAGES[code] ??
    "Something went wrong signing you in. Please try again."
  );
}

export default async function LoginPage(props: PageProps<"/login">) {
  const searchParams = await props.searchParams;
  const errorParam =
    typeof searchParams.error === "string" ? searchParams.error : undefined;
  const errorMessage = errorMessageFor(errorParam);

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-10">
      <Image
        alt=""
        aria-hidden="true"
        className="absolute inset-0 z-0 object-cover"
        fill
        priority
        sizes="100vw"
        src={loginBackground}
      />
      <div className="absolute inset-0 z-10 bg-[linear-gradient(135deg,rgba(0,45,85,0.62),rgba(0,45,85,0.34)_48%,rgba(243,192,58,0.22))]" />
      <div className="absolute inset-0 z-10 bg-[radial-gradient(circle_at_15%_15%,rgba(255,255,255,0.18),transparent_28%),radial-gradient(circle_at_85%_82%,rgba(255,255,255,0.14),transparent_30%)]" />

      <div className="relative z-20 w-full max-w-xl overflow-hidden rounded-[2rem] border border-white/50 bg-white/98 shadow-[0_28px_90px_rgba(0,0,0,0.35)] backdrop-blur-md">
        <section className="flex min-h-[600px] items-center px-8 py-14 sm:px-18">
          <div className="mx-auto w-full max-w-lg">
            <div className="mb-8 text-center">
              <Image
                alt="University logo"
                className="mx-auto h-28 w-28 rounded-full object-cover ring-1 ring-[var(--line)] sm:h-32 sm:w-32"
                priority
                src={uniLogo}
              />
              <p className="mt-5 text-xs uppercase tracking-[0.28em] text-[var(--uom-blue)]">
                UniAttend
              </p>
              <h1 className="mt-2 text-xl font-semibold text-[#2c3b47]">
                Smart Attendance Dashboard
              </h1>
            </div>

            <div className="text-center">
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-[var(--uom-blue)]">
                University access
              </p>
              <h2 className="mt-2 text-2xl font-semibold text-[#2c3b47]">
                Welcome back
              </h2>
              <p className="mt-3 text-sm leading-6 text-[var(--muted)]">
                Sign in with your University account.
              </p>
            </div>

            {errorMessage ? (
              <p
                role="alert"
                className="mt-5 border border-[#e5bcbc] bg-[var(--danger-bg)] p-3 text-xs text-[var(--danger)]"
              >
                {errorMessage}
              </p>
            ) : null}

            <a
              href="/api/auth/login"
              className="mt-6 flex w-full items-center justify-center gap-2 border border-[var(--uom-blue)] bg-[var(--uom-blue)] px-4 py-3 text-sm font-semibold text-white transition hover:bg-[var(--uom-blue-dark)]"
            >
              Continue with University account
            </a>

            <p className="mt-4 text-center text-[11px] leading-5 text-[var(--muted)]">
              Use your assigned lecturer or administrator account. Student
              accounts continue through the mobile app.
            </p>
          </div>
        </section>
      </div>
    </main>
  );
}
