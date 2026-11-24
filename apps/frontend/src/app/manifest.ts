import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "ArtisanOS — Nigeria's All-Artisan Nearby Marketplace & Business OS",
    short_name: "ArtisanOS",
    description:
      "Find nearby verified artisans in your neighborhood, book services, patronize local goods, and manage artisan workshops across Nigeria.",
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
