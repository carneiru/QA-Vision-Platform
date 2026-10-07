import { loginPath, safeNext } from "./redirect";

describe("safeNext accepts only same-origin relative paths", () => {
  test.each([
    ["/projects/42/runs?status=failing#top", "/projects/42/runs?status=failing#top"],
    ["/invitations/abc123", "/invitations/abc123"],
    ["/", "/"],
  ])("%s", (raw, expected) => expect(safeNext(raw)).toBe(expected));

  test.each([
    ["protocol-relative", "//evil.example/x"],
    ["absolute http", "http://evil.example"],
    ["absolute https", "https://evil.example/projects/1"],
    ["javascript scheme", "javascript:alert(1)"],
    ["data scheme", "data:text/html,x"],
    ["backslash trick", "/\\evil.example"],
    ["backslash after path", "/projects\\..\\..\\x"],
    ["tab inside, which browsers strip to //", "/\t/evil.example"],
    ["newline inside", "/\n/evil.example"],
    ["no leading slash", "projects/42"],
    ["bare host", "evil.example"],
    ["empty", ""],
    ["login itself, which would loop", "/login?next=/x"],
  ])("rejects %s", (_name, raw) => expect(safeNext(raw)).toBeNull());

  test("rejects a missing value", () => {
    expect(safeNext(null)).toBeNull();
    expect(safeNext(undefined)).toBeNull();
  });
});

describe("loginPath", () => {
  test("remembers where the user was going", () => {
    expect(loginPath({ pathname: "/projects/42/runs", search: "?status=failing", hash: "" }))
      .toBe("/login?next=%2Fprojects%2F42%2Fruns%3Fstatus%3Dfailing");
  });
  test("marks an expired session", () => {
    expect(loginPath({ pathname: "/invitations/t", search: "", hash: "" }, "expired"))
      .toBe("/login?next=%2Finvitations%2Ft&reason=expired");
  });
  test("the front page is not worth remembering", () => {
    expect(loginPath({ pathname: "/", search: "", hash: "" })).toBe("/login");
    expect(loginPath({ pathname: "/", search: "", hash: "" }, "expired")).toBe("/login?reason=expired");
  });
});
