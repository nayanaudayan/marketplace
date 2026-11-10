import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { GitCompare, MessageSquarePlus, Sparkles } from "lucide-react";
import { aiApi } from "@/api/endpoints";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/feedback";
import { Select } from "@/components/ui/input";
import { AISearchBar } from "@/features/ai-search/AISearchBar";
import { CompareDialog } from "@/features/ai-search/CompareDialog";
import { ProductCardView, ProductGrid } from "@/features/products/ProductCardView";
import { filterLabel } from "@/utils/format";
import type { AISearchResponse } from "@/types";

export default function AISearchPage() {
  const [params, setParams] = useSearchParams();
  const initialQ = params.get("q") ?? "";
  const [conversationId, setConversationId] = useState<number | undefined>();
  const [history, setHistory] = useState<string[]>([]);
  const [result, setResult] = useState<AISearchResponse | null>(null);
  const [sortBy, setSortBy] = useState("relevance");
  const [selected, setSelected] = useState<number[]>([]);
  const [compareIds, setCompareIds] = useState<number[] | null>(null);
  const started = useRef<string | null>(null);

  const search = useMutation({
    mutationFn: (v: { query: string; conversation_id?: number; sort_by?: string }) =>
      aiApi.search({ query: v.query, conversation_id: v.conversation_id, sort_by: v.sort_by, page: 1, page_size: 20 }),
    onSuccess: (res, v) => {
      setResult(res);
      setConversationId(res.conversation_id);
      setHistory((h) => [...h, v.query]);
      setSelected([]);
    },
  });

  // Run the query passed via ?q= (e.g. from the home page) once.
  useEffect(() => {
    if (initialQ && started.current !== initialQ) {
      started.current = initialQ;
      search.mutate({ query: initialQ, sort_by: sortBy });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialQ]);

  const run = (query: string) => {
    search.mutate({ query, conversation_id: conversationId, sort_by: sortBy });
  };

  const newSearch = () => {
    setConversationId(undefined);
    setHistory([]);
    setResult(null);
    started.current = null;
    setParams({});
  };

  const toggle = (id: number) =>
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : s.length < 4 ? [...s, id] : s));

  // Spec requirements and preferences arrive as ready-to-read phrases ("RAM ≥ 16 GB", "Lighter weight"): one chip each.
  const chips: { id: string; label: string; soft?: boolean }[] = [];
  for (const [k, v] of Object.entries(result?.extracted_filters ?? {})) {
    if (v === null || v === undefined || v === "") continue;
    if ((k === "specs" || k === "preferences") && Array.isArray(v)) {
      for (const phrase of v) chips.push({ id: `${k}:${phrase}`, label: String(phrase), soft: k === "preferences" });
    } else {
      chips.push({ id: k, label: filterLabel(k, v) });
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight">
          <Sparkles className="h-6 w-6 text-primary" /> AI product search
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Describe what you need in plain language. {conversationId && "Add follow-ups to refine — earlier requirements are kept."}
        </p>
      </div>

      <AISearchBar
        onSubmit={run}
        loading={search.isPending}
        clearOnSubmit
        size="md"
        placeholder={
          conversationId ? "Refine your search, e.g. “only Lenovo” or “with 16GB RAM”" : "e.g. lightweight laptop for programming under ₹70,000"
        }
        buttonLabel={conversationId ? "Refine" : "Search"}
        initialValue={conversationId ? "" : initialQ}
      />

      {history.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span className="text-muted-foreground">Conversation:</span>
          {history.map((h, i) => (
            <Badge key={i} variant="secondary" className="max-w-xs truncate">
              {h}
            </Badge>
          ))}
          <Button variant="ghost" size="sm" onClick={newSearch}>
            <MessageSquarePlus className="h-4 w-4" /> New search
          </Button>
        </div>
      )}

      {search.isError && <ErrorState error={search.error} onRetry={() => history.length && run(history[history.length - 1])} />}

      {search.isPending && (
        <div className="space-y-4">
          <Skeleton className="h-20 w-full" />
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-72" />
            ))}
          </div>
        </div>
      )}

      {result && !search.isPending && (
        <div className="space-y-5">
          <Card className="space-y-3 p-5">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-medium">Understood requirements:</span>
              {chips.length === 0 && <span className="text-sm text-muted-foreground">none detected — using semantic match</span>}
              {chips.map((c) => (
                <Badge key={c.id} title={c.soft ? "Preference: used to rank results, not a hard requirement" : undefined}>
                  {c.soft ? `Prefer: ${c.label.toLowerCase()}` : c.label}
                </Badge>
              ))}
            </div>
            {result.explanation && <p className="text-sm leading-relaxed text-muted-foreground">{result.explanation}</p>}
          </Card>

          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-muted-foreground">
              {result.total} matching product{result.total === 1 ? "" : "s"}
            </p>
            <div className="flex items-center gap-2">
              {selected.length >= 2 && (
                <Button variant="outline" size="sm" onClick={() => setCompareIds(selected)}>
                  <GitCompare className="h-4 w-4" /> Compare ({selected.length})
                </Button>
              )}
              <Select
                value={sortBy}
                aria-label="Sort"
                className="h-8 w-auto text-xs"
                onChange={(e) => {
                  setSortBy(e.target.value);
                  if (history.length)
                    search.mutate({ query: history[history.length - 1], conversation_id: conversationId, sort_by: e.target.value });
                }}
              >
                <option value="relevance">Best match</option>
                <option value="price_asc">Price: low to high</option>
                <option value="price_desc">Price: high to low</option>
              </Select>
            </div>
          </div>

          {result.products.length === 0 ? (
            <EmptyState
              title="No products matched"
              description="Try relaxing a requirement, e.g. a higher budget or fewer specifications."
            />
          ) : (
            <ProductGrid>
              {result.products.map((p) => (
                <div key={p.id} className="relative">
                  <ProductCardView product={p} />
                  <label className="absolute left-2 top-2 flex items-center gap-1.5 rounded-full bg-card/90 px-2 py-1 text-xs shadow">
                    <input type="checkbox" checked={selected.includes(p.id)} onChange={() => toggle(p.id)} />
                    Compare
                  </label>
                </div>
              ))}
            </ProductGrid>
          )}
        </div>
      )}

      {!result && !search.isPending && !search.isError && (
        <EmptyState
          title="Start with what you need"
          description="Mention the use case, budget and must-have specs — we turn it into filters and rank real, in-stock listings."
        />
      )}

      <CompareDialog productIds={compareIds} onClose={() => setCompareIds(null)} />
    </div>
  );
}
