import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Heart, ShoppingCart } from "lucide-react";
import { productApi } from "@/api/endpoints";
import { Rating } from "@/components/Rating";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ErrorState, PageSpinner } from "@/components/ui/feedback";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/features/auth/AuthContext";
import { useCartMutations } from "@/features/cart/useCart";
import { ProductImage } from "@/features/products/ProductImage";
import { Reviews } from "@/features/products/Reviews";
import { useToggleWishlist, useWishlist } from "@/features/wishlist/useWishlist";
import { cn } from "@/utils/cn";
import { formatPrice } from "@/utils/format";

export default function ProductDetailPage() {
  const id = Number(useParams().id);
  const navigate = useNavigate();
  const { user } = useAuth();
  const cart = useCartMutations();
  const wishlist = useWishlist();
  const toggleWishlist = useToggleWishlist();

  const product = useQuery({ queryKey: ["product", id], queryFn: () => productApi.get(id), enabled: Number.isFinite(id) });

  const [variantId, setVariantId] = useState<number | null>(null);
  const [imageId, setImageId] = useState<number | null>(null);
  const [qty, setQty] = useState(1);

  const p = product.data;
  useEffect(() => {
    if (p && variantId === null && p.variants.length) setVariantId(p.variants[0].id);
  }, [p, variantId]);

  const variant = useMemo(() => p?.variants.find((v) => v.id === variantId), [p, variantId]);
  const mainImage = p?.images.find((i) => i.id === imageId) ?? p?.images.find((i) => i.is_primary) ?? p?.images[0];
  const inWishlist = !!wishlist.data?.some((w) => w.id === id);

  if (product.isLoading) return <PageSpinner />;
  if (product.isError) return <ErrorState error={product.error} onRetry={() => product.refetch()} />;
  if (!p) return null;

  const addToCart = (listingId: number) => {
    if (!user) return navigate("/login", { state: { from: `/products/${id}` } });
    cart.add.mutate({ listingId, quantity: qty });
  };

  const specs = Object.entries(p.specifications ?? {});
  const listings = [...(variant?.listings ?? [])].sort((a, b) => a.selling_price - b.selling_price);

  return (
    <div className="space-y-10">
      <div className="grid gap-8 lg:grid-cols-2">
        <div className="space-y-3">
          <ProductImage
            src={mainImage?.image_url ?? p.primary_image_url}
            alt={p.name}
            className="aspect-square w-full rounded-lg border"
          />
          {p.images.length > 1 && (
            <div className="flex gap-2 overflow-x-auto">
              {p.images.map((img) => (
                <button
                  key={img.id}
                  onClick={() => setImageId(img.id)}
                  className={cn("shrink-0 rounded-md border-2", img.id === mainImage?.id ? "border-primary" : "border-transparent")}
                >
                  <ProductImage src={img.image_url} alt="" className="h-16 w-16 rounded" />
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="space-y-5">
          <div>
            <Link to={`/products?category_id=${p.category_id}`} className="text-sm text-primary hover:underline">
              {p.category_name}
            </Link>
            <h1 className="mt-1 text-3xl font-bold tracking-tight">{p.name}</h1>
            <div className="mt-2 flex flex-wrap items-center gap-3">
              {p.brand && <Badge variant="secondary">{p.brand}</Badge>}
              <Rating value={p.avg_rating} count={p.review_count} />
              {p.in_stock ? <Badge variant="success">In stock</Badge> : <Badge variant="destructive">Out of stock</Badge>}
            </div>
          </div>

          <p className="whitespace-pre-line text-muted-foreground">{p.description}</p>

          {p.variants.length > 0 && (
            <div className="space-y-2">
              <p className="text-sm font-medium">Variant</p>
              <div className="flex flex-wrap gap-2">
                {p.variants.map((v) => (
                  <button
                    key={v.id}
                    onClick={() => setVariantId(v.id)}
                    className={cn(
                      "rounded-md border px-3 py-2 text-sm transition-colors",
                      v.id === variantId ? "border-primary bg-accent text-accent-foreground" : "hover:border-primary/50",
                    )}
                  >
                    {v.variant_name}
                  </button>
                ))}
              </div>
              {variant && Object.keys(variant.attributes ?? {}).length > 0 && (
                <p className="text-xs text-muted-foreground">
                  {Object.entries(variant.attributes)
                    .map(([k, v]) => `${k.replace(/_/g, " ")}: ${String(v)}`)
                    .join(" · ")}
                </p>
              )}
            </div>
          )}

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium">Seller offers</p>
              {user?.role !== "seller" && user?.role !== "admin" && (
                <div className="flex items-center gap-2 text-sm">
                  <label htmlFor="qty">Qty</label>
                  <Input
                    id="qty"
                    type="number"
                    min={1}
                    value={qty}
                    onChange={(e) => setQty(Math.max(1, Number(e.target.value) || 1))}
                    className="h-8 w-20"
                  />
                </div>
              )}
            </div>
            {listings.length === 0 && <p className="text-sm text-muted-foreground">No active offers for this variant.</p>}
            {listings.map((l, i) => (
              <Card key={l.id} className="flex flex-wrap items-center justify-between gap-3 p-3">
                <div>
                  <p className="font-medium">{l.seller_name}</p>
                  <p className="text-xs text-muted-foreground">
                    {l.available_quantity > 0 ? `${l.available_quantity} available` : "Out of stock"}
                    {i === 0 && l.available_quantity > 0 && listings.length > 1 && " · Lowest price"}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xl font-bold">{formatPrice(l.selling_price)}</span>
                  {user?.role !== "seller" && user?.role !== "admin" && (
                    <Button
                      size="sm"
                      disabled={l.available_quantity < 1 || qty > l.available_quantity}
                      loading={cart.add.isPending && cart.add.variables?.listingId === l.id}
                      onClick={() => addToCart(l.id)}
                    >
                      <ShoppingCart className="h-4 w-4" /> Add to cart
                    </Button>
                  )}
                </div>
              </Card>
            ))}
          </div>

          {user?.role === "customer" && (
            <Button
              variant="outline"
              onClick={() => toggleWishlist.mutate({ productId: id, inWishlist })}
              loading={toggleWishlist.isPending}
            >
              <Heart className={cn("h-4 w-4", inWishlist && "fill-destructive text-destructive")} />
              {inWishlist ? "Remove from wishlist" : "Save to wishlist"}
            </Button>
          )}
        </div>
      </div>

      {specs.length > 0 && (
        <section>
          <h2 className="mb-3 text-xl font-semibold">Specifications</h2>
          <Card className="overflow-hidden">
            <dl className="divide-y">
              {specs.map(([k, v]) => (
                <div key={k} className="grid grid-cols-3 gap-4 px-4 py-2.5 text-sm">
                  <dt className="capitalize text-muted-foreground">{k.replace(/_/g, " ")}</dt>
                  <dd className="col-span-2">{typeof v === "object" ? JSON.stringify(v) : String(v)}</dd>
                </div>
              ))}
            </dl>
          </Card>
        </section>
      )}

      <Reviews productId={id} />
    </div>
  );
}
