import { useRef, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MapPin, Plus } from "lucide-react";
import { orderApi, userApi } from "@/api/endpoints";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorState, PageHeader, PageSpinner } from "@/components/ui/feedback";
import { Field, Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { cartKey, useCart } from "@/features/cart/useCart";
import { PaymentPanel } from "@/features/orders/PaymentPanel";
import { cn } from "@/utils/cn";
import { formatPrice } from "@/utils/format";
import type { Order } from "@/types";

const emptyAddress = { address_line: "", city: "", state: "", country: "India", postal_code: "" };

export default function CheckoutPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const toast = useToast();
  const cart = useCart();
  const addresses = useQuery({ queryKey: ["addresses"], queryFn: userApi.addresses });

  const [selected, setSelected] = useState<number | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyAddress);
  const [order, setOrder] = useState<Order | null>(null);
  // One idempotency key per checkout attempt so a double-click can't create two orders.
  const idempotencyKey = useRef(crypto.randomUUID());

  const addAddress = useMutation({
    mutationFn: () => userApi.addAddress({ ...form, is_default: (addresses.data?.length ?? 0) === 0 }),
    onSuccess: (a) => {
      qc.invalidateQueries({ queryKey: ["addresses"] });
      setSelected(a.id);
      setShowForm(false);
      setForm(emptyAddress);
      toast.success("Address saved");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const place = useMutation({
    mutationFn: () => orderApi.create(addressId!, idempotencyKey.current),
    onSuccess: (o) => {
      setOrder(o);
      qc.invalidateQueries({ queryKey: cartKey });
      qc.invalidateQueries({ queryKey: ["orders"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (cart.isLoading || addresses.isLoading) return <PageSpinner />;
  if (cart.isError) return <ErrorState error={cart.error} onRetry={() => cart.refetch()} />;
  if (addresses.isError) return <ErrorState error={addresses.error} onRetry={() => addresses.refetch()} />;

  const defaultId = addresses.data?.find((a) => a.is_default)?.id ?? addresses.data?.[0]?.id ?? null;
  const addressId = selected ?? defaultId;
  const items = cart.data?.items ?? [];

  if (order) {
    return (
      <div className="mx-auto max-w-xl space-y-4">
        <PageHeader title="Complete your payment" description="Your items are reserved while the payment is pending." />
        <PaymentPanel order={order} onDone={(o) => navigate(`/orders/${o.id}`, { replace: true })} />
        <Button variant="link" asChild>
          <Link to={`/orders/${order.id}`}>Pay later from my orders</Link>
        </Button>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <EmptyState
        title="Nothing to check out"
        description="Your cart is empty."
        action={
          <Button asChild>
            <Link to="/products">Browse products</Link>
          </Button>
        }
      />
    );
  }

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const submitAddress = (e: FormEvent) => {
    e.preventDefault();
    addAddress.mutate();
  };

  return (
    <div>
      <PageHeader title="Checkout" />
      <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
        <div className="space-y-4">
          <h2 className="font-semibold">Shipping address</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            {addresses.data?.map((a) => (
              <button
                key={a.id}
                type="button"
                onClick={() => setSelected(a.id)}
                className={cn(
                  "rounded-lg border bg-card p-4 text-left transition-colors",
                  a.id === addressId ? "border-primary ring-2 ring-primary/30" : "hover:border-primary/50",
                )}
              >
                <MapPin className="mb-2 h-4 w-4 text-primary" />
                <p className="text-sm font-medium">{a.address_line}</p>
                <p className="text-sm text-muted-foreground">
                  {a.city}, {a.state} {a.postal_code}
                </p>
                <p className="text-sm text-muted-foreground">{a.country}</p>
              </button>
            ))}
            {!showForm && (
              <button
                type="button"
                onClick={() => setShowForm(true)}
                className="flex min-h-24 items-center justify-center gap-2 rounded-lg border border-dashed text-sm text-muted-foreground hover:border-primary hover:text-primary"
              >
                <Plus className="h-4 w-4" /> Add new address
              </button>
            )}
          </div>

          {showForm && (
            <Card className="p-5">
              <form onSubmit={submitAddress} className="grid gap-4 sm:grid-cols-2">
                <Field label="Address" htmlFor="line" className="sm:col-span-2">
                  <Input id="line" required value={form.address_line} onChange={set("address_line")} />
                </Field>
                <Field label="City" htmlFor="city">
                  <Input id="city" required value={form.city} onChange={set("city")} />
                </Field>
                <Field label="State" htmlFor="state">
                  <Input id="state" required value={form.state} onChange={set("state")} />
                </Field>
                <Field label="Postal code" htmlFor="pin">
                  <Input id="pin" required value={form.postal_code} onChange={set("postal_code")} />
                </Field>
                <Field label="Country" htmlFor="country">
                  <Input id="country" required value={form.country} onChange={set("country")} />
                </Field>
                <div className="flex gap-2 sm:col-span-2">
                  <Button type="submit" loading={addAddress.isPending}>
                    Save address
                  </Button>
                  <Button type="button" variant="ghost" onClick={() => setShowForm(false)}>
                    Cancel
                  </Button>
                </div>
              </form>
            </Card>
          )}
        </div>

        <Card className="h-fit space-y-4 p-5 lg:sticky lg:top-24">
          <h2 className="font-semibold">Order summary</h2>
          <ul className="space-y-2 text-sm">
            {items.map((i) => (
              <li key={i.id} className="flex justify-between gap-3">
                <span className="line-clamp-1">
                  {i.product_name} × {i.quantity}
                </span>
                <span>{formatPrice(i.subtotal)}</span>
              </li>
            ))}
          </ul>
          <div className="flex justify-between border-t pt-4 text-lg font-bold">
            <span>Total</span>
            <span>{formatPrice(cart.data?.total)}</span>
          </div>
          <Button className="w-full" size="lg" disabled={!addressId} loading={place.isPending} onClick={() => place.mutate()}>
            Place order
          </Button>
          {!addressId && <p className="text-xs text-muted-foreground">Add a shipping address to continue.</p>}
        </Card>
      </div>
    </div>
  );
}
