import { Link } from "react-router-dom";
import { Heart } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Rating } from "@/components/Rating";
import { useAuth } from "@/features/auth/AuthContext";
import { useToggleWishlist, useWishlist } from "@/features/wishlist/useWishlist";
import { cn } from "@/utils/cn";
import { formatPrice } from "@/utils/format";
import type { AIProduct, ProductCard } from "@/types";
import { ProductImage } from "./ProductImage";

function WishlistButton({ productId }: { productId: number }) {
  const { user } = useAuth();
  const { data } = useWishlist();
  const toggle = useToggleWishlist();
  if (user?.role !== "customer") return null;
  const inWishlist = !!data?.some((p) => p.id === productId);
  return (
    <button
      type="button"
      aria-label={inWishlist ? "Remove from wishlist" : "Add to wishlist"}
      disabled={toggle.isPending}
      onClick={() => toggle.mutate({ productId, inWishlist })}
      className="absolute right-2 top-2 rounded-full bg-card/90 p-2 shadow hover:bg-card"
    >
      <Heart className={cn("h-4 w-4", inWishlist ? "fill-destructive text-destructive" : "text-muted-foreground")} />
    </button>
  );
}

export function ProductCardView({ product }: { product: ProductCard | AIProduct }) {
  const ai = "match_reason" in product ? product : null;
  const price = ai ? ai.price : product.min_price;
  const inStock = ai ? ai.stock > 0 : product.in_stock;

  return (
    <Card className="group relative flex flex-col overflow-hidden transition-shadow hover:shadow-md">
      <Link to={`/products/${product.id}`} className="block">
        <ProductImage
          src={product.primary_image_url}
          alt={product.name}
          className="aspect-[4/3] w-full transition-transform group-hover:scale-[1.02]"
        />
      </Link>
      <WishlistButton productId={product.id} />
      <div className="flex flex-1 flex-col gap-2 p-4">
        <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
          <span>{product.brand ?? product.category_name}</span>
          <Rating value={product.avg_rating} count={product.review_count} className="text-xs" />
        </div>
        <Link to={`/products/${product.id}`} className="line-clamp-2 font-medium leading-snug hover:text-primary">
          {product.name}
        </Link>
        {ai && (
          <p className="rounded-md bg-accent px-2.5 py-1.5 text-xs text-accent-foreground">{ai.match_reason}</p>
        )}
        <div className="mt-auto flex items-end justify-between pt-2">
          <div>
            {!ai && product.min_price != null && <span className="text-xs text-muted-foreground">From </span>}
            <span className="text-lg font-bold">{formatPrice(price)}</span>
            {ai && <p className="text-xs text-muted-foreground">Sold by {ai.seller_name}</p>}
          </div>
          {inStock ? (
            <Badge variant="success">{ai ? `${ai.stock} in stock` : "In stock"}</Badge>
          ) : (
            <Badge variant="destructive">Out of stock</Badge>
          )}
        </div>
      </div>
    </Card>
  );
}

export function ProductGrid({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">{children}</div>;
}
