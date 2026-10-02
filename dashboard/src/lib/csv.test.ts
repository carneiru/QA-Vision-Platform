import { toCsv } from "./csv";

test("quotes fields containing commas, quotes and newlines", () => {
  const csv = toCsv(
    ["name", "message"],
    [
      ["plain", "hello"],
      ["com,ma", 'say "hi"'],
      ["line", "a\nb"],
      ["empty", null],
      ["number", 42],
    ],
  );
  expect(csv.split("\r\n")).toEqual([
    "name,message",
    "plain,hello",
    '"com,ma","say ""hi"""',
    'line,"a\nb"',
    "empty,",
    "number,42",
  ]);
});
