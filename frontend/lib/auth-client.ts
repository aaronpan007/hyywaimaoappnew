"use client";

import { createAuthClient } from "better-auth/react";

export const authClient = createAuthClient({
  // In production: auth requests go to api.clientconnet.com (auth-service on backend)
  // In local dev: not set → defaults to window.location.origin (localhost:3000 → Next.js API route)
  ...(process.env.NEXT_PUBLIC_AUTH_URL
    ? { baseURL: process.env.NEXT_PUBLIC_AUTH_URL }
    : {}),
});
