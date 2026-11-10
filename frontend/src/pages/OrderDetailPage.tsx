import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { orderApi } from "@/api/endpoints";
import { StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ErrorState, PageSpinner } from "@/components/ui/feedback";
import { useToast } from "@/components/ui/toast";
import { PaymentPanel } from "@/features/orders/PaymentPanel";
import { formatDate, formatPrice } from "@/utils/format";

const STEPS = ["pending", "confirmed", "shipped", "delivered"] as const;

export default function OrderDetailPage() {
  const id = Number(useParams().id);
  const qc = useQueryClient();
  const toast = useToast();
  const order = useQuery({ queryKey: ["order", id], queryFn: () => orderApi.get(id), enabled: Number.isFinite(id) });

  const cancel = useMutation({
    mutationFn: () => orderApi.cancel(id),
    onSuccess: (o) => {
      qc.setQueryData(["order", id], o);
      qc.invalidateQueries({ queryKey: ["orders"] });
      toast.success("Order cancelled");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (order.isLoading) return <PageSpinner />;
  if (order.isError) return <ErrorState error={order.error} onRetry={() => order.refetch()} />;
  const o = order.data;
  if (!o) return null;

  const cancelled = o.order_status === "cancelled";
  const needsPayment = !cancelled && (o.payment_status === "pending" || o.payment_status === "failed");
  const canCancel = o.order_status === "pending" || o.order_status === "confirmed";
  const stepIndex = STEPS.indexOf(o.order_status as (typeof STEPS)[number]);

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <Button variant="ghost" size="sm" asChild>
        <Link to="/orders">
          <ArrowLeft className="h-4 w-4" /> All orders
        </Link>
      </Button>

      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{o.order_number}</h1>
          <p className="text-sm text-muted-foreground">Placed {formatDate(o.created_at)}</p>
        </div>
        <div className="flex gap-2">
          <StatusBadge status={o.order_status} />
          <StatusBadge status={o.payment_status} />
        </div>
      </div>

      {!cancelled && (
        <ol className="grid grid-cols-4 gap-2">
          {STEPS.map((s, i) => (
            <li key={s} className="space-y-1.5">
              <div className={i <= stepIndex ? "h-1.5 rounded-full bg-primary" : "h-1.5 rounded-full bg-muted"} />
              <p className={i <= stepIndex ? "text-xs font-medium capitalize" : "text-xs capitalize text-muted-foreground"}>{s}</p>
            </li>
          ))}
        </ol>
      )}

      {needsPayment && <PaymentPanel order={o} onDone={(updated) => qc.setQueryData(["order", id], updated)} />}

      <Card>
        <ul className="divide-y">
          {o.items.map((i) => (
            <li key={i.id} className="flex items-center justify-between gap-4 p-4 text-sm">
              <div>
                <p className="font-medium">{i.product_name_snapshot}</p>
                <p className="text-xs text-muted-foreground">
                  {formatPrice(i.price_snapshot)} × {i.quantity}
                </p>
              </div>
              <span className="font-medium">{formatPrice(i.subtotal)}</span>
            </li>
          ))}
        </ul>
        <div className="flex justify-between border-t p-4 text-lg font-bold">
          <span>Total</span>
          <span>{formatPrice(o.total_amount)}</span>
        </div>
      </Card>

      {canCancel && (
        <Button variant="destructive" loading={cancel.isPending} onClick={() => confirm("Cancel this order?") && cancel.mutate()}>
          Cancel order
        </Button>
      )}
    </div>
  );
}
