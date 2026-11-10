import { useQuery } from "@tanstack/react-query";
import { adminApi } from "@/api/endpoints";
import { StatusBadge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorState, PageSpinner } from "@/components/ui/feedback";
import { formatDate, formatPrice } from "@/utils/format";

export function OrdersPanel() {
  const orders = useQuery({ queryKey: ["admin", "orders"], queryFn: adminApi.orders });
  if (orders.isLoading) return <PageSpinner />;
  if (orders.isError) return <ErrorState error={orders.error} onRetry={() => orders.refetch()} />;
  if (!orders.data?.length) return <EmptyState title="No orders yet" />;
  return (
    <Card className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-sm">
        <thead>
          <tr className="border-b text-left text-muted-foreground">
            <th className="p-3 font-medium">Order</th>
            <th className="p-3 font-medium">Placed</th>
            <th className="p-3 font-medium">Items</th>
            <th className="p-3 font-medium">Total</th>
            <th className="p-3 font-medium">Order status</th>
            <th className="p-3 font-medium">Payment</th>
          </tr>
        </thead>
        <tbody>
          {orders.data.map((o) => (
            <tr key={o.id} className="border-b last:border-0">
              <td className="p-3 font-medium">{o.order_number}</td>
              <td className="p-3 text-muted-foreground">{formatDate(o.created_at)}</td>
              <td className="p-3">{o.items.length}</td>
              <td className="p-3">{formatPrice(o.total_amount)}</td>
              <td className="p-3">
                <StatusBadge status={o.order_status} />
              </td>
              <td className="p-3">
                <StatusBadge status={o.payment_status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}
