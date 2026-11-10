import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { productApi } from "@/api/endpoints";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field, Input, Select, Textarea } from "@/components/ui/input";
import { ImageUploader } from "./ImageUploader";
import { useToast } from "@/components/ui/toast";
import { useCategories } from "@/hooks/useCategories";
import type { ProductInput } from "@/types";

interface VariantRow {
  sku: string;
  variant_name: string;
  attributes: string;
  selling_price: string;
  quantity: string;
}
interface SpecRow {
  key: string;
  value: string;
}

const newVariant = (): VariantRow => ({ sku: "", variant_name: "", attributes: "", selling_price: "", quantity: "" });

/** "ram: 16GB, storage: 512GB" -> { ram: "16GB", storage: "512GB" } */
function parseAttributes(text: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const part of text.split(/[,\n]/)) {
    const idx = part.indexOf(":");
    if (idx > 0) {
      const k = part.slice(0, idx).trim();
      const v = part.slice(idx + 1).trim();
      if (k && v) out[k] = v;
    }
  }
  return out;
}

function coerce(v: string): string | number {
  const n = Number(v);
  return v.trim() !== "" && Number.isFinite(n) ? n : v;
}

export function ProductForm({ onCreated }: { onCreated: () => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const categories = useCategories();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [brand, setBrand] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [images, setImages] = useState<string[]>([]);
  const [uploadingImages, setUploadingImages] = useState(false);
  const [specs, setSpecs] = useState<SpecRow[]>([{ key: "", value: "" }]);
  const [variants, setVariants] = useState<VariantRow[]>([newVariant()]);

  const create = useMutation({
    mutationFn: (input: ProductInput) => productApi.create(input),
    onSuccess: () => {
      toast.success("Product created. It will appear in AI search once indexed.");
      qc.invalidateQueries({ queryKey: ["seller", "products"] });
      qc.invalidateQueries({ queryKey: ["products"] });
      onCreated();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const setVariant = (i: number, patch: Partial<VariantRow>) =>
    setVariants((vs) => vs.map((v, idx) => (idx === i ? { ...v, ...patch } : v)));
  const setSpec = (i: number, patch: Partial<SpecRow>) =>
    setSpecs((ss) => ss.map((s, idx) => (idx === i ? { ...s, ...patch } : s)));

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const specifications: Record<string, string | number> = {};
    for (const s of specs) if (s.key.trim() && s.value.trim()) specifications[s.key.trim()] = coerce(s.value.trim());

    create.mutate({
      category_id: Number(categoryId),
      name: name.trim(),
      description: description.trim(),
      brand: brand.trim() || undefined,
      specifications,
      image_urls: images,
      variants: variants.map((v) => ({
        sku: v.sku.trim(),
        variant_name: v.variant_name.trim(),
        attributes: parseAttributes(v.attributes),
        selling_price: Number(v.selling_price),
        quantity: Number(v.quantity),
      })),
    });
  };

  return (
    <form onSubmit={submit} className="space-y-6">
      <Card className="grid gap-4 p-5 sm:grid-cols-2">
        <Field label="Product name" htmlFor="pname" className="sm:col-span-2">
          <Input id="pname" required value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <Field label="Category" htmlFor="pcat">
          <Select id="pcat" required value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
            <option value="">Select a category</option>
            {categories.data?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Brand" htmlFor="pbrand">
          <Input id="pbrand" value={brand} onChange={(e) => setBrand(e.target.value)} />
        </Field>
        <Field label="Description" htmlFor="pdesc" className="sm:col-span-2" hint="Used for keyword and AI semantic search — be descriptive.">
          <Textarea id="pdesc" required rows={4} value={description} onChange={(e) => setDescription(e.target.value)} />
        </Field>
        <Field label="Images" className="sm:col-span-2">
          <ImageUploader urls={images} onChange={setImages} onBusyChange={setUploadingImages} />
        </Field>
      </Card>

      <Card className="space-y-3 p-5">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold">Specifications</h3>
          <Button type="button" variant="outline" size="sm" onClick={() => setSpecs((s) => [...s, { key: "", value: "" }])}>
            <Plus className="h-4 w-4" /> Add
          </Button>
        </div>
        {specs.map((s, i) => (
          <div key={i} className="flex gap-2">
            <Input placeholder="e.g. ram_gb" aria-label="Specification name" value={s.key} onChange={(e) => setSpec(i, { key: e.target.value })} />
            <Input placeholder="e.g. 16" aria-label="Specification value" value={s.value} onChange={(e) => setSpec(i, { value: e.target.value })} />
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label="Remove specification"
              disabled={specs.length === 1}
              onClick={() => setSpecs((ss) => ss.filter((_, idx) => idx !== i))}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        ))}
        <p className="text-xs text-muted-foreground">Numeric values are stored as numbers (e.g. ram_gb: 16).</p>
      </Card>

      <Card className="space-y-4 p-5">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold">Variants &amp; your offer</h3>
          <Button type="button" variant="outline" size="sm" onClick={() => setVariants((v) => [...v, newVariant()])}>
            <Plus className="h-4 w-4" /> Add variant
          </Button>
        </div>
        {variants.map((v, i) => (
          <div key={i} className="grid gap-3 rounded-md border p-3 sm:grid-cols-6">
            <Field label="SKU" className="sm:col-span-2">
              <Input required value={v.sku} onChange={(e) => setVariant(i, { sku: e.target.value })} />
            </Field>
            <Field label="Variant name" className="sm:col-span-4">
              <Input required placeholder="e.g. 16GB / 512GB" value={v.variant_name} onChange={(e) => setVariant(i, { variant_name: e.target.value })} />
            </Field>
            <Field label="Attributes" className="sm:col-span-3" hint="key: value, key: value">
              <Input placeholder="ram: 16GB, storage: 512GB" value={v.attributes} onChange={(e) => setVariant(i, { attributes: e.target.value })} />
            </Field>
            <Field label="Price (₹)" className="sm:col-span-1">
              <Input required type="number" min={1} step="0.01" value={v.selling_price} onChange={(e) => setVariant(i, { selling_price: e.target.value })} />
            </Field>
            <Field label="Stock" className="sm:col-span-1">
              <Input required type="number" min={0} value={v.quantity} onChange={(e) => setVariant(i, { quantity: e.target.value })} />
            </Field>
            <div className="flex items-end sm:col-span-1">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                disabled={variants.length === 1}
                onClick={() => setVariants((vs) => vs.filter((_, idx) => idx !== i))}
              >
                <Trash2 className="h-4 w-4" /> Remove
              </Button>
            </div>
          </div>
        ))}
      </Card>

      <Button type="submit" size="lg" loading={create.isPending} disabled={uploadingImages}>
        Create product
      </Button>
    </form>
  );
}
