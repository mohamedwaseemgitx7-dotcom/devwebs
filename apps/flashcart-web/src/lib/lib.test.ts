import { describe, expect, it } from "vitest";
import { ApiError, errorMessage } from "../api/client";
import { passwordProblems, safeNext } from "../pages/AuthPages";
import { parseFilters, toApiQuery, toSearchParams } from "./filters";
import { formatCount, formatPrice } from "./format";

describe("formatPrice", () => {
  it("formats paise as Indian rupees", () => {
    expect(formatPrice(269900)).toBe("₹2,699");
    expect(formatPrice(12345678)).toBe("₹1,23,456.78");
    expect(formatPrice(0)).toBe("₹0");
  });
  it("abbreviates large counts", () => {
    expect(formatCount(1024)).toBe("1k+");
    expect(formatCount(37)).toBe("37");
  });
});

describe("URL filters", () => {
  it("round-trips valid filters", () => {
    const f = parseFilters(new URLSearchParams("q=mouse&category=Electronics&color=black&min_price=500&sort=price_asc&page=2"));
    expect(f).toMatchObject({ q: "mouse", category: ["Electronics"], color: ["black"], minPrice: 500, sort: "price_asc", page: 2 });
    expect(parseFilters(toSearchParams(f))).toEqual(f);
  });
  it("drops invalid or malicious values instead of sending them to the API", () => {
    const f = parseFilters(new URLSearchParams("category=Weapons&category[$ne]=x&color=%3Cscript%3E&sort=evil&page=-4&min_price=abc&min_rating=9"));
    expect(f.category).toEqual([]);
    expect(f.color).toEqual([]);
    expect(f.sort).toBe("rating");
    expect(f.page).toBe(1);
    expect(f.minPrice).toBeUndefined();
    expect(f.minRating).toBeUndefined();
  });
  it("converts rupees to paise for the API", () => {
    const q = toApiQuery(parseFilters(new URLSearchParams("min_price=500&max_price=2000")));
    expect(q.min_price).toBe(50000);
    expect(q.max_price).toBe(200000);
  });
  it("caps search length and page number", () => {
    const f = parseFilters(new URLSearchParams(`q=${"a".repeat(500)}&page=9999`));
    expect(f.q).toHaveLength(100);
    expect(f.page).toBe(1);
  });
});

describe("safeNext (open-redirect protection)", () => {
  it.each([
    ["/checkout", "/checkout"],
    ["/orders?page=2", "/orders?page=2"],
    ["//evil.example.com", "/products"],
    ["https://evil.example.com", "/products"],
    ["/\\evil.example.com", "/products"],
    ["javascript:alert(1)", "/products"],
    [null, "/products"],
  ])("%s → %s", (input, expected) => {
    expect(safeNext(input)).toBe(expected);
  });
});

describe("passwordProblems", () => {
  it("mirrors the server password policy", () => {
    expect(passwordProblems("Str0ng!Pass")).toEqual([]);
    expect(passwordProblems("short")).toHaveLength(2);
    expect(passwordProblems("alllowercaseletters")).toEqual(["3 of: lowercase, uppercase, digits, symbols"]);
  });
});

describe("errorMessage", () => {
  it("never leaks raw server details", () => {
    expect(errorMessage(new ApiError(500, "Traceback (most recent call last)…", "rid"))).toBe(
      "Something went wrong on our side. Please try again.",
    );
    expect(errorMessage(new ApiError(429, "slow down", null))).toMatch(/Too many requests/);
    expect(errorMessage(new ApiError(422, [{ loc: ["body", "email"], msg: "invalid email" }], null))).toBe("email: invalid email");
    expect(errorMessage(new ApiError(409, { message: "Some items are no longer available" }, null))).toBe(
      "Some items are no longer available",
    );
    expect(errorMessage(new TypeError("Failed to fetch"))).toMatch(/Network error/);
  });
});
