import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Clock, XCircle } from "lucide-react";
import { ApiError } from "@/api/client";
import { sellerApi } from "@/api/endpoints";
import { StatusBadge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { ErrorState, PageHeader, PageSpinner } from "@/components/ui/feedback";
import { ProductForm } from "@/features/seller/ProductForm";
import { SellerOrders } from "@/features/seller/SellerOrders";
import { SellerProducts } from "@/features/seller/SellerProducts";
import { SellerRegisterForm } from "@/features/seller/SellerRegisterForm";
import { cn } from "@/utils/cn";

type Tab = "products" | "new" | "orders";

export default function SellerDashboardPage() {
  const [tab, setTab] = useState<Tab>("products");
  const profile = useQuery({
    queryKey: ["seller", "profile"],
    queryFn: sellerApi.profile,
    retry: false,
  });

  if (profile.isLoading) return <PageSpinner />;

  // No seller profile yet: let the user create their store.
  if (profile.error instanceof ApiError && profile.error.status === 404) {
    return (
      <div>
        <PageHeader title="Seller dashboard" />
        <SellerRegisterForm />
      </div>
    );
  }
  if (profile.isError) return <ErrorState error={profile.error} onRetry={() => profile.refetch()} />;
  const seller = profile.data!;

  if (seller.approval_status !== "approved") {
    const rejected = seller.approval_status === "rejected";
    return (
      <div>
        <PageHeader title="Seller dashboard" />
        <Card className="mx-auto flex max-w-lg flex-col items-center gap-3 p-8 text-center">
          {rejected ? <XCircle className="h-10 w-10 text-destructive" /> : <Clock className="h-10 w-10 text-amber-500" />}
          <h2 className="text-lg font-semibold">{seller.store_name}</h2>
          <StatusBadge status={seller.approval_status} />
          <p className="text-sm text-muted-foreground">
            {rejected
              ? "Your store application was not approved. Please contact marketplace support."
              : "Your store is awaiting administrator approval. You'll be able to list products once it's approved."}
          </p>
        </Card>
      </div>
    );
  }

  const tabs: { id: Tab; label: string }[] = [
    { id: "products", label: "My products" },
    { id: "new", label: "Add product" },
    { id: "orders", label: "Orders" },
  ];

  return (
    <div>
      <PageHeader
        title={seller.store_name}
        description={seller.store_description ?? "Manage your catalogue, inventory and orders."}
        actions={<StatusBadge status={seller.approval_status} />}
      />
      <div className="mb-6 flex gap-1 border-b" role="tablist">
        {tabs.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => setTab(t.id)}
            className={cn(
              "-mb-px border-b-2 px-4 py-2.5 text-sm font-medium transition-colors",
              tab === t.id ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "products" && <SellerProducts sellerId={seller.id} />}
      {tab === "new" && <ProductForm onCreated={() => setTab("products")} />}
      {tab === "orders" && <SellerOrders />}
    </div>
  );
}
