import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Package, ShoppingBag, Store, Users, Wallet } from "lucide-react";
import { adminApi } from "@/api/endpoints";
import { Card } from "@/components/ui/card";
import { ErrorState, PageSpinner } from "@/components/ui/feedback";
import { formatPrice } from "@/utils/format";

export function useAdminStats() {
  return useQuery({ queryKey: ["admin", "dashboard"], queryFn: adminApi.dashboard });
}

export function StatsTiles() {
  const stats = useAdminStats();
  if (stats.isLoading) return <PageSpinner />;
  if (stats.isError) return <ErrorState error={stats.error} onRetry={() => stats.refetch()} />;
  const d = stats.data!;
  const tiles = [
    { label: "Users", value: d.users, icon: Users, to: undefined },
    { label: "Sellers", value: d.sellers, icon: Store, to: "/sellers", note: d.pending_sellers ? `${d.pending_sellers} pending` : undefined },
    { label: "Products", value: d.products, icon: Package, to: undefined },
    { label: "Orders", value: d.orders, icon: ShoppingBag, to: "/orders" },
    { label: "Revenue", value: formatPrice(d.revenue), icon: Wallet, to: undefined },
  ];
  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-5">
      {tiles.map((t) => {
        const body = (
          <Card className={`h-full p-4 ${t.to ? "transition-colors hover:border-primary" : ""}`}>
            <t.icon className="mb-2 h-5 w-5 text-primary" />
            <p className="text-2xl font-bold">{t.value}</p>
            <p className="text-sm text-muted-foreground">{t.label}</p>
            {t.note && <p className="mt-1 text-xs font-medium text-amber-600">{t.note}</p>}
          </Card>
        );
        return t.to ? (
          <Link key={t.label} to={t.to} aria-label={`${t.label}: view details`}>
            {body}
          </Link>
        ) : (
          <div key={t.label}>{body}</div>
        );
      })}
    </div>
  );
}
