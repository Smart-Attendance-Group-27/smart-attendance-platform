export default function Home() {
  return (
    <main className="min-h-screen bg-zinc-950 px-6 py-10 text-zinc-100">
      <section className="mx-auto flex max-w-3xl flex-col gap-5">
        <p className="text-sm font-medium uppercase tracking-wide text-cyan-300">
          Smart Attendance Platform
        </p>
        <h1 className="text-4xl font-semibold tracking-tight text-white">
          Web testing workspace
        </h1>
        <p className="max-w-2xl text-zinc-400">
          Use this temporary web app to test lecturer-side QR session creation
          against the FastAPI core backend.
        </p>

        <a
          href="/qr-test"
          className="w-fit rounded-md bg-cyan-400 px-4 py-3 text-sm font-semibold text-zinc-950 transition hover:bg-cyan-300"
        >
          Open QR test
        </a>
      </section>
    </main>
  );
}
