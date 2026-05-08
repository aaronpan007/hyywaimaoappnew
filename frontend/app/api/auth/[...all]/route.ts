import { auth } from "@/lib/auth";
import { toNextJsHandler } from "better-auth/next-js";

export const runtime = "nodejs";

// In production, auth is handled by auth-service on the backend server.
// This route is only active for local dev (when DATABASE_URL is available).
const handlers = auth
  ? toNextJsHandler(auth.handler)
  : {
      GET: () =>
        new Response("Auth handled by backend", { status: 404 }),
      POST: () =>
        new Response("Auth handled by backend", { status: 404 }),
      PUT: () =>
        new Response("Auth handled by backend", { status: 404 }),
      PATCH: () =>
        new Response("Auth handled by backend", { status: 404 }),
      DELETE: () =>
        new Response("Auth handled by backend", { status: 404 }),
    };

export const GET = handlers.GET;
export const POST = handlers.POST;
export const PUT = handlers.PUT;
export const PATCH = handlers.PATCH;
export const DELETE = handlers.DELETE;
