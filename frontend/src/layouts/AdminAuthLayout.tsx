import { useEffect } from "react";
import { Outlet } from "react-router-dom";
import { ShieldCheck } from "lucide-react";

/** Bare shell for the admin sign-in page: no sidebar for visitors who aren't signed in. */
export default function AdminAuthLayout() {
  useEffect(() => {
    document.title = "Marketplace Admin";
  }, []);
  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-4 py-10">
      <div className="mb-2 flex items-center gap-2.5">
        <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <ShieldCheck className="h-5 w-5" />
        </span>
        <span className="text-xl font-bold">Marketplace Admin</span>
      </div>
      <div className="w-full">
        <Outlet />
      </div>
    </div>
  );
}
