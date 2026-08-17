import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// `test.globals` isn't enabled (see vitest.config.mts), so @testing-library/react
// can't auto-detect the test framework to register its own cleanup — without this,
// DOM nodes from one test leak into the next and break queries like getByText.
afterEach(() => {
  cleanup();
});
