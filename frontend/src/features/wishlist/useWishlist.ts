import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { wishlistApi } from "@/api/endpoints";
import { useAuth } from "@/features/auth/AuthContext";
import { useToast } from "@/components/ui/toast";

export const wishlistKey = ["wishlist"];

export function useWishlist() {
  const { user } = useAuth();
  return useQuery({ queryKey: wishlistKey, queryFn: wishlistApi.list, enabled: user?.role === "customer" });
}

export function useToggleWishlist() {
  const qc = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: (v: { productId: number; inWishlist: boolean }) =>
      v.inWishlist ? wishlistApi.remove(v.productId) : wishlistApi.add(v.productId),
    onSuccess: (_d, v) => {
      qc.invalidateQueries({ queryKey: wishlistKey });
      toast.success(v.inWishlist ? "Removed from wishlist" : "Saved to wishlist");
    },
    onError: (e: Error) => toast.error(e.message),
  });
}
