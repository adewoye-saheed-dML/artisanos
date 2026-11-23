import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "ArtisanOS — Nigeria's All-Artisan Nearby Marketplace & Business OS",
    short_name: "ArtisanOS",
    description:
      "Find nearby artisans by Nigerian Ward or Polling Unit, call for work, patronize goods & services, and manage artisan workshops.",
    start_url: "/marketplace",
    display: "standalone",
    background_color: "#fffbfc",
    theme_color: "#221420",
    orientation: "portrait-primary",
    icons: [
      {
        src: "/icon.svg",
        sizes: "any",
        type: "image/svg+xml",
      },
      {
        src: "/apple-icon",
        sizes: "180x180",
        type: "image/png",
      },
    ],
  };
}
