# Performance-profile evidence

Start with [performance-test-report.md](performance-test-report.md). The
`scripts` directory contains the exact k6 scenarios. Open each
`evidence/<scenario>/k6-dashboard.html` file in a browser for the clearest
interactive-style report, and use its adjacent `k6-summary.json` for the raw
aggregate values.

The current evidence set contains 200 measured transactions per scenario (800
in total), executed sequentially with one virtual user. Concurrency is covered
by the separate load test.

The scripts require `TEST_USERNAME`, `TEST_PASSWORD` and, for authenticated
read scenarios, `PKCE_VERIFIER` environment variables. Supply them at runtime
from a protected source. Do not save credentials in this directory.
