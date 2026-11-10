const inr = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
const inr2 = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", minimumFractionDigits: 2 });

export const formatPrice = (n: number | null | undefined) =>
  n == null ? "—" : Number.isInteger(n) ? inr.format(n) : inr2.format(n);

export const formatDate = (iso: string) =>
  new Date(iso).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });

export function filterLabel(key: string, value: unknown): string {
  const labels: Record<string, string> = {
    category: "Category",
    max_price: "Max price",
    min_price: "Min price",
    minimum_ram_gb: "Min RAM",
    brand: "Brand",
    usage: "Usage",
    keywords: "Keywords",
    in_stock_only: "In stock only",
  };
  const label = labels[key] ?? key.replace(/_/g, " ");
  if (key.endsWith("price") && typeof value === "number") return `${label}: ${formatPrice(value)}`;
  if (key.endsWith("_gb")) return `${label}: ${value} GB`;
  if (Array.isArray(value)) return `${label}: ${value.join(", ")}`;
  return `${label}: ${String(value)}`;
}
