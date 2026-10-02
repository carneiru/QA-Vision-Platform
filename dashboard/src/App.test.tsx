import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";

test("renders the app shell (login when logged out)", async () => {
  const qc = new QueryClient();
  render(
    <QueryClientProvider client={qc}>
      <App />
    </QueryClientProvider>,
  );
  // Boot first probes the cookie session (the test server answers 401).
  expect(await screen.findByRole("button", { name: /sign in/i })).toBeInTheDocument();
});
