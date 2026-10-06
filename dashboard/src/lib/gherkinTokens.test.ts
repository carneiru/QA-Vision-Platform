import { tokenizeLine } from "./gherkinTokens";

test("keywords, tags, tables, doc strings and comments", () => {
  expect(tokenizeLine("  Given a cart")).toEqual([{ kind: "text", text: "  " }, { kind: "keyword", text: "Given " }, { kind: "text", text: "a cart" }]);
  expect(tokenizeLine("Scenario Outline: Pay")[0]).toEqual({ kind: "keyword", text: "Scenario Outline:" });
  expect(tokenizeLine("    | a | b |")[1].kind).toBe("table");
  expect(tokenizeLine('    """json')[1].kind).toBe("docstring");
  expect(tokenizeLine("@smoke @ado-1")[0].kind).toBe("tag");
  expect(tokenizeLine("# note")[0].kind).toBe("comment");
  expect(tokenizeLine("  Dado um carrinho")[1]).toEqual({ kind: "keyword", text: "Dado " });
});

test("placeholders and quoted values in steps", () => {
  expect(tokenizeLine("When I toggle <off>")).toEqual([
    { kind: "keyword", text: "When " }, { kind: "text", text: "I toggle " }, { kind: "param", text: "<off>" }]);
  expect(tokenizeLine('Then I see "SAVE10" applied')).toEqual([
    { kind: "keyword", text: "Then " }, { kind: "text", text: "I see " }, { kind: "string", text: '"SAVE10"' }, { kind: "text", text: " applied" }]);
  expect(tokenizeLine('When I apply "<code>"')).toEqual([
    { kind: "keyword", text: "When " }, { kind: "text", text: "I apply " },
    { kind: "string", text: '"' }, { kind: "param", text: "<code>" }, { kind: "string", text: '"' }]);
  expect(tokenizeLine('And I type "a <x> b"').slice(2)).toEqual([
    { kind: "string", text: '"a ' }, { kind: "param", text: "<x>" }, { kind: "string", text: ' b"' }]);
});

test("numbers stay plain; an unclosed quote stays plain; cells highlight placeholders only", () => {
  expect(tokenizeLine("Given 3 items")[1]).toEqual({ kind: "text", text: "3 items" });
  expect(tokenizeLine('Given a "broken')[1]).toEqual({ kind: "text", text: 'a "broken' });
  expect(tokenizeLine('    | <code> | "x" |')).toEqual([
    { kind: "text", text: "    " }, { kind: "table", text: "| " }, { kind: "param", text: "<code>" }, { kind: "table", text: ' | "x" |' }]);
});
