import { betterAuth } from "better-auth";
import pg from "pg";
import http from "node:http";
import dotenv from "dotenv";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

// Load .env from project root (parent of auth-service/)
const __dirname = dirname(fileURLToPath(import.meta.url));
dotenv.config({ path: resolve(__dirname, "../.env") });

const { Pool } = pg;

// Connect to local PostgreSQL (same server, no remote connection needed)
const connectionString =
  process.env.DATABASE_URL?.replace("postgresql+asyncpg://", "postgresql://") ||
  process.env.AUTH_DATABASE_URL ||
  "postgresql://postgres:postgres@localhost:5432/waimao";

const pool = new Pool({ connectionString });

const cookieDomain = process.env.BETTER_AUTH_COOKIE_DOMAIN;
// Auth service runs on api.clientconnet.com, not clientconnet.com
const baseURL = process.env.AUTH_BASE_URL || "http://localhost:8000";

const auth = betterAuth({
  appName: "AI 外贸业务员",
  baseURL,
  trustedOrigins: [
    baseURL,
    "https://clientconnet.com",
    "https://www.clientconnet.com",
  ],
  secret: process.env.BETTER_AUTH_SECRET || "change-me",
  database: pool,
  emailAndPassword: {
    enabled: true,
    autoSignIn: true,
    minPasswordLength: 8,
  },
  user: {
    modelName: "users",
    fields: {
      name: "username",
      emailVerified: "email_verified",
      createdAt: "created_at",
      updatedAt: "updated_at",
    },
  },
  session: {
    modelName: "auth_sessions",
    fields: {
      expiresAt: "expires_at",
      createdAt: "created_at",
      updatedAt: "updated_at",
      ipAddress: "ip_address",
      userAgent: "user_agent",
      userId: "user_id",
    },
  },
  account: {
    modelName: "auth_accounts",
    fields: {
      accountId: "account_id",
      providerId: "provider_id",
      userId: "user_id",
      accessToken: "access_token",
      refreshToken: "refresh_token",
      idToken: "id_token",
      accessTokenExpiresAt: "access_token_expires_at",
      refreshTokenExpiresAt: "refresh_token_expires_at",
      createdAt: "created_at",
      updatedAt: "updated_at",
    },
  },
  verification: {
    modelName: "auth_verifications",
    fields: {
      expiresAt: "expires_at",
      createdAt: "created_at",
      updatedAt: "updated_at",
    },
  },
  advanced: {
    database: {
      generateId: "serial",
    },
    ...(cookieDomain
      ? {
          crossSubDomainCookies: {
            enabled: true,
            domain: cookieDomain,
          },
        }
      : {}),
  },
});

const PORT = parseInt(process.env.AUTH_PORT || "8001", 10);

// Read request body as ArrayBuffer
async function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on("data", (chunk) => chunks.push(chunk));
    req.on("end", () => resolve(Buffer.concat(chunks)));
    req.on("error", reject);
  });
}

const server = http.createServer(async (req, res) => {
  const origin = req.headers.origin || "";
  const url = new URL(req.url, `http://localhost:${PORT}`);

  // Only handle /api/auth/* routes
  if (!url.pathname.startsWith("/api/auth/")) {
    res.writeHead(404, { "Content-Type": "text/plain" });
    res.end("Not Found");
    return;
  }

  try {
    const body = await readBody(req);

    // Build Web Request
    const headers = new Headers();
    for (const [key, value] of Object.entries(req.headers)) {
      if (value != null) {
        headers.set(key, Array.isArray(value) ? value.join(", ") : value);
      }
    }

    const requestBody =
      req.method !== "GET" && req.method !== "HEAD"
        ? body.buffer.slice(body.byteOffset, body.byteOffset + body.byteLength)
        : undefined;

    const webRequest = new Request(url, {
      method: req.method,
      headers,
      body: requestBody,
    });

    // Call Better Auth handler
    const webResponse = await auth.handler(webRequest);

    // Write response back
    res.writeHead(webResponse.status, Object.fromEntries(webResponse.headers));
    const responseBody = await webResponse.arrayBuffer();
    res.end(Buffer.from(responseBody));
  } catch (err) {
    console.error("[auth-service] Error:", err);
    res.writeHead(500, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: "Internal server error" }));
  }
});

server.listen(PORT, "127.0.0.1", () => {
  console.log(`[auth-service] Better Auth listening on http://127.0.0.1:${PORT}`);
});
