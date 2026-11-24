import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Find Verified Artisans Near You",
  description:
    "Browse verified electricians, plumbers, tailors, carpenters, mechanics, shoemakers, and handcrafted goods across neighborhoods in all 36 Nigerian States and FCT Abuja.",
};

export default function MarketplaceLayout({ children }: { children: ReactNode }) {
  return children;
}
