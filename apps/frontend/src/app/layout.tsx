import type { Metadata, Viewport } from "next";
import { ReactNode } from "react";

import { AuthProvider } from "@/providers/auth-provider";
import { QueryProvider } from "@/providers/query-provider";

import "./globals.css";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://artisanos.ng";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "ArtisanOS Nigeria — Find Verified Artisans Near Your Neighborhood",
    template: "%s | ArtisanOS Nigeria",
  },
  description:
    "Find verified electricians, plumbers, tailors, carpenters, mechanics, shoemakers, and local makers right in your neighborhood across Nigeria. Hire directly for services or buy handcrafted goods with secure payment protection.",
  keywords: [
    "find artisans in Nigeria",
    "verified artisans near me",
    "electrician near me Lagos",
    "plumber near me Abuja",
    "tailor near me Nigeria",
    "carpenter near me Lagos",
    "auto mechanic near me Nigeria",
    "shoemaker Nigeria",
    "AC repair technician near me",
    "solar inverter installer Nigeria",
    "local artisan finder Nigeria",
    "neighborhood artisan directory Nigeria",
    "NIN verified artisans Nigeria",
    "CAC verified artisans Nigeria",
    "escrow payment for artisans Nigeria",
    "hire handyman Lagos Abuja Port Harcourt Ibadan Kano",
    "buy handmade goods Nigeria",
    "ArtisanOS",
  ],
  authors: [{ name: "ArtisanOS Nigeria" }],
  creator: "ArtisanOS",
  publisher: "ArtisanOS",
  alternates: {
    canonical: "/",
  },
  openGraph: {
    type: "website",
    locale: "en_NG",
    url: SITE_URL,
    siteName: "ArtisanOS Nigeria",
    title: "ArtisanOS Nigeria — Trusted Artisans Right in Your Neighborhood",
    description:
      "Search verified local artisans near your area across Nigeria. Book home repairs, custom services, or buy handcrafted goods with secure payment protection.",
    images: [
      {
        url: "https://images.pexels.com/photos/3738095/pexels-photo-3738095.jpeg?auto=compress&cs=tinysrgb&w=1200",
        width: 1200,
        height: 800,
        alt: "Tailor sewing fabric on a sewing machine in a workshop on ArtisanOS Nigeria",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "ArtisanOS Nigeria — Find Verified Artisans Near Your Neighborhood",
    description:
      "Discover verified electricians, plumbers, tailors, carpenters, and mechanics right in your neighborhood across Nigeria.",
    images: [
      "https://images.pexels.com/photos/3738095/pexels-photo-3738095.jpeg?auto=compress&cs=tinysrgb&w=1200",
    ],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
  appleWebApp: {
    capable: true,
    title: "ArtisanOS",
    statusBarStyle: "black-translucent",
  },
};

export const viewport: Viewport = {
  themeColor: "#240c21",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en-NG">
      <body>
        <QueryProvider>
          <AuthProvider>{children}</AuthProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
