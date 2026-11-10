import { Link } from "react-router-dom";
import { Minus, Plus, ShoppingBag, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorState, PageHeader, PageSpinner } from "@/components/ui/feedback";
import { useCart, useCartMutations } from "@/features/cart/useCart";
import { ProductImage } from "@/features/products/ProductImage";
import { formatPrice } from "@/utils/format";

export default function CartPage() {
  const cart = useCart();
  const { update, remove } = useCartMutations();

  if (cart.isLoading) return <PageSpinner />;
  if (cart.isError) return <ErrorState error={cart.error} onRetry={() => cart.refetch()} />;

  const items = cart.data?.items ?? [];
  if (items.length === 0) {
    return (
      <EmptyState
        title="Your cart is empty"
        description="Find something you like with AI search or by browsing the catalogue."
        action={
          <Button asChild>
            <Link to="/products">
              <ShoppingBag className="h-4 w-4" /> Start shopping
            </Link>
          </Button>
        }
      />
    );
  }

  const hasIssue = items.some((i) => i.available_quantity < i.quantity);
  const busy = update.isPending || remove.isPending;

  return (
    <div>
      <PageHeader title="Shopping cart" />
      <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
        <div className="space-y-3">
          {items.map((i) => {
            const short = i.available_quantity < i.quantity;
            return (
              <Card key={i.id} className="flex gap-4 p-4">
                <ProductImage src={i.image_url} alt={i.product_name} className="h-24 w-24 shrink-0 rounded-md" />
                <div className="flex min-w-0 flex-1 flex-col gap-1">
                  <Link to={`/products/${i.product_id}`} className="line-clamp-2 font-medium hover:text-primary">
                    {i.product_name}
                  </Link>
                  <p className="text-xs text-muted-foreground">
                    {i.variant_name} · Sold by {i.seller_name}
                  </p>
                  {short && (
                    <p className="text-xs font-medium text-destructive">
                      {i.available_quantity === 0 ? "Out of stock" : `Only ${i.available_quantity} left`} — adjust the quantity.
                    </p>
                  )}
                  <div className="mt-auto flex flex-wrap items-center justify-between gap-2 pt-2">
                    <div className="flex items-center gap-1 rounded-md border">
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label="Decrease quantity"
                        disabled={busy || i.quantity <= 1}
                        onClick={() => update.mutate({ id: i.id, quantity: i.quantity - 1 })}
                      >
                        <Minus className="h-4 w-4" />
                      </Button>
                      <span className="w-8 text-center text-sm font-medium">{i.quantity}</span>
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label="Increase quantity"
                        disabled={busy || i.quantity >= i.available_quantity}
                        onClick={() => update.mutate({ id: i.id, quantity: i.quantity + 1 })}
                      >
                        <Plus className="h-4 w-4" />
                      </Button>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="text-right">
                        <p className="font-bold">{formatPrice(i.subtotal)}</p>
                        <p className="text-xs text-muted-foreground">{formatPrice(i.unit_price)} each</p>
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label="Remove item"
                        disabled={busy}
                        onClick={() => remove.mutate(i.id)}
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>

        <Card className="h-fit space-y-4 p-5 lg:sticky lg:top-24">
          <h2 className="font-semibold">Order summary</h2>
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Items ({items.reduce((n, i) => n + i.quantity, 0)})</span>
            <span>{formatPrice(cart.data?.total)}</span>
          </div>
          <div className="flex justify-between border-t pt-4 text-lg font-bold">
            <span>Total</span>
            <span>{formatPrice(cart.data?.total)}</span>
          </div>
          <Button className="w-full" size="lg" asChild={!hasIssue} disabled={hasIssue}>
            {hasIssue ? <span>Fix stock issues to continue</span> : <Link to="/checkout">Proceed to checkout</Link>}
          </Button>
          <p className="text-xs text-muted-foreground">Prices and stock are re-verified when you place the order.</p>
        </Card>
      </div>
    </div>
  );
}
