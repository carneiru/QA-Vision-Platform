import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";

test("renders the app shell (login when logged out)", () => {
  const qc = new QueryClient();
  render(
    <QueryClientProvider client={qc}>
      <App />
    </QueryClientProvider>,
  );
  expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
});
