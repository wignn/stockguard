import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import LandingPage from "@/app/page";

it("renders StokGuard landing page with hero, workflow steps, and login action", () => {
  render(<LandingPage />);

  // Brand / Wordmark
  expect(screen.getByRole("banner")).toBeInTheDocument();
  expect(screen.getAllByText(/Stok/i).length).toBeGreaterThan(0);

  // CTA Masuk link
  const loginLinks = screen.getAllByRole("link", { name: /masuk/i });
  expect(loginLinks.length).toBeGreaterThan(0);
  expect(loginLinks[0]).toHaveAttribute("href", "/login");

  // Key headings
  expect(screen.getByRole("heading", { level: 1, name: /kendalikan stok/i })).toBeInTheDocument();
  expect(screen.getByRole("heading", { level: 2, name: /tiga langkah/i })).toBeInTheDocument();
  expect(screen.getByRole("heading", { level: 2, name: /keunggulan integritas/i })).toBeInTheDocument();

  // Workflow steps
  expect(screen.getByText(/pencatatan & nota ocr/i)).toBeInTheDocument();
  expect(screen.getByText(/opname fisik berkala/i)).toBeInTheDocument();
  expect(screen.getByText(/investigasi & persetujuan/i)).toBeInTheDocument();
});
