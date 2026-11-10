import { PageHeader } from "@/components/ui/feedback";
import { SellersPanel } from "@/features/admin/SellersPanel";

export default function AdminSellersPage() {
  return (
    <div>
      <PageHeader title="Sellers" description="Approve or reject seller accounts." />
      <SellersPanel />
    </div>
  );
}
