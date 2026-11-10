import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ChevronRight } from "lucide-react";
import { orderApi } from "@/api/endpoints";
import { StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorState, PageHeader, PageSpinner } from "@/components/ui/feedback";
import { formatDate, formatPrice } from "@/utils/format";

export default function OrdersPage() {
  const orders = useQuery({ queryKey: ["orders"], queryFn: orderApi.list });

  if (orders.isLoading) return <PageSpinner />;
  if (orders.isError) return <ErrorState error={orders.error} onRetry={() => orders.refetch()} />;

  return (
    <div>
      <PageHeader title="My orders" />
      {orders.data?.length === 0 ? (
        <EmptyState
          title="No orders yet"
          description="Once you place an order it will show up here."
          action={
            <Button asChild>
              <Link to="/products">Start shopping</Link>
            </Button>
          }
        />
      ) : (
        <div className="space-y-3">
          {orders.data?.map((o) => (
            <Link key={o.id} to={`/orders/${o.id}`} className="block">
              <Card className="flex flex-wrap items-center justify-between gap-4 p-4 transition-shadow hover:shadow-md">
                <div className="space-y-1">
                  <p className="font-semibold">{o.order_number}</p>
                  <p className="text-xs text-muted-foreground">
                    {formatDate(o.created_at)} · {o.items.length} item{o.items.length === 1 ? "" : "s"}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <StatusBadge status={o.order_status} />
                  <StatusBadge status={o.payment_status} />
                  <span className="ml-2 font-bold">{formatPrice(o.total_amount)}</span>
                  <ChevronRight className="h-4 w-4 text-muted-foreground" />
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
