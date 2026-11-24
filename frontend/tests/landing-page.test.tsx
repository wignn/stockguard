import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import LandingPage from "@/app/page";

it("renders StokGuard anti-slop landing page with real operational previews and login action", () => {
  render(<LandingPage />);

  // Brand / Wordmark
  expect(screen.getByRole("banner")).toBeInTheDocument();
  expect(screen.getAllByText(/Stok/i).length).toBeGreaterThan(0);

  // CTA Masuk link
  const loginLinks = screen.getAllByRole("link", { name: /masuk/i });
  expect(loginLinks.length).toBeGreaterThan(0);
  expect(loginLinks[0]).toHaveAttribute("href", "/login");

  // Core grounded headings
  expect(
    screen.getByRole("heading", {
      level: 1,
      name: /saat toko tutup sore ini/i,
    })
  ).toBeInTheDocument();
  expect(
    screen.getByRole("heading", {
      level: 2,
      name: /tiga alur kerja nyata/i,
    })
  ).toBeInTheDocument();
  expect(
    screen.getByRole("heading", {
      level: 2,
      name: /realita lapangan/i,
    })
  ).toBeInTheDocument();

  // Three concrete operational workflow elements
  expect(screen.getByText(/opname fisik terarah tanpa tutup toko/i)).toBeInTheDocument();
  expect(screen.getByText(/nota pasar basah atau supplier langsung dipindai/i)).toBeInTheDocument();
  expect(screen.getByText(/tidak ada riwayat transaksi yang bisa diedit diam-diam/i)).toBeInTheDocument();
});
