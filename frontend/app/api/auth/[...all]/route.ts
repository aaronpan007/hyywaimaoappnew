import { auth } from "@/lib/auth";
import { toNextJsHandler } from "better-auth/next-js";

export const runtime = "nodejs";

// In production, auth is handled by auth-service on the backend.
// This route is only active for local dev (when DATABASE_URL is available).
if (auth) {
  const { GET, POST, PUT, PATCH, DELETE } = toNextJsHandler(auth.handler);
  export { GET, POST, PUT, PATCH, DELETE };
} else {
  // No-op handlers for Vercel build (auth-service handles all auth requests)
  async function noop() {
    return new Response(
      "Auth is handled by the backend auth-service",
      { status: 404 }
    );
  }
  export const GET = noop;
  export const POST = noop;
  export const PUT = noop;
  export const PATCH = noop;
  export const DELETE = noop;
}
