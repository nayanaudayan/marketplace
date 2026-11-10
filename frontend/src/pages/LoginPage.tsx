import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { ADMIN_PORTAL_URL, IS_ADMIN_APP } from "@/config";
import { useAuth, WrongPortalError } from "@/features/auth/AuthContext";
import { homeFor } from "@/features/auth/homeFor";

export default function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const toast = useToast();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const from = (location.state as { from?: string } | null)?.from;

  if (user) return <Navigate to={from ?? homeFor(user.role)} replace />;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      // The admin app only admits administrators; the storefront never signs admins in.
      const u = await login(email.trim(), password, IS_ADMIN_APP ? ["admin"] : ["customer", "seller"]);
      toast.success(`Welcome back, ${u.name}`);
      navigate(from ?? homeFor(u.role), { replace: true });
    } catch (err) {
      if (err instanceof WrongPortalError) {
        toast.error(
          IS_ADMIN_APP
            ? "This portal is for administrators only. Customers and sellers sign in on the main site."
            : `Administrators sign in at the admin portal${ADMIN_PORTAL_URL ? `: ${ADMIN_PORTAL_URL}` : "."}`,
        );
      } else {
        toast.error((err as Error).message);
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-md py-8">
      <Card>
        <CardHeader>
          <CardTitle className="text-2xl">{IS_ADMIN_APP ? "Admin sign in" : "Log in"}</CardTitle>
          <CardDescription>
            {IS_ADMIN_APP ? "Restricted to marketplace administrators." : "Access your cart, orders and seller tools."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className="space-y-4">
            <Field label="Email" htmlFor="email">
              <Input id="email" type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
            </Field>
            <Field label="Password" htmlFor="password">
              <Input
                id="password"
                type="password"
                required
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </Field>
            <Button type="submit" className="w-full" loading={busy}>
              Log in
            </Button>
          </form>
          {!IS_ADMIN_APP && (
            <p className="mt-4 text-center text-sm text-muted-foreground">
              New here?{" "}
              <Link to="/register" className="font-medium text-primary hover:underline">
                Create an account
              </Link>
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
