import { useEffect } from "react";
import { useMutation } from "@tanstack/react-query";
import { aiApi } from "@/api/endpoints";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ErrorState, PageSpinner } from "@/components/ui/feedback";
import { formatPrice } from "@/utils/format";

export function CompareDialog({ productIds, onClose }: { productIds: number[] | null; onClose: () => void }) {
  const compare = useMutation({ mutationFn: (ids: number[]) => aiApi.compare(ids) });

  useEffect(() => {
    if (productIds) compare.mutate(productIds);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productIds]);

  const products = compare.data?.products ?? [];
  const specKeys = Array.from(new Set(products.flatMap((p) => Object.keys(p.specifications ?? {}))));

  return (
    <Dialog open={!!productIds} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-4xl">
        <DialogHeader>
          <DialogTitle>Product comparison</DialogTitle>
          <DialogDescription>AI summary based on live catalogue data.</DialogDescription>
        </DialogHeader>
        {compare.isPending && <PageSpinner />}
        {compare.isError && <ErrorState error={compare.error} />}
        {compare.data && (
          <div className="space-y-4">
            <p className="rounded-md bg-accent p-3 text-sm text-accent-foreground">{compare.data.summary}</p>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[480px] text-sm">
                <thead>
                  <tr className="border-b text-left">
                    <th className="p-2" />
                    {products.map((p) => (
                      <th key={p.id} className="p-2 font-semibold">
                        {p.name}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-b">
                    <td className="p-2 text-muted-foreground">Price from</td>
                    {products.map((p) => (
                      <td key={p.id} className="p-2 font-medium">
                        {formatPrice(p.min_price)}
                      </td>
                    ))}
                  </tr>
                  <tr className="border-b">
                    <td className="p-2 text-muted-foreground">Brand</td>
                    {products.map((p) => (
                      <td key={p.id} className="p-2">
                        {p.brand ?? "—"}
                      </td>
                    ))}
                  </tr>
                  <tr className="border-b">
                    <td className="p-2 text-muted-foreground">Rating</td>
                    {products.map((p) => (
                      <td key={p.id} className="p-2">
                        {p.avg_rating != null ? `${p.avg_rating.toFixed(1)} (${p.review_count})` : "—"}
                      </td>
                    ))}
                  </tr>
                  {specKeys.map((k) => (
                    <tr key={k} className="border-b">
                      <td className="p-2 capitalize text-muted-foreground">{k.replace(/_/g, " ")}</td>
                      {products.map((p) => (
                        <td key={p.id} className="p-2">
                          {p.specifications?.[k] != null ? String(p.specifications[k]) : "—"}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
