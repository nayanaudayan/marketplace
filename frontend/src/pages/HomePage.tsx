import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, ShieldCheck, Sparkles, Store } from "lucide-react";
import { productApi } from "@/api/endpoints";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ErrorState, Skeleton } from "@/components/ui/feedback";
import { AISearchBar } from "@/features/ai-search/AISearchBar";
import { ProductCardView, ProductGrid } from "@/features/products/ProductCardView";
import { useCategories } from "@/hooks/useCategories";

const EXAMPLES = [
  "Lightweight laptop for programming, 16GB RAM, 512GB SSD, under ₹70,000",
  "Phone with great camera and good battery under ₹30,000",
  "Noise-cancelling headphones for travel",
];

export default function HomePage() {
  const navigate = useNavigate();
  const go = (q: string) => navigate(`/search?q=${encodeURIComponent(q)}`);
  const categories = useCategories();
  const featured = useQuery({
    queryKey: ["products", "featured"],
    queryFn: () => productApi.list({ page: 1, page_size: 8, sort_by: "newest" }),
  });

  return (
    <div className="space-y-12">
      <section className="rounded-2xl bg-gradient-to-br from-primary/10 via-accent to-card px-5 py-12 text-center sm:px-10 sm:py-16">
        <Badge className="mb-4">
          <Sparkles className="mr-1 h-3 w-3" /> AI-powered discovery
        </Badge>
        <h1 className="mx-auto max-w-3xl text-3xl font-bold tracking-tight sm:text-5xl">
          Just tell us what you need. We&apos;ll find it.
        </h1>
        <p className="mx-auto mt-4 max-w-2xl text-muted-foreground">
          Describe your requirements in everyday language. Our AI understands budget, specs and use case, then ranks real
          listings from verified sellers — with live price and stock.
        </p>
        <div className="mx-auto mt-8 max-w-3xl text-left">
          <AISearchBar onSubmit={go} />
        </div>
        <div className="mx-auto mt-4 flex max-w-3xl flex-wrap justify-center gap-2">
          {EXAMPLES.map((e) => (
            <button
              key={e}
              onClick={() => go(e)}
              className="rounded-full border bg-card px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:border-primary hover:text-primary"
            >
              {e}
            </button>
          ))}
        </div>
      </section>

      {categories.data && categories.data.length > 0 && (
        <section>
          <h2 className="mb-3 text-lg font-semibold">Browse by category</h2>
          <div className="flex flex-wrap gap-2">
            {categories.data.map((c) => (
              <Button key={c.id} variant="outline" size="sm" asChild>
                <Link to={`/products?category_id=${c.id}`}>{c.name}</Link>
              </Button>
            ))}
          </div>
        </section>
      )}

      <section>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">New arrivals</h2>
          <Button variant="link" asChild>
            <Link to="/products">
              View all <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
        </div>
        {featured.isLoading && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-72" />
            ))}
          </div>
        )}
        {featured.isError && <ErrorState error={featured.error} onRetry={() => featured.refetch()} />}
        {featured.data && (
          <ProductGrid>
            {featured.data.items.map((p) => (
              <ProductCardView key={p.id} product={p} />
            ))}
          </ProductGrid>
        )}
      </section>

      <section className="grid gap-4 sm:grid-cols-3">
        {[
          { icon: Sparkles, title: "Understands intent", text: "Budget, RAM, battery, use case — extracted from your own words." },
          { icon: ShieldCheck, title: "Verified data", text: "Price and stock always come from the marketplace database, never the AI." },
          { icon: Store, title: "Many sellers", text: "Compare offers for the same product across multiple vendors." },
        ].map((f) => (
          <div key={f.title} className="rounded-lg border bg-card p-5">
            <f.icon className="mb-3 h-6 w-6 text-primary" />
            <h3 className="font-semibold">{f.title}</h3>
            <p className="mt-1 text-sm text-muted-foreground">{f.text}</p>
          </div>
        ))}
      </section>
    </div>
  );
}
