import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { cartApi } from "@/api/endpoints";
import { useAuth } from "@/features/auth/AuthContext";
import { useToast } from "@/components/ui/toast";
import type { Cart } from "@/types";

export const cartKey = ["cart"];

export function useCart() {
  const { user } = useAuth();
  return useQuery({ queryKey: cartKey, queryFn: cartApi.get, enabled: user?.role === "customer" });
}

export function useCartMutations() {
  const qc = useQueryClient();
  const toast = useToast();
  const set = (cart: Cart) => qc.setQueryData(cartKey, cart);
  const onError = (e: Error) => toast.error(e.message);

  return {
    add: useMutation({
      mutationFn: (v: { listingId: number; quantity: number }) => cartApi.add(v.listingId, v.quantity),
      onSuccess: (c) => {
        set(c);
        toast.success("Added to cart");
      },
      onError,
    }),
    update: useMutation({
      mutationFn: (v: { id: number; quantity: number }) => cartApi.update(v.id, v.quantity),
      onSuccess: set,
      onError,
    }),
    remove: useMutation({ mutationFn: (id: number) => cartApi.remove(id), onSuccess: set, onError }),
  };
}
