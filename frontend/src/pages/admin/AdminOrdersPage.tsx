import { PageHeader } from "@/components/ui/feedback";
import { OrdersPanel } from "@/features/admin/OrdersPanel";

export default function AdminOrdersPage() {
  return (
    <div>
      <PageHeader title="Orders" description="All marketplace orders and their payment status." />
      <OrdersPanel />
    </div>
  );
}
