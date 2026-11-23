import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Find Verified Artisans Near Your Ward & Polling Unit",
  description:
    "Browse verified electricians, plumbers, tailors, carpenters, mechanics, shoemakers, and handcrafted goods across all 36 Nigerian States, FCT Abuja, 774 LGAs, Wards, and Polling Units.",
};

export default function MarketplaceLayout({ children }: { children: ReactNode }) {
  return children;
}
