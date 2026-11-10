import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { sellerApi } from "@/api/endpoints";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Textarea } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";

export function SellerRegisterForm() {
  const qc = useQueryClient();
  const toast = useToast();
  const [storeName, setStoreName] = useState("");
  const [description, setDescription] = useState("");

  const register = useMutation({
    mutationFn: () => sellerApi.register({ store_name: storeName.trim(), store_description: description.trim() || undefined }),
    onSuccess: (seller) => {
      qc.setQueryData(["seller", "profile"], seller);
      toast.success("Store submitted for approval");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    register.mutate();
  };

  return (
    <Card className="mx-auto max-w-lg">
      <CardHeader>
        <CardTitle>Set up your store</CardTitle>
        <CardDescription>An administrator will review your store before you can list products.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="space-y-4">
          <Field label="Store name" htmlFor="store">
            <Input id="store" required minLength={2} value={storeName} onChange={(e) => setStoreName(e.target.value)} />
          </Field>
          <Field label="Store description" htmlFor="sdesc">
            <Textarea id="sdesc" value={description} onChange={(e) => setDescription(e.target.value)} />
          </Field>
          <Button type="submit" loading={register.isPending}>
            Submit for approval
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
