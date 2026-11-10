import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { sellerApi } from "@/api/endpoints";
import { StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorState, PageSpinner } from "@/components/ui/feedback";
import { useToast } from "@/components/ui/toast";
import { formatDate, formatPrice } from "@/utils/format";

export function SellerOrders() {
  const qc = useQueryClient();
  const toast = useToast();
  const orders = useQuery({ queryKey: ["seller", "orders"], queryFn: sellerApi.orders });

  const update = useMutation({
    mutationFn: (v: { orderId: number; status: "shipped" | "delivered" }) => sellerApi.updateOrderStatus(v.orderId, v.status),
    onSuccess: (_o, v) => {
      toast.success(`Order marked ${v.status}`);
      qc.invalidateQueries({ queryKey: ["seller", "orders"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (orders.isLoading) return <PageSpinner />;
  if (orders.isError) return <ErrorState error={orders.error} onRetry={() => orders.refetch()} />;
  if (!orders.data?.length) return <EmptyState title="No orders yet" description="Customer orders for your products appear here." />;

  return (
    <Card className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-sm">
        <thead>
          <tr className="border-b text-left text-muted-foreground">
            <th className="p-3 font-medium">Order</th>
            <th className="p-3 font-medium">Product</th>
            <th className="p-3 font-medium">Qty</th>
            <th className="p-3 font-medium">Subtotal</th>
            <th className="p-3 font-medium">Status</th>
            <th className="p-3" />
          </tr>
        </thead>
        <tbody>
          {orders.data.map((o, i) => {
            const next = o.order_status === "confirmed" ? "shipped" : o.order_status === "shipped" ? "delivered" : null;
            const pendingThis = update.isPending && update.variables?.orderId === o.order_id;
            return (
              <tr key={`${o.order_id}-${i}`} className="border-b last:border-0">
                <td className="p-3">
                  <p className="font-medium">{o.order_number}</p>
                  <p className="text-xs text-muted-foreground">{formatDate(o.created_at)}</p>
                </td>
                <td className="p-3">{o.product_name}</td>
                <td className="p-3">{o.quantity}</td>
                <td className="p-3">{formatPrice(o.subtotal)}</td>
                <td className="p-3">
                  <StatusBadge status={o.order_status} />
                </td>
                <td className="p-3 text-right">
                  {next && (
                    <Button size="sm" variant="outline" loading={pendingThis} onClick={() => update.mutate({ orderId: o.order_id, status: next })}>
                      Mark {next}
                    </Button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Card>
  );
}
