import { useState } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { Heart, LogOut, Menu, Package, ShoppingCart, Sparkles, Store, X, LayoutDashboard, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/features/auth/AuthContext";
import { useCart } from "@/features/cart/useCart";
import { cn } from "@/utils/cn";

function CartLink() {
  const { data } = useCart();
  const count = data?.items.reduce((n, i) => n + i.quantity, 0) ?? 0;
  return (
    <Link to="/cart" className="relative rounded-md p-2 hover:bg-accent" aria-label="Cart">
      <ShoppingCart className="h-5 w-5" />
      {count > 0 && (
        <span className="absolute -right-0.5 -top-0.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-primary px-1 text-[11px] font-semibold text-primary-foreground">
          {count}
        </span>
      )}
    </Link>
  );
}

export default function MainLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);

  const navLink = ({ isActive }: { isActive: boolean }) =>
    cn(
      "rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-accent",
      isActive ? "text-primary" : "text-muted-foreground",
    );

  const links = (
    <>
      <NavLink to="/products" className={navLink} onClick={() => setOpen(false)}>
        Shop
      </NavLink>
      <NavLink to="/search" className={navLink} onClick={() => setOpen(false)}>
        <span className="inline-flex items-center gap-1.5">
          <Sparkles className="h-4 w-4" /> AI Search
        </span>
      </NavLink>
      {user?.role === "customer" && (
        <>
          <NavLink to="/orders" className={navLink} onClick={() => setOpen(false)}>
            Orders
          </NavLink>
          <NavLink to="/wishlist" className={navLink} onClick={() => setOpen(false)}>
            Wishlist
          </NavLink>
        </>
      )}
      {user?.role === "seller" && (
        <NavLink to="/seller" className={navLink} onClick={() => setOpen(false)}>
          Seller dashboard
        </NavLink>
      )}
    </>
  );

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-40 border-b bg-card/90 backdrop-blur">
        <div className="container flex h-16 items-center gap-4">
          <Link to="/" className="flex items-center gap-2 text-lg font-bold">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <Store className="h-4 w-4" />
            </span>
            <span className="hidden sm:inline">AI Marketplace</span>
          </Link>

          <nav className="ml-4 hidden items-center gap-1 md:flex">{links}</nav>

          <div className="ml-auto flex items-center gap-1">
            {user?.role === "customer" && (
              <>
                <Link to="/wishlist" className="hidden rounded-md p-2 hover:bg-accent sm:block" aria-label="Wishlist">
                  <Heart className="h-5 w-5" />
                </Link>
                <CartLink />
              </>
            )}
            {user ? (
              <div className="ml-2 flex items-center gap-2">
                <div className="hidden text-right leading-tight lg:block">
                  <p className="text-sm font-medium">{user.name}</p>
                  <p className="text-xs capitalize text-muted-foreground">{user.role}</p>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Log out"
                  onClick={async () => {
                    await logout();
                    navigate("/");
                  }}
                >
                  <LogOut className="h-5 w-5" />
                </Button>
              </div>
            ) : (
              <div className="ml-2 flex items-center gap-2">
                <Button variant="ghost" size="sm" asChild>
                  <Link to="/login">Log in</Link>
                </Button>
                <Button size="sm" asChild>
                  <Link to="/register">Sign up</Link>
                </Button>
              </div>
            )}
            <Button variant="ghost" size="icon" className="md:hidden" onClick={() => setOpen((o) => !o)} aria-label="Menu">
              {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </Button>
          </div>
        </div>
        {open && <nav className="container flex flex-col gap-1 border-t py-3 md:hidden">{links}</nav>}
      </header>

      <main className="container flex-1 py-6">
        <Outlet />
      </main>

      <footer className="border-t bg-card">
        <div className="container flex flex-wrap items-center justify-between gap-3 py-6 text-sm text-muted-foreground">
          <p>© {new Date().getFullYear()} AI Marketplace. Natural-language product discovery.</p>
          <div className="flex items-center gap-4">
            <span className="inline-flex items-center gap-1">
              <Package className="h-4 w-4" /> Multi-vendor
            </span>
            <span className="inline-flex items-center gap-1">
              <ShieldCheck className="h-4 w-4" /> Verified price &amp; stock
            </span>
            <span className="inline-flex items-center gap-1">
              <LayoutDashboard className="h-4 w-4" /> Sellers welcome
            </span>
          </div>
        </div>
      </footer>
    </div>
  );
}
