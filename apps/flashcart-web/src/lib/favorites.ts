import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { useAuth } from "./auth";

export function useFavorites() {
  const { status } = useAuth();
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["favorites"],
    queryFn: () => api<{ product_ids: string[] }>("/favorites"),
    enabled: status === "authenticated",
  });
  const toggle = useMutation({
    mutationFn: ({ id, on }: { id: string; on: boolean }) =>
      api<{ product_ids: string[] }>(`/favorites/${id}`, { method: on ? "PUT" : "DELETE" }),
    // Optimistic update so the heart responds instantly; rolled back on error.
    onMutate: async ({ id, on }) => {
      await queryClient.cancelQueries({ queryKey: ["favorites"] });
      const previous = queryClient.getQueryData<{ product_ids: string[] }>(["favorites"]);
      const ids = new Set(previous?.product_ids ?? []);
      if (on) ids.add(id);
      else ids.delete(id);
      queryClient.setQueryData(["favorites"], { product_ids: [...ids] });
      return { previous };
    },
    onError: (_err, _vars, ctx) => queryClient.setQueryData(["favorites"], ctx?.previous),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["favorites"] }),
  });
  const ids = new Set(query.data?.product_ids ?? []);
  return {
    ids,
    isFavorite: (id: string) => ids.has(id),
    toggle: (id: string) => toggle.mutate({ id, on: !ids.has(id) }),
    enabled: status === "authenticated",
  };
}
