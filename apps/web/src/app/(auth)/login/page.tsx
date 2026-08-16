import { mockSignIn } from "@/app/actions/auth";

const MOCK_ACCOUNTS = [
  { role: "lecturer" as const, name: "Prof. Dulani Meedeniya", description: "Lecturer dashboard access" },
  { role: "administrator" as const, name: "Dr. Sunimal Rathnayake", description: "Administrator dashboard access" },
];

export default function LoginPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-[var(--page)] px-4 py-10">
      <div className="w-full max-w-md border border-[var(--line)] bg-[var(--surface)] shadow-[var(--shadow)]">
        <div className="border-b-[3px] border-[var(--uom-gold)] bg-[var(--uom-blue)] px-6 py-5 text-white">
          <p className="text-xs uppercase tracking-wide text-[#dceaf4]">UniAttend</p>
          <h1 className="mt-1 text-lg font-semibold">Smart Attendance Dashboard</h1>
        </div>

        <div className="p-6">
          <p className="mb-4 text-xs leading-relaxed text-[var(--muted)]">
            Sign-in for this preview uses a mock account picker instead of Keycloak while the web OIDC
            client is provisioned. Choose the role you want to preview.
          </p>

          <div className="flex flex-col gap-3">
            {MOCK_ACCOUNTS.map((account) => (
              <form key={account.role} action={mockSignIn}>
                <input type="hidden" name="role" value={account.role} />
                <input type="hidden" name="name" value={account.name} />
                <button
                  type="submit"
                  className="flex w-full items-center justify-between border border-[var(--line)] px-4 py-3 text-left hover:border-[var(--uom-blue)] hover:bg-[var(--uom-blue-soft)]"
                >
                  <span>
                    <span className="block text-sm font-semibold text-[var(--text)]">{account.name}</span>
                    <span className="block text-xs text-[var(--muted)]">{account.description}</span>
                  </span>
                  <span className="text-xs font-medium text-[var(--link)]">Continue &rarr;</span>
                </button>
              </form>
            ))}
          </div>
        </div>
      </div>
    </main>
  );
}
