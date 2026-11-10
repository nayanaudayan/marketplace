import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/features/auth/AuthContext";
import { homeFor } from "@/features/auth/homeFor";
import { cn } from "@/utils/cn";

export default function RegisterPage() {
  const { user, register } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const [role, setRole] = useState<"customer" | "seller">("customer");
  const [form, setForm] = useState({ name: "", email: "", phone: "", password: "" });
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={homeFor(user.role)} replace />;

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const u = await register({
        name: form.name.trim(),
        email: form.email.trim(),
        password: form.password,
        phone: form.phone.trim() || undefined,
        role,
      });
      toast.success("Account created");
      navigate(homeFor(u.role), { replace: true });
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-md py-8">
      <Card>
        <CardHeader>
          <CardTitle className="text-2xl">Create your account</CardTitle>
          <CardDescription>Shop smarter, or start selling to customers.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="mb-4 grid grid-cols-2 gap-2 rounded-lg bg-muted p-1" role="radiogroup" aria-label="Account type">
            {(["customer", "seller"] as const).map((r) => (
              <button
                key={r}
                type="button"
                role="radio"
                aria-checked={role === r}
                onClick={() => setRole(r)}
                className={cn(
                  "rounded-md py-2 text-sm font-medium capitalize transition-colors",
                  role === r ? "bg-card shadow-sm" : "text-muted-foreground",
                )}
              >
                {r === "customer" ? "I want to buy" : "I want to sell"}
              </button>
            ))}
          </div>
          <form onSubmit={submit} className="space-y-4">
            <Field label="Full name" htmlFor="name">
              <Input id="name" required minLength={2} autoComplete="name" value={form.name} onChange={set("name")} />
            </Field>
            <Field label="Email" htmlFor="email">
              <Input id="email" type="email" required autoComplete="email" value={form.email} onChange={set("email")} />
            </Field>
            <Field label="Phone (optional)" htmlFor="phone">
              <Input id="phone" type="tel" autoComplete="tel" value={form.phone} onChange={set("phone")} />
            </Field>
            <Field label="Password" htmlFor="password" hint="At least 8 characters.">
              <Input
                id="password"
                type="password"
                required
                minLength={8}
                autoComplete="new-password"
                value={form.password}
                onChange={set("password")}
              />
            </Field>
            <Button type="submit" className="w-full" loading={busy}>
              Create account
            </Button>
          </form>
          <p className="mt-4 text-center text-sm text-muted-foreground">
            Already registered?{" "}
            <Link to="/login" className="font-medium text-primary hover:underline">
              Log in
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
