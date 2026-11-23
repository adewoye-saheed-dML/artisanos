import type { AvailabilityStatus, OrgCategory, ProximityTier } from "@/types/api";

export interface ArtisanCategoryMeta {
  value: OrgCategory;
  label: string;
  shortLabel: string;
  group: "Fashion & Craft" | "Home & Building Trades" | "Auto & Tech" | "Lifestyle & Events";
  defaultProductCategory: string;
}

export const ARTISAN_CATEGORIES: ArtisanCategoryMeta[] = [
  {
    value: "tailor",
    label: "Tailor & Fashion Designer",
    shortLabel: "Tailor",
    group: "Fashion & Craft",
    defaultProductCategory: "Bespoke Tailoring",
  },
  {
    value: "shoemaker",
    label: "Shoemaker & Cobbler",
    shortLabel: "Shoemaker",
    group: "Fashion & Craft",
    defaultProductCategory: "Handcrafted Footwear",
  },
  {
    value: "leatherworker",
    label: "Leatherworker & Bag Maker",
    shortLabel: "Leatherworker",
    group: "Fashion & Craft",
    defaultProductCategory: "Leather Goods",
  },
  {
    value: "electrician",
    label: "Electrician & Solar Tech",
    shortLabel: "Electrician",
    group: "Home & Building Trades",
    defaultProductCategory: "Electrical & Solar",
  },
  {
    value: "plumber",
    label: "Plumber & Pipefitter",
    shortLabel: "Plumber",
    group: "Home & Building Trades",
    defaultProductCategory: "Plumbing & Water",
  },
  {
    value: "carpenter",
    label: "Carpenter & Furniture Maker",
    shortLabel: "Carpenter",
    group: "Home & Building Trades",
    defaultProductCategory: "Furniture & Woodwork",
  },
  {
    value: "ac_technician",
    label: "AC & Refrigeration Tech",
    shortLabel: "AC Technician",
    group: "Home & Building Trades",
    defaultProductCategory: "AC & Cooling",
  },
  {
    value: "welder",
    label: "Welder & Metal Fabricator",
    shortLabel: "Welder",
    group: "Home & Building Trades",
    defaultProductCategory: "Metal Fabrication",
  },
  {
    value: "painter",
    label: "Painter & Interior Decorator",
    shortLabel: "Painter",
    group: "Home & Building Trades",
    defaultProductCategory: "Painting & Decor",
  },
  {
    value: "mason",
    label: "Mason, Tiler & Bricklayer",
    shortLabel: "Mason / Tiler",
    group: "Home & Building Trades",
    defaultProductCategory: "Masonry & Tiling",
  },
  {
    value: "mechanic",
    label: "Auto Mechanic & Technician",
    shortLabel: "Auto Mechanic",
    group: "Auto & Tech",
    defaultProductCategory: "Auto Repair",
  },
  {
    value: "generator_tech",
    label: "Generator & Inverter Tech",
    shortLabel: "Generator Tech",
    group: "Auto & Tech",
    defaultProductCategory: "Power & Generators",
  },
  {
    value: "phone_repair",
    label: "Phone & Electronics Repair",
    shortLabel: "Phone Repair",
    group: "Auto & Tech",
    defaultProductCategory: "Electronics Repair",
  },
  {
    value: "hair_beauty",
    label: "Hair Stylist, Barber & Beauty",
    shortLabel: "Hair & Beauty",
    group: "Lifestyle & Events",
    defaultProductCategory: "Beauty & Grooming",
  },
  {
    value: "caterer",
    label: "Caterer & Baker",
    shortLabel: "Caterer / Baker",
    group: "Lifestyle & Events",
    defaultProductCategory: "Catering & Pastries",
  },
  {
    value: "cleaner",
    label: "Cleaning & Laundry Services",
    shortLabel: "Cleaning / Laundry",
    group: "Lifestyle & Events",
    defaultProductCategory: "Cleaning Services",
  },
  {
    value: "other",
    label: "Other Artisan / Craft",
    shortLabel: "Other Craft",
    group: "Fashion & Craft",
    defaultProductCategory: "Custom Craft",
  },
];

export const ORG_CATEGORY_VALUES = ARTISAN_CATEGORIES.map((c) => c.value) as [
  OrgCategory,
  ...OrgCategory[],
];

export function getCategoryLabel(category: string | undefined | null): string {
  if (!category) return "Artisan";
  return ARTISAN_CATEGORIES.find((c) => c.value === category)?.label || category.replace(/_/g, " ");
}

export function getDefaultProductCategory(category: string | undefined | null): string {
  return (
    ARTISAN_CATEGORIES.find((c) => c.value === category)?.defaultProductCategory || "Artisan Goods"
  );
}

export function buildTelHref(phone: string | undefined | null): string | null {
  if (!phone) return null;
  const cleaned = phone.replace(/[^\d+]/g, "");
  return cleaned.length >= 6 ? `tel:${cleaned}` : null;
}

export function buildWhatsAppHref(
  phone: string | undefined | null,
  prefillMessage?: string
): string | null {
  if (!phone) return null;
  let digits = phone.replace(/\D/g, "");
  if (!digits) return null;
  // Convert Nigerian local 080... format to 23480...
  if (digits.startsWith("0") && digits.length === 11) {
    digits = `234${digits.slice(1)}`;
  }
  const base = `https://wa.me/${digits}`;
  if (prefillMessage) {
    return `${base}?text=${encodeURIComponent(prefillMessage)}`;
  }
  return base;
}

export function getAvailabilityBadge(status: AvailabilityStatus | string) {
  switch (status) {
    case "available":
      return {
        label: "Available for Work",
        classes: "border-emerald-200 bg-emerald-50 text-emerald-800",
        dot: "bg-emerald-500",
      };
    case "busy":
      return {
        label: "Busy / Limited Slots",
        classes: "border-amber-200 bg-amber-50 text-amber-800",
        dot: "bg-amber-500",
      };
    default:
      return {
        label: "Offline",
        classes: "border-slate-200 bg-slate-100 text-slate-600",
        dot: "bg-slate-400",
      };
  }
}

export function getProximityBadgeClasses(tier: ProximityTier | null): string {
  switch (tier) {
    case "same_polling_unit":
      return "border-emerald-300 bg-emerald-600 text-white";
    case "same_ward":
      return "border-brand-300 bg-brand-700 text-white";
    case "covers_ward":
      return "border-brand-200 bg-surface-blush text-brand-700";
    case "same_lga":
      return "border-line bg-white text-plum";
    default:
      return "border-line-soft bg-surface text-ink-soft";
  }
}
