import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive } from "lucide-react";
import { productApi, sellerApi } from "@/api/endpoints";
import { StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorState, PageSpinner } from "@/components/ui/feedback";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { ProductImage } from "@/features/products/ProductImage";
import type { Listing } from "@/types";

function ListingEditor({ listing, label }: { listing: Listing; label: string }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [price, setPrice] = useState(String(listing.selling_price));
  const [qty, setQty] = useState(String(listing.available_quantity));

  const dirty = Number(price) !== listing.selling_price || Number(qty) !== listing.available_quantity;

  const save = useMutation({
    mutationFn: () => sellerApi.updateListing(listing.id, { selling_price: Number(price), available_quantity: Number(qty) }),
    onSuccess: () => {
      toast.success("Listing updated");
      qc.invalidateQueries({ queryKey: ["seller", "products"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-md bg-muted/50 p-3">
      <span className="min-w-32 flex-1 text-sm font-medium">{label}</span>
      <label className="flex items-center gap-2 text-xs text-muted-foreground">
        Price ₹
        <Input type="number" min={1} step="0.01" className="h-8 w-28" value={price} onChange={(e) => setPrice(e.target.value)} />
      </label>
      <label className="flex items-center gap-2 text-xs text-muted-foreground">
        Stock
        <Input type="number" min={0} className="h-8 w-24" value={qty} onChange={(e) => setQty(e.target.value)} />
      </label>
      <Button size="sm" disabled={!dirty || !(Number(price) > 0) || Number(qty) < 0} loading={save.isPending} onClick={() => save.mutate()}>
        Save
      </Button>
    </div>
  );
}

export function SellerProducts({ sellerId }: { sellerId: number }) {
  const qc = useQueryClient();
  const toast = useToast();
  const products = useQuery({ queryKey: ["seller", "products"], queryFn: sellerApi.products });

  const archive = useMutation({
    mutationFn: (id: number) => productApi.remove(id),
    onSuccess: () => {
      toast.success("Product archived");
      qc.invalidateQueries({ queryKey: ["seller", "products"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (products.isLoading) return <PageSpinner />;
  if (products.isError) return <ErrorState error={products.error} onRetry={() => products.refetch()} />;
  if (!products.data?.length)
    return <EmptyState title="No products yet" description="Create your first product to start selling." />;

  return (
    <div className="space-y-4">
      {products.data.map((p) => (
        <Card key={p.id} className="space-y-3 p-4">
          <div className="flex gap-4">
            <ProductImage src={p.primary_image_url} alt={p.name} className="h-16 w-16 shrink-0 rounded-md" />
            <div className="min-w-0 flex-1">
              <Link to={`/products/${p.id}`} className="font-semibold hover:text-primary">
                {p.name}
              </Link>
              <p className="text-xs text-muted-foreground">
                {p.category_name}
                {p.brand ? ` · ${p.brand}` : ""}
              </p>
            </div>
            <div className="flex items-start gap-2">
              <StatusBadge status={p.status} />
              {p.status !== "archived" && (
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Archive product"
                  onClick={() => confirm(`Archive “${p.name}”?`) && archive.mutate(p.id)}
                >
                  <Archive className="h-4 w-4" />
                </Button>
              )}
            </div>
          </div>
          <div className="space-y-2">
            {p.variants.flatMap((v) =>
              v.listings
                .filter((l) => l.seller_id === sellerId)
                .map((l) => <ListingEditor key={l.id} listing={l} label={v.variant_name} />),
            )}
          </div>
        </Card>
      ))}
    </div>
  );
}
