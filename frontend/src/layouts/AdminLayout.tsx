import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { LayoutDashboard, LogOut, Menu, ShieldCheck, ShoppingBag, Store, Tags, X, type LucideIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/features/auth/AuthContext";
import { useAdminStats } from "@/features/admin/StatsTiles";
import { cn } from "@/utils/cn";

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  end?: boolean;
  badge?: number;
}

function Brand() {
  return (
    <div className="flex items-center gap-2.5">
      <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
        <ShieldCheck className="h-5 w-5" />
      </span>
      <div className="leading-tight">
        <p className="font-bold">Marketplace</p>
        <p className="text-xs text-muted-foreground">Admin console</p>
      </div>
    </div>
  );
}

export default function AdminLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const stats = useAdminStats();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    document.title = "Marketplace Admin";
  }, []);
  // close the mobile drawer after navigating
  useEffect(() => setOpen(false), [location.pathname]);

  const items: NavItem[] = [
    { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
    { to: "/sellers", label: "Sellers", icon: Store, badge: stats.data?.pending_sellers },
    { to: "/orders", label: "Orders", icon: ShoppingBag },
    { to: "/categories", label: "Categories", icon: Tags },
  ];

  const signOut = async () => {
    await logout();
    navigate("/login");
  };

  const sidebar = (
    <div className="flex h-full flex-col">
      <div className="flex h-16 items-center justify-between border-b px-4">
        <Brand />
        <Button variant="ghost" size="icon" className="md:hidden" aria-label="Close menu" onClick={() => setOpen(false)}>
          <X className="h-5 w-5" />
        </Button>
      </div>

      <nav aria-label="Admin sections" className="flex-1 space-y-1 overflow-y-auto p-3">
        {items.map(({ to, label, icon: Icon, end, badge }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors",
                isActive ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-accent hover:text-foreground",
              )
            }
          >
            <Icon className="h-4 w-4 shrink-0" />
            <span className="flex-1">{label}</span>
            {!!badge && (
              <span
                aria-label={`${badge} pending`}
                className="flex h-5 min-w-5 items-center justify-center rounded-full bg-amber-500 px-1.5 text-[11px] font-semibold text-white"
              >
                {badge}
              </span>
            )}
          </NavLink>
        ))}
      </nav>

      {user && (
        <div className="border-t p-3">
          <div className="mb-2 px-2 leading-tight">
            <p className="truncate text-sm font-medium">{user.name}</p>
            <p className="truncate text-xs text-muted-foreground">{user.email}</p>
          </div>
          <Button variant="ghost" size="sm" className="w-full justify-start" aria-label="Log out" onClick={signOut}>
            <LogOut className="h-4 w-4" /> Log out
          </Button>
        </div>
      )}
    </div>
  );

  return (
    <div className="min-h-screen md:flex">
      {/* Desktop: fixed sidebar. Mobile: slide-in drawer over a dimmed backdrop. */}
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 border-r bg-card md:block">{sidebar}</aside>
      {open && <div className="fixed inset-0 z-40 bg-black/40 md:hidden" onClick={() => setOpen(false)} aria-hidden />}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 w-64 border-r bg-card transition-transform md:hidden",
          open ? "translate-x-0" : "-translate-x-full",
        )}
        aria-hidden={!open}
      >
        {open && sidebar}
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b bg-card/90 px-4 backdrop-blur md:hidden">
          <Button variant="ghost" size="icon" aria-label="Open menu" onClick={() => setOpen(true)}>
            <Menu className="h-5 w-5" />
          </Button>
          <Brand />
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 p-4 md:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
