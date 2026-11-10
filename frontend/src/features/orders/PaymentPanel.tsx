import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CreditCard, ShieldCheck } from "lucide-react";
import { paymentApi } from "@/api/endpoints";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useToast } from "@/components/ui/toast";
import { cartKey } from "@/features/cart/useCart";
import { formatPrice } from "@/utils/format";
import type { Order, PaymentInit } from "@/types";

/**
 * Dev payment flow: initiate a payment, then simulate the gateway outcome.
 * Both outcomes go through the backend's verified payment path.
 */
export function PaymentPanel({ order, onDone }: { order: Order; onDone: (order: Order) => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [payment, setPayment] = useState<PaymentInit | null>(null);

  const initiate = useMutation({
    mutationFn: () => paymentApi.initiate(order.id),
    onSuccess: setPayment,
    onError: (e: Error) => toast.error(e.message),
  });

  const complete = useMutation({
    mutationFn: (success: boolean) => paymentApi.mockComplete(payment!.payment_id, success),
    onSuccess: (updated, success) => {
      qc.invalidateQueries({ queryKey: ["orders"] });
      qc.invalidateQueries({ queryKey: ["order", order.id] });
      qc.invalidateQueries({ queryKey: cartKey });
      if (success) toast.success("Payment successful — order confirmed");
      else toast.error("Payment failed. You can try again.");
      setPayment(null);
      onDone(updated);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <Card className="space-y-4 p-5">
      <div className="flex items-center gap-2">
        <CreditCard className="h-5 w-5 text-primary" />
        <h2 className="font-semibold">Payment</h2>
      </div>
      <p className="text-sm text-muted-foreground">
        Order {order.order_number} · Amount due <strong className="text-foreground">{formatPrice(order.total_amount)}</strong>
      </p>

      {!payment ? (
        <Button onClick={() => initiate.mutate()} loading={initiate.isPending}>
          {order.payment_status === "failed" ? "Retry payment" : "Pay now"}
        </Button>
      ) : (
        <div className="space-y-3 rounded-md border border-dashed bg-muted/50 p-4">
          <p className="flex items-center gap-2 text-sm font-medium">
            <ShieldCheck className="h-4 w-4 text-success" /> Test payment gateway
          </p>
          <p className="text-xs text-muted-foreground">
            This simulates the gateway callback. The result is verified by the server, not trusted from the browser.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => complete.mutate(true)} loading={complete.isPending && complete.variables === true}>
              Simulate successful payment
            </Button>
            <Button
              variant="outline"
              onClick={() => complete.mutate(false)}
              loading={complete.isPending && complete.variables === false}
            >
              Simulate failed payment
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}
