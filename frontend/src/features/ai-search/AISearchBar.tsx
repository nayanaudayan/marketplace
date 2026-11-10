import { useState, type FormEvent } from "react";
import { Search, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/cn";

export function AISearchBar({
  onSubmit,
  initialValue = "",
  placeholder = "Describe what you need, e.g. lightweight laptop for programming, 16GB RAM, under ₹70,000",
  loading,
  size = "lg",
  buttonLabel = "Search",
  clearOnSubmit,
}: {
  onSubmit: (q: string) => void;
  initialValue?: string;
  placeholder?: string;
  loading?: boolean;
  size?: "md" | "lg";
  buttonLabel?: string;
  clearOnSubmit?: boolean;
}) {
  const [value, setValue] = useState(initialValue);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const q = value.trim();
    if (!q) return;
    onSubmit(q);
    if (clearOnSubmit) setValue("");
  };

  return (
    <form
      onSubmit={submit}
      className={cn(
        "flex items-center gap-2 rounded-xl border bg-card p-2 shadow-sm focus-within:ring-2 focus-within:ring-ring",
        size === "lg" && "shadow-md",
      )}
    >
      <Sparkles className="ml-2 hidden h-5 w-5 shrink-0 text-primary sm:block" />
      <input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={placeholder}
        aria-label="Natural-language product search"
        className={cn(
          "min-w-0 flex-1 bg-transparent px-2 outline-none placeholder:text-muted-foreground",
          size === "lg" ? "h-12 text-base" : "h-10 text-sm",
        )}
      />
      <Button type="submit" size={size === "lg" ? "lg" : "default"} loading={loading} className="shrink-0">
        {!loading && <Search className="h-4 w-4" />}
        <span className="hidden sm:inline">{buttonLabel}</span>
      </Button>
    </form>
  );
}
