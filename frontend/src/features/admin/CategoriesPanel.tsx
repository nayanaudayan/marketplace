import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { adminApi } from "@/api/endpoints";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { PageSpinner } from "@/components/ui/feedback";
import { Field, Input, Select } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { useCategories } from "@/hooks/useCategories";

export function CategoriesPanel() {
  const qc = useQueryClient();
  const toast = useToast();
  const categories = useCategories();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [parent, setParent] = useState("");

  const add = useMutation({
    mutationFn: () =>
      adminApi.addCategory({
        name: name.trim(),
        description: description.trim() || undefined,
        parent_category_id: parent ? Number(parent) : undefined,
      }),
    onSuccess: (c) => {
      toast.success(`Category “${c.name}” added`);
      setName("");
      setDescription("");
      setParent("");
      qc.invalidateQueries({ queryKey: ["categories"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    add.mutate();
  };

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card className="h-fit p-5">
        <h3 className="mb-4 font-semibold">Add category</h3>
        <form onSubmit={submit} className="space-y-4">
          <Field label="Name" htmlFor="cname">
            <Input id="cname" required value={name} onChange={(e) => setName(e.target.value)} />
          </Field>
          <Field label="Description" htmlFor="cdesc">
            <Input id="cdesc" value={description} onChange={(e) => setDescription(e.target.value)} />
          </Field>
          <Field label="Parent category" htmlFor="cparent">
            <Select id="cparent" value={parent} onChange={(e) => setParent(e.target.value)}>
              <option value="">None (top level)</option>
              {categories.data?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </Select>
          </Field>
          <Button type="submit" loading={add.isPending}>
            Add category
          </Button>
        </form>
      </Card>
      <Card className="p-5">
        <h3 className="mb-3 font-semibold">Existing categories</h3>
        {categories.isLoading && <PageSpinner />}
        <ul className="divide-y text-sm">
          {categories.data?.map((c) => (
            <li key={c.id} className="flex items-center justify-between py-2">
              <span className="font-medium">{c.name}</span>
              <span className="text-xs text-muted-foreground">
                {c.parent_category_id
                  ? `under ${categories.data?.find((p) => p.id === c.parent_category_id)?.name ?? "#" + c.parent_category_id}`
                  : "top level"}
              </span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
