import type { Role } from "@/types";

import { IS_ADMIN_APP } from "@/config";

export function homeFor(role: Role): string {
  if (IS_ADMIN_APP) return "/";
  if (role === "seller") return "/seller";
  return "/";
}
