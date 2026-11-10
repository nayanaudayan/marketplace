import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorState, PageHeader, PageSpinner } from "@/components/ui/feedback";
import { ProductCardView, ProductGrid } from "@/features/products/ProductCardView";
import { useWishlist } from "@/features/wishlist/useWishlist";

export default function WishlistPage() {
  const wishlist = useWishlist();

  if (wishlist.isLoading) return <PageSpinner />;
  if (wishlist.isError) return <ErrorState error={wishlist.error} onRetry={() => wishlist.refetch()} />;

  return (
    <div>
      <PageHeader title="My wishlist" />
      {wishlist.data?.length === 0 ? (
        <EmptyState
          title="Your wishlist is empty"
          description="Tap the heart on any product to save it for later."
          action={
            <Button asChild>
              <Link to="/products">Browse products</Link>
            </Button>
          }
        />
      ) : (
        <ProductGrid>
          {wishlist.data?.map((p) => (
            <ProductCardView key={p.id} product={p} />
          ))}
        </ProductGrid>
      )}
    </div>
  );
}
