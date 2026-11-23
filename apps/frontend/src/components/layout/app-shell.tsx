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
              <div className="grid grid-cols-2 gap-3">
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
    <div className="flex h-full flex-col justify-between bg-plum px-4 py-6 text-white">
      <div>
        <Link href="/" className="flex items-center gap-2.5 px-2 pb-6">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-brand">
            <Wrench className="h-4 w-4" />
          </div>
          <div>
            <div className="text-base font-extrabold tracking-tight text-white">ArtisanOS</div>
            <div className="text-[11px] font-medium text-plum-soft">Artisan Business OS</div>
          </div>
        </Link>

        <div className="mb-6 rounded-2xl border border-white/10 bg-plum-surface p-3">
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

        <nav className="space-y-1.5" aria-label="Main navigation">
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
                <span className="flex items-center gap-3">
                  <Icon className="h-4 w-4" />
                  {item.label}
                </span>
                {item.href === "/notifications" && unreadNotifications > 0 && (
                  <span className="inline-flex min-w-5 items-center justify-center rounded-full bg-brand-500 px-1.5 py-0.5 text-[10px] font-extrabold text-white">
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
              <ShieldAlert className="h-4 w-4" />
              Platform Admin
            </Link>
          )}
        </nav>
      </div>

      <div className="border-t border-white/10 pt-4">
        <div className="mb-3 rounded-xl bg-white/[0.04] px-3 py-2.5">
          <div className="truncate text-sm font-semibold text-white">{user.full_name}</div>
          <div className="truncate text-xs text-plum-soft">{user.email}</div>
          <div className="mt-1 text-[10px] font-bold uppercase tracking-wider text-brand-300">
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
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-line bg-paper/90 px-4 py-3 backdrop-blur-md lg:hidden">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-brand">
            <Wrench className="h-4 w-4" />
          </div>
          <div>
            <div className="text-sm font-bold text-plum">{activeOrganization.name}</div>
            <div className="text-[11px] font-medium text-ink-faint">ArtisanOS</div>
          </div>
        </div>
        <button
          type="button"
          aria-label="Toggle navigation menu"
          onClick={() => setMobileOpen(!mobileOpen)}
          className="rounded-full border border-line bg-white p-2 text-ink hover:bg-surface-blush"
        >
          {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </header>

      {mobileOpen && (
        <div className="fixed inset-0 z-40 flex lg:hidden">
          <div className="w-72 max-w-[85vw]">{sidebarContent}</div>
          <div
            className="flex-1 bg-plum/50 backdrop-blur-xs"
            onClick={() => setMobileOpen(false)}
            aria-hidden="true"
          />
        </div>
      )}

      {/* Main content */}
      <main className="flex-1 lg:pl-64">
        <div className="mx-auto max-w-6xl px-4 py-7 sm:px-6 lg:px-9">{children}</div>
      </main>
    </div>
  );
}
