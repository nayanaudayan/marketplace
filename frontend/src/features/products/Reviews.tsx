import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { productApi } from "@/api/endpoints";
import { Rating, StarPicker } from "@/components/Rating";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/feedback";
import { Textarea } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/features/auth/AuthContext";
import { formatDate } from "@/utils/format";

export function Reviews({ productId }: { productId: number }) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const [rating, setRating] = useState(5);
  const [text, setText] = useState("");

  const reviews = useQuery({ queryKey: ["reviews", productId], queryFn: () => productApi.reviews(productId) });
  const add = useMutation({
    mutationFn: () => productApi.addReview(productId, { rating, review_text: text.trim() || undefined }),
    onSuccess: () => {
      setText("");
      setRating(5);
      toast.success("Thanks for your review!");
      qc.invalidateQueries({ queryKey: ["reviews", productId] });
      qc.invalidateQueries({ queryKey: ["product", productId] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    add.mutate();
  };

  return (
    <section className="space-y-4">
      <h2 className="text-xl font-semibold">Customer reviews</h2>

      {user?.role === "customer" && (
        <Card className="p-4">
          <form onSubmit={submit} className="space-y-3">
            <p className="text-sm font-medium">Write a review</p>
            <StarPicker value={rating} onChange={setRating} />
            <Textarea placeholder="Share your experience (optional)" value={text} onChange={(e) => setText(e.target.value)} />
            <Button type="submit" size="sm" loading={add.isPending}>
              Submit review
            </Button>
          </form>
        </Card>
      )}

      {reviews.isLoading && <Skeleton className="h-24" />}
      {reviews.isError && <ErrorState error={reviews.error} />}
      {reviews.data?.length === 0 && <EmptyState title="No reviews yet" description="Be the first to review this product." />}
      <div className="space-y-3">
        {reviews.data?.map((r) => (
          <Card key={r.id} className="p-4">
            <div className="flex items-center justify-between">
              <span className="font-medium">{r.user_name}</span>
              <span className="text-xs text-muted-foreground">{formatDate(r.created_at)}</span>
            </div>
            <Rating value={r.rating} className="mt-1" />
            {r.review_text && <p className="mt-2 text-sm text-muted-foreground">{r.review_text}</p>}
          </Card>
        ))}
      </div>
    </section>
  );
}
