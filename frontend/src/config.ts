/** The same codebase builds two apps: the public storefront (customers + sellers) and a separate admin console.
 *  Selected at build time via VITE_APP_MODE (see .env.admin, `npm run dev:admin`, `npm run build:admin`). */
export const APP_MODE: "storefront" | "admin" = import.meta.env.VITE_APP_MODE === "admin" ? "admin" : "storefront";
export const IS_ADMIN_APP = APP_MODE === "admin";

/** Where administrators sign in, shown to admins who try the storefront. Optional. */
export const ADMIN_PORTAL_URL: string | undefined = import.meta.env.VITE_ADMIN_URL || undefined;
