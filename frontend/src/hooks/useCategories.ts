import { useQuery } from "@tanstack/react-query";
import { categoryApi } from "@/api/endpoints";

export function useCategories() {
  return useQuery({ queryKey: ["categories"], queryFn: categoryApi.list, staleTime: 5 * 60_000 });
}
