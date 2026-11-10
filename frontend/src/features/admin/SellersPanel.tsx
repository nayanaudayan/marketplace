import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, X } from "lucide-react";
import { adminApi } from "@/api/endpoints";
import { StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorState, PageSpinner } from "@/components/ui/feedback";
import { Select } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";

interface Props {
  /** Lock the list to one approval status and hide the filter (used on the dashboard for "pending"). */
  fixedStatus?: string;
  emptyTitle?: string;
}

export function SellersPanel({ fixedStatus, emptyTitle = "No sellers found" }: Props) {
  const qc = useQueryClient();
  const toast = useToast();
  const [filter, setFilter] = useState("");
  const status = fixedStatus ?? filter;
  const sellers = useQuery({ queryKey: ["admin", "sellers", status], queryFn: () => adminApi.sellers(status || undefined) });

  const decide = useMutation({
    mutationFn: (v: { id: number; approve: boolean }) => (v.approve ? adminApi.approve(v.id) : adminApi.reject(v.id)),
    onSuccess: (s, v) => {
      toast.success(`${s.store_name} ${v.approve ? "approved" : "rejected"}`);
      qc.invalidateQueries({ queryKey: ["admin"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div className="space-y-4">
      {!fixedStatus && (
        <Select aria-label="Filter by status" className="w-48" value={filter} onChange={(e) => setFilter(e.target.value)}>
          <option value="">All sellers</option>
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
        </Select>
      )}
      {sellers.isLoading && <PageSpinner />}
      {sellers.isError && <ErrorState error={sellers.error} onRetry={() => sellers.refetch()} />}
      {sellers.data?.length === 0 && <EmptyState title={emptyTitle} />}
      {!!sellers.data?.length && (
        <Card className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <thead>
              <tr className="border-b text-left text-muted-foreground">
                <th className="p-3 font-medium">Store</th>
                <th className="p-3 font-medium">Owner</th>
                <th className="p-3 font-medium">Commission</th>
                <th className="p-3 font-medium">Status</th>
                <th className="p-3" />
              </tr>
            </thead>
            <tbody>
              {sellers.data.map((s) => {
                const busy = decide.isPending && decide.variables?.id === s.id;
                return (
                  <tr key={s.id} className="border-b last:border-0">
                    <td className="p-3">
                      <p className="font-medium">{s.store_name}</p>
                      {s.store_description && <p className="line-clamp-1 text-xs text-muted-foreground">{s.store_description}</p>}
                    </td>
                    <td className="p-3">
                      <p>{s.user_name ?? `User #${s.user_id}`}</p>
                      <p className="text-xs text-muted-foreground">{s.user_email}</p>
                    </td>
                    <td className="p-3">{s.commission_percentage}%</td>
                    <td className="p-3">
                      <StatusBadge status={s.approval_status} />
                    </td>
                    <td className="p-3">
                      <div className="flex justify-end gap-2">
                        {s.approval_status !== "approved" && (
                          <Button size="sm" disabled={busy} onClick={() => decide.mutate({ id: s.id, approve: true })}>
                            <Check className="h-4 w-4" /> Approve
                          </Button>
                        )}
                        {s.approval_status !== "rejected" && (
                          <Button size="sm" variant="outline" disabled={busy} onClick={() => decide.mutate({ id: s.id, approve: false })}>
                            <X className="h-4 w-4" /> Reject
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
