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
