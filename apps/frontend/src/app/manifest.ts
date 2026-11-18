import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "ArtisanOS — Measurement & Order Workspace",
    short_name: "ArtisanOS",
    description:
      "Multi-tenant SaaS for tailors, shoemakers, leatherworkers, and measurement-based artisan businesses.",
    start_url: "/dashboard",
    display: "standalone",
    background_color: "#fffdfb",
    theme_color: "#240c21",
    orientation: "portrait-primary",
  };
}
