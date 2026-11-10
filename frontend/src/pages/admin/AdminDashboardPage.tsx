import { Link } from "react-router-dom";
import { PageHeader } from "@/components/ui/feedback";
import { SellersPanel } from "@/features/admin/SellersPanel";
import { StatsTiles } from "@/features/admin/StatsTiles";

export default function AdminDashboardPage() {
  return (
    <div className="space-y-8">
      <PageHeader title="Admin dashboard" description="Marketplace overview and moderation." />
      <StatsTiles />
      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Sellers awaiting approval</h2>
          <Link to="/sellers" className="text-sm font-medium text-primary hover:underline">
            All sellers
          </Link>
        </div>
        <SellersPanel fixedStatus="pending" emptyTitle="No sellers are waiting for approval" />
      </section>
    </div>
  );
}
