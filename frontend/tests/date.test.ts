import { describe, expect, it } from "vitest";

import { addDays, dayLabel, todayString } from "@/lib/date";

describe("date helpers", () => {
  it("formats local dates without a UTC day shift", () => {
    expect(todayString(new Date(2026, 7, 29, 23, 30))).toBe("2026-08-29");
  });

  it("moves across month boundaries and labels nearby dates", () => {
    expect(addDays("2026-08-31", 1)).toBe("2026-09-01");
    expect(dayLabel("2026-08-29", "2026-08-29")).toBe("今天");
    expect(dayLabel("2026-08-30", "2026-08-29")).toBe("明天");
  });
});
