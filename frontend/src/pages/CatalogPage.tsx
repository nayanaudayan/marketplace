import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Search, X } from "lucide-react";
import { productApi } from "@/api/endpoints";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorState, PageHeader, Skeleton } from "@/components/ui/feedback";
import { Field, Input, Select } from "@/components/ui/input";
import { ProductCardView, ProductGrid } from "@/features/products/ProductCardView";
import { useCategories } from "@/hooks/useCategories";
import { useDebounced } from "@/hooks/useDebounced";

const PAGE_SIZE = 12;

export default function CatalogPage() {
  const [params, setParams] = useSearchParams();
  const categories = useCategories();

  const q = params.get("q") ?? "";
  const categoryId = params.get("category_id") ?? "";
  const brand = params.get("brand") ?? "";
  const minPrice = params.get("min_price") ?? "";
  const maxPrice = params.get("max_price") ?? "";
  const inStock = params.get("in_stock") === "true";
  const sortBy = params.get("sort_by") ?? "newest";
  const page = Math.max(1, Number(params.get("page") ?? 1) || 1);

  // Text inputs are debounced before they hit the URL (and therefore the API).
  const [qInput, setQInput] = useState(q);
  const [brandInput, setBrandInput] = useState(brand);
  const [minInput, setMinInput] = useState(minPrice);
  const [maxInput, setMaxInput] = useState(maxPrice);
  const dq = useDebounced(qInput);
  const dbrand = useDebounced(brandInput);
  const dmin = useDebounced(minInput);
  const dmax = useDebounced(maxInput);

  const update = (patch: Record<string, string | null>, resetPage = true) => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(patch)) {
      if (v === null || v === "") next.delete(k);
      else next.set(k, v);
    }
    if (resetPage) next.delete("page");
    setParams(next, { replace: true });
  };

  useEffect(() => {
    if (dq !== q || dbrand !== brand || dmin !== minPrice || dmax !== maxPrice) {
      update({ q: dq, brand: dbrand, min_price: dmin, max_price: dmax });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dq, dbrand, dmin, dmax]);

  const query = useQuery({
    queryKey: ["products", { q, categoryId, brand, minPrice, maxPrice, inStock, sortBy, page }],
    queryFn: () =>
      productApi.list({
        q: q || undefined,
        category_id: categoryId ? Number(categoryId) : undefined,
        brand: brand || undefined,
        min_price: minPrice ? Number(minPrice) : undefined,
        max_price: maxPrice ? Number(maxPrice) : undefined,
        in_stock: inStock || undefined,
        sort_by: sortBy,
        page,
        page_size: PAGE_SIZE,
      }),
    placeholderData: keepPreviousData,
  });

  const totalPages = query.data ? Math.max(1, Math.ceil(query.data.total / PAGE_SIZE)) : 1;
  const hasFilters = !!(q || categoryId || brand || minPrice || maxPrice || inStock);

  const clear = () => {
    setQInput("");
    setBrandInput("");
    setMinInput("");
    setMaxInput("");
    setParams({}, { replace: true });
  };

  return (
    <div>
      <PageHeader title="Shop" description="Browse every product from all sellers." />
      <div className="grid gap-6 lg:grid-cols-[260px_1fr]">
        <aside className="space-y-4 rounded-lg border bg-card p-4 lg:sticky lg:top-24 lg:self-start">
          <Field label="Search" htmlFor="q">
            <div className="relative">
              <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
              <Input id="q" className="pl-9" placeholder="Keywords" value={qInput} onChange={(e) => setQInput(e.target.value)} />
            </div>
          </Field>
          <Field label="Category" htmlFor="category">
            <Select id="category" value={categoryId} onChange={(e) => update({ category_id: e.target.value })}>
              <option value="">All categories</option>
              {categories.data?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Brand" htmlFor="brand">
            <Input id="brand" placeholder="e.g. Lenovo" value={brandInput} onChange={(e) => setBrandInput(e.target.value)} />
          </Field>
          <div className="grid grid-cols-2 gap-2">
            <Field label="Min price" htmlFor="minp">
              <Input id="minp" type="number" min={0} value={minInput} onChange={(e) => setMinInput(e.target.value)} />
            </Field>
            <Field label="Max price" htmlFor="maxp">
              <Input id="maxp" type="number" min={0} value={maxInput} onChange={(e) => setMaxInput(e.target.value)} />
            </Field>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={inStock}
              onChange={(e) => update({ in_stock: e.target.checked ? "true" : null })}
            />
            In stock only
          </label>
          {hasFilters && (
            <Button variant="ghost" size="sm" className="w-full" onClick={clear}>
              <X className="h-4 w-4" /> Clear filters
            </Button>
          )}
        </aside>

        <section className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-muted-foreground">
              {query.data ? `${query.data.total} product${query.data.total === 1 ? "" : "s"}` : "Loading…"}
            </p>
            <Select
              aria-label="Sort"
              className="h-9 w-auto"
              value={sortBy}
              onChange={(e) => update({ sort_by: e.target.value })}
            >
              <option value="newest">Newest</option>
              <option value="relevance">Relevance</option>
              <option value="price_asc">Price: low to high</option>
              <option value="price_desc">Price: high to low</option>
            </Select>
          </div>

          {query.isError && <ErrorState error={query.error} onRetry={() => query.refetch()} />}
          {query.isLoading && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-72" />
              ))}
            </div>
          )}
          {query.data && query.data.items.length === 0 && (
            <EmptyState
              title="No products found"
              description="Try different keywords or clear some filters."
              action={hasFilters ? <Button onClick={clear}>Clear filters</Button> : undefined}
            />
          )}
          {query.data && query.data.items.length > 0 && (
            <div className={query.isPlaceholderData ? "opacity-60 transition-opacity" : "transition-opacity"}>
              <ProductGrid>
                {query.data.items.map((p) => (
                  <ProductCardView key={p.id} product={p} />
                ))}
              </ProductGrid>
            </div>
          )}

          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-3 pt-2">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => update({ page: String(page - 1) }, false)}
              >
                <ChevronLeft className="h-4 w-4" /> Prev
              </Button>
              <span className="text-sm text-muted-foreground">
                Page {page} of {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= totalPages}
                onClick={() => update({ page: String(page + 1) }, false)}
              >
                Next <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
