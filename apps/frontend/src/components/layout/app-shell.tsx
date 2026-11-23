"use client";

import { useQuery } from "@tanstack/react-query";
import {
  BarChart3,
  Bell,
  Building2,
  Calendar,
  ClipboardList,
  Compass,
  CreditCard,
  Kanban,
  LayoutDashboard,
  Lock,
  LogOut,
  Menu,
  Ruler,
  Settings,
  ShieldAlert,
  ShieldCheck,
  ShoppingBag,
  Users,
  Wrench,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ReactNode, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/form-controls";
import { apiRequest } from "@/lib/api-client";
import { ARTISAN_CATEGORIES, getCategoryLabel } from "@/lib/artisans";
import { cn } from "@/lib/utils";
import { useAuth } from "@/providers/auth-provider";
import type { NotificationListResponse } from "@/types/api";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/customers", label: "Customers", icon: Users },
  { href: "/orders", label: "Orders & Jobs", icon: ClipboardList },
  { href: "/production", label: "Production", icon: Kanban },
  { href: "/appointments", label: "Appointments", icon: Calendar },
  { href: "/products", label: "Goods, Store & Calls", icon: ShoppingBag },
  { href: "/escrow", label: "Escrow Protection", icon: Lock },
  { href: "/verification", label: "KYC Verification", icon: ShieldCheck },
  { href: "/marketplace", label: "Nearby Marketplace", icon: Compass },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/templates", label: "Templates", icon: Ruler },
  { href: "/notifications", label: "Notifications", icon: Bell },
  { href: "/billing", label: "Billing & Plans", icon: CreditCard },
  { href: "/settings", label: "Workspace & Ward", icon: Settings },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, activeOrganization, activeMembership, isLoading, switchOrganization, logout, refreshUser } =
    useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);

  const [orgName, setOrgName] = useState("");
  const [orgCategory, setOrgCategory] = useState("tailor");
  const [orgCurrency, setOrgCurrency] = useState("NGN");
  const [orgError, setOrgError] = useState("");
  const [creatingOrg, setCreatingOrg] = useState(false);

  const { data: notificationsData } = useQuery({
    queryKey: ["notifications-badge", activeOrganization?.id],
    queryFn: () => apiRequest<NotificationListResponse>("/notifications/"),
    enabled: !!user && !!activeOrganization?.id,
    refetchInterval: 30_000,
  });
  const unreadNotifications = notificationsData?.unread_count ?? 0;

  useEffect(() => {
    if (!isLoading && !user) {
      router.replace("/login");
    }
  }, [isLoading, user, router]);

  useEffect(() => {
    if (!mobileOpen) return;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMobileOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = prevOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [mobileOpen]);

  if (isLoading) {
    return (
      <div className="mezer-hero-bg flex min-h-screen items-center justify-center">
        <div className="rounded-full border border-line bg-white px-5 py-2.5 text-sm font-medium text-ink-soft shadow-mezer-sm">
          Loading workspace...
        </div>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  if (!activeOrganization) {
    return (
      <div className="mezer-hero-bg flex min-h-screen items-center justify-center p-4">
        <Card className="w-full max-w-md rounded-mezer-lg">
          <CardHeader>
            <div className="mezer-eyebrow mb-1">Workspace Onboarding</div>
            <h1 className="text-xl font-bold text-plum">Create your artisan workspace</h1>
            <p className="mt-1 text-sm text-ink-soft">
              Every customer, measurement profile, and order is isolated to your workspace.
            </p>
          </CardHeader>
          <CardContent>
            <form
              className="space-y-4"
              onSubmit={async (e) => {
                e.preventDefault();
                setOrgError("");
                setCreatingOrg(true);
                try {
                  await apiRequest("/organizations/", {
                    method: "POST",
                    skipOrgHeader: true,
                    body: JSON.stringify({
                      name: orgName,
                      category: orgCategory,
                      currency: orgCurrency,
                    }),
                  });
                  await refreshUser();
                } catch (err) {
                  setOrgError(err instanceof Error ? err.message : "Could not create workspace.");
                } finally {
                  setCreatingOrg(false);
                }
              }}
            >
              {orgError && (
                <div className="rounded-xl border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
                  {orgError}
                </div>
              )}
              <div>
                <Label htmlFor="onboard-name">Business name</Label>
                <Input
                  id="onboard-name"
                  required
                  value={orgName}
                  onChange={(e) => setOrgName(e.target.value)}
                  placeholder="e.g. Savile Lagos Bespoke"
                />
              </div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div>
                  <Label htmlFor="onboard-category">Category</Label>
                  <Select
                    id="onboard-category"
                    value={orgCategory}
                    onChange={(e) => setOrgCategory(e.target.value)}
                  >
                    {ARTISAN_CATEGORIES.map((c) => (
                      <option key={c.value} value={c.value}>
                        {c.label}
                      </option>
                    ))}
                  </Select>
                </div>
                <div>
                  <Label htmlFor="onboard-currency">Currency</Label>
                  <Input
                    id="onboard-currency"
                    maxLength={3}
                    value={orgCurrency}
                    onChange={(e) => setOrgCurrency(e.target.value.toUpperCase())}
                  />
                </div>
              </div>
              <Button type="submit" className="w-full" disabled={creatingOrg}>
                {creatingOrg ? "Creating workspace..." : "Create workspace"}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    );
  }

  const sidebarContent = (
    <div className="flex h-full max-h-[100dvh] flex-col bg-plum px-4 py-5 text-white">
      <div className="flex shrink-0 items-center justify-between gap-2 px-1 pb-5">
        <Link href="/" onClick={() => setMobileOpen(false)} className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-brand">
            <Wrench className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <div className="text-base font-extrabold tracking-tight text-white">ArtisanOS</div>
            <div className="text-[11px] font-medium text-plum-soft">Artisan Business OS</div>
          </div>
        </Link>
        <button
          type="button"
          aria-label="Close navigation menu"
          onClick={() => setMobileOpen(false)}
          className="flex h-9 w-9 items-center justify-center rounded-full border border-white/15 bg-white/5 text-white hover:bg-white/15 lg:hidden"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="mb-4 shrink-0 rounded-2xl border border-white/10 bg-plum-surface p-3">
        <div className="mb-1.5 flex items-center gap-1.5 text-[10px] font-extrabold uppercase tracking-[0.12em] text-[#ffdce6]">
          <Building2 className="h-3.5 w-3.5 text-brand-400" />
          Active Workspace
        </div>
        <Select
          aria-label="Switch active organization"
          value={activeOrganization.id}
          onChange={(e) => switchOrganization(e.target.value)}
          className="mt-0 border-white/15 bg-plum text-xs font-medium text-white focus:border-brand-400 focus:bg-plum"
        >
          {user.memberships.map((m) => (
            <option key={m.organization.id} value={m.organization.id} className="bg-plum text-white">
              {m.organization.name} ({m.role})
            </option>
          ))}
        </Select>
        <div className="mt-2 flex items-center justify-between gap-2 text-[11px] text-plum-soft">
          <span className="truncate">{getCategoryLabel(activeOrganization.category)}</span>
          <span className="shrink-0 rounded-full bg-white/10 px-2 py-0.5 text-[10px] font-semibold text-[#ffdce6]">
            {activeOrganization.ward_name || activeOrganization.currency}
          </span>
        </div>
      </div>

      <nav
        className="flex-1 space-y-1 overflow-y-auto pr-1 pb-4"
        aria-label="Main navigation"
      >
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setMobileOpen(false)}
              className={cn(
                "flex items-center justify-between gap-3 rounded-full px-4 py-2.5 text-sm font-semibold transition-all",
                active
                  ? "bg-gradient-to-r from-brand-600 to-brand-700 text-white shadow-brand"
                  : "text-plum-soft hover:bg-white/10 hover:text-white"
              )}
            >
              <span className="flex min-w-0 items-center gap-3">
                <Icon className="h-4 w-4 shrink-0" />
                <span className="truncate">{item.label}</span>
              </span>
              {item.href === "/notifications" && unreadNotifications > 0 && (
                <span className="inline-flex min-w-5 shrink-0 items-center justify-center rounded-full bg-brand-500 px-1.5 py-0.5 text-[10px] font-extrabold text-white">
                  {unreadNotifications}
                </span>
              )}
            </Link>
          );
        })}
        {user.is_platform_admin && (
          <Link
            href="/platform-admin"
            onClick={() => setMobileOpen(false)}
            className={cn(
              "mt-2 flex items-center gap-3 rounded-full border border-white/15 px-4 py-2.5 text-sm font-semibold transition-all",
              pathname.startsWith("/platform-admin")
                ? "bg-white text-plum shadow-md"
                : "text-[#ffdce6] hover:bg-white/10 hover:text-white"
            )}
          >
            <ShieldAlert className="h-4 w-4 shrink-0" />
            <span className="truncate">Platform Admin</span>
          </Link>
        )}
      </nav>

      <div className="shrink-0 border-t border-white/10 pt-3.5">
        <div className="mb-2.5 rounded-xl bg-white/[0.04] px-3 py-2">
          <div className="truncate text-sm font-semibold text-white">{user.full_name}</div>
          <div className="truncate text-xs text-plum-soft">{user.email}</div>
          <div className="mt-0.5 text-[10px] font-bold uppercase tracking-wider text-brand-300">
            Role: {activeMembership?.role}
          </div>
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-start text-plum-soft hover:bg-white/10 hover:text-white"
          onClick={async () => {
            await logout();
            router.push("/login");
          }}
        >
          <LogOut className="h-4 w-4" />
          Sign out
        </Button>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-surface lg:flex">
      {/* Desktop sidebar */}
      <aside className="hidden lg:fixed lg:inset-y-0 lg:flex lg:w-64 lg:flex-col">
        {sidebarContent}
      </aside>

      {/* Mobile top bar */}
      <header className="sticky top-0 z-30 flex items-center justify-between gap-2 border-b border-line bg-paper/95 px-3.5 py-2.5 backdrop-blur-md lg:hidden">
        <Link href="/dashboard" className="flex min-w-0 flex-1 items-center gap-2.5">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-brand">
            <Wrench className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <div className="truncate text-sm font-bold text-plum">{activeOrganization.name}</div>
            <div className="truncate text-[11px] font-medium text-ink-faint">
              ArtisanOS{activeOrganization.ward_name ? ` · ${activeOrganization.ward_name}` : ""}
            </div>
          </div>
        </Link>
        <div className="flex shrink-0 items-center gap-1.5">
          <Link
            href="/notifications"
            aria-label="Notifications"
            className="relative flex h-10 w-10 items-center justify-center rounded-full border border-line bg-white text-ink hover:bg-surface-blush"
          >
            <Bell className="h-4 w-4" />
            {unreadNotifications > 0 && (
              <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-brand-600 px-1 text-[9px] font-extrabold text-white">
                {unreadNotifications > 9 ? "9+" : unreadNotifications}
              </span>
            )}
          </Link>
          <button
            type="button"
            aria-label="Toggle navigation menu"
            aria-expanded={mobileOpen}
            onClick={() => setMobileOpen(!mobileOpen)}
            className="flex h-10 w-10 items-center justify-center rounded-full border border-line bg-white text-ink hover:bg-surface-blush"
          >
            {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </header>

      {mobileOpen && (
        <div className="fixed inset-0 z-50 flex lg:hidden">
          <div className="h-full w-72 max-w-[85vw] shadow-2xl">{sidebarContent}</div>
          <div
            className="flex-1 bg-plum/60 backdrop-blur-sm"
            onClick={() => setMobileOpen(false)}
            aria-hidden="true"
          />
        </div>
      )}

      {/* Main content */}
      <main className="min-w-0 flex-1 lg:pl-64">
        <div className="mx-auto max-w-6xl px-3.5 py-5 sm:px-6 sm:py-7 lg:px-9">{children}</div>
      </main>
    </div>
  );
}
