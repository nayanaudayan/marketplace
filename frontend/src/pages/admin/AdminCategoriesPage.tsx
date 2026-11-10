import { PageHeader } from "@/components/ui/feedback";
import { CategoriesPanel } from "@/features/admin/CategoriesPanel";

export default function AdminCategoriesPage() {
  return (
    <div>
      <PageHeader title="Categories" description="Organise the product catalogue." />
      <CategoriesPanel />
    </div>
  );
}
