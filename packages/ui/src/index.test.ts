import { expect, test } from "vitest";

import { packageName } from "./index.js";

test("the package is wired into the workspace", () => {
  expect(packageName).toBe("@globalens/ui");
});
