import type {
  EmailSettings,
  CompanyProfile,
  Lead,
  CalloutData,
  TimelineStep,
  ConfirmParamsData,
} from "@/types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ─── Generic fetch wrapper ────────────────────────────────────────────

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    credentials: "include",
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || `API error ${res.status}`);
  }

  // Handle empty responses
  const text = await res.text();
  if (!text) return undefined as T;
  return JSON.parse(text) as T;
}

// ─── Types for API responses ──────────────────────────────────────────

interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

interface LeadResponse extends Omit<Lead, "emailStatus"> {
  emailStatus: string;
}

interface ProfileResponse {
  id: number;
  companyName: string;
  oneLineIntro?: string;
  fullIntro?: string;
  location?: string;
  industry?: string;
  website?: string;
  established?: string;
  scale?: string;
  employees?: string;
  certifications?: any[] | string;
  cooperationModels?: any[] | string;
  products: any[];
  competencies: any[];
  targetCustomerTypes?: any[];
  caseStudies: any[];
  uniqueSellingPoints?: any[];
  customerMatchingGuide?: any[];
  boundaries?: Record<string, any>;
  metadata?: Record<string, any>;
  profileData?: Record<string, any>;
  profileMarkdown?: string;
  collectedAt: string;
  isCurrent: boolean;
}

// ─── Settings ─────────────────────────────────────────────────────────

export async function getSettings(): Promise<EmailSettings> {
  return apiFetch<EmailSettings>("/api/settings");
}

export async function updateSettings(
  data: Partial<EmailSettings>
): Promise<EmailSettings> {
  return apiFetch<EmailSettings>("/api/settings", {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function generatePrefix(companyName: string): Promise<string[]> {
  const res = await apiFetch<{ prefixes: string[] }>(
    "/api/settings/generate-prefix",
    {
      method: "POST",
      body: JSON.stringify({ companyName }),
    }
  );
  return res.prefixes;
}

// ─── Company Profile ─────────────────────────────────────────────────

export async function getProfile(): Promise<CompanyProfile | null> {
  try {
    const res = await apiFetch<ProfileResponse>("/api/profile");
    // Backend returns { detail: "No profile found" } when empty
    if ((res as any).detail) return null;
    return res as unknown as CompanyProfile;
  } catch {
    return null;
  }
}

export async function clearProfile(): Promise<void> {
  await apiFetch<{ ok: boolean; cleared: boolean }>("/api/profile", {
    method: "DELETE",
  });
}

export async function exportProfileDocx(): Promise<void> {
  const res = await fetch(`${BASE_URL}/api/profile/export`, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
  });

  if (!res.ok) {
    throw new Error("画像导出失败");
  }

  const blob = await res.blob();
  const disposition = res.headers.get("Content-Disposition") || "";
  const filenameMatch = disposition.match(/filename\*=UTF-8''([^;]+)/);
  const filename = filenameMatch
    ? decodeURIComponent(filenameMatch[1])
    : `公司画像_${new Date().toISOString().slice(0, 10)}.docx`;

  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// ─── Leads ────────────────────────────────────────────────────────────

export interface GetLeadsParams {
  page?: number;
  pageSize?: number;
  taskId?: number;
  search?: string;
  country?: string;
  industry?: string;
  minScore?: number;
  sortBy?: string;
  sortOrder?: "asc" | "desc";
}

export async function getLeads(
  params?: GetLeadsParams
): Promise<PaginatedResponse<Lead>> {
  const sp = new URLSearchParams();
  if (params?.page) sp.set("page", String(params.page));
  if (params?.pageSize) sp.set("pageSize", String(params.pageSize));
  if (params?.taskId) sp.set("taskId", String(params.taskId));
  if (params?.search) sp.set("search", params.search);
  if (params?.country) sp.set("country", params.country);
  if (params?.industry) sp.set("industry", params.industry);
  if (params?.minScore !== undefined) sp.set("minScore", String(params.minScore));
  if (params?.sortBy) sp.set("sortBy", params.sortBy);
  if (params?.sortOrder) sp.set("sortOrder", params.sortOrder);

  const query = sp.toString();
  const path = `/api/leads${query ? `?${query}` : ""}`;
  return apiFetch<PaginatedResponse<Lead>>(path);
}

export async function deleteLeads(leadIds: number[]): Promise<{ deleted: number }> {
  return apiFetch<{ deleted: number }>("/api/leads", {
    method: "DELETE",
    body: JSON.stringify({ lead_ids: leadIds }),
  });
}

export async function importLeadsFromFiles(
  files: { filename: string; data: string }[]
): Promise<{ taskId: number; savedCount: number }> {
  return apiFetch<{ taskId: number; savedCount: number }>("/api/leads/import", {
    method: "POST",
    body: JSON.stringify({ files }),
  });
}

export async function updateLead(leadId: number, fields: { contactName?: string; email?: string; userNote?: string }): Promise<void> {
  const body: Record<string, string> = {};
  if (fields.contactName !== undefined) body["contact_name"] = fields.contactName;
  if (fields.email !== undefined) body["email"] = fields.email;
  if (fields.userNote !== undefined) body["user_note"] = fields.userNote;
  return apiFetch<void>(`/api/leads/${leadId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function updateLeadEmail(
  leadId: number,
  fields: { emailSubject?: string; emailBody?: string }
): Promise<{ emailSubject: string; emailBody: string; sendStatus: string }> {
  const body: Record<string, string> = {};
  if (fields.emailSubject !== undefined) body["email_subject"] = fields.emailSubject;
  if (fields.emailBody !== undefined) body["email_body"] = fields.emailBody;
  const res = await apiFetch<any>(
    `/api/emails/leads/${leadId}`,
    {
      method: "PATCH",
      body: JSON.stringify(body),
    }
  );
  return {
    emailSubject: res.emailSubject ?? res.email_subject ?? "",
    emailBody: res.emailBody ?? res.email_body ?? "",
    sendStatus: res.sendStatus ?? res.send_status ?? "draft",
  };
}

export interface LeadWithEmail extends Lead {
  emailSubject?: string;
  emailBody?: string;
}

export async function getLeadsWithEmails(
  taskId: number,
  params?: { page?: number; pageSize?: number; search?: string }
): Promise<PaginatedResponse<LeadWithEmail>> {
  const sp = new URLSearchParams();
  if (params?.page) sp.set("page", String(params.page));
  if (params?.pageSize) sp.set("pageSize", String(params.pageSize));
  if (params?.search) sp.set("search", params.search);

  const query = sp.toString();
  const path = `/api/leads/${taskId}/emails${query ? `?${query}` : ""}`;
  return apiFetch<PaginatedResponse<LeadWithEmail>>(path);
}

export async function exportLeadsExcel(params?: Omit<GetLeadsParams, "page" | "pageSize" | "sortBy" | "sortOrder">): Promise<void> {
  const sp = new URLSearchParams();
  if (params?.taskId) sp.set("taskId", String(params.taskId));
  if (params?.search) sp.set("search", params.search);
  if (params?.country) sp.set("country", params.country);
  if (params?.industry) sp.set("industry", params.industry);
  if (params?.minScore !== undefined) sp.set("minScore", String(params.minScore));

  const query = sp.toString();
  const res = await fetch(`${BASE_URL}/api/leads/0/export${query ? `?${query}` : ""}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
  });

  if (!res.ok) {
    throw new Error("导出失败");
  }

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `leads_${new Date().toISOString().slice(0, 10)}.xlsx`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// ─── Emails ───────────────────────────────────────────────────────────

export async function getEmails(params?: {
  page?: number;
  pageSize?: number;
}): Promise<PaginatedResponse<any>> {
  const sp = new URLSearchParams();
  if (params?.page) sp.set("page", String(params.page));
  if (params?.pageSize) sp.set("pageSize", String(params.pageSize));

  const query = sp.toString();
  const path = `/api/emails${query ? `?${query}` : ""}`;
  return apiFetch(path);
}

// ─── Email Export ─────────────────────────────────────────────────────

export async function exportEmailsExcel(taskId?: number): Promise<void> {
  if (!taskId) return;
  const res = await fetch(`${BASE_URL}/api/emails/${taskId}/export`, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
  });

  if (!res.ok) {
    throw new Error("邮件导出失败");
  }

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `emails_${taskId}_${new Date().toISOString().slice(0, 10)}.xlsx`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// ─── Conversations ──────────────────────────────────────────────────

export interface ConversationListItem {
  id: number;
  title: string;
  mode: string;
  createdAt: string;
  updatedAt: string | null;
  messageCount: number;
}

export interface ConversationMessageResponse {
  id: number;
  role: "user" | "assistant";
  content: string;
  messageType: string;
  extraData: Record<string, any> | null;
  createdAt: string;
}

export async function getConversations(): Promise<ConversationListItem[]> {
  return apiFetch<ConversationListItem[]>("/api/conversations");
}

export async function getConversationMessages(
  conversationId: number
): Promise<ConversationMessageResponse[]> {
  return apiFetch<ConversationMessageResponse[]>(
    `/api/conversations/${conversationId}/messages`
  );
}

// ─── Tasks ────────────────────────────────────────────────────────────

export async function renameConversation(
  conversationId: number,
  title: string
): Promise<ConversationListItem> {
  return apiFetch<ConversationListItem>(`/api/conversations/${conversationId}`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });
}

export async function deleteConversation(
  conversationId: number
): Promise<{ deleted: boolean }> {
  return apiFetch<{ deleted: boolean }>(`/api/conversations/${conversationId}`, {
    method: "DELETE",
  });
}

export async function getTasks(params?: {
  page?: number;
  pageSize?: number;
  type?: string;
}): Promise<PaginatedResponse<any>> {
  const sp = new URLSearchParams();
  if (params?.page) sp.set("page", String(params.page));
  if (params?.pageSize) sp.set("pageSize", String(params.pageSize));
  if (params?.type) sp.set("type", params.type);

  const query = sp.toString();
  const path = `/api/tasks${query ? `?${query}` : ""}`;
  return apiFetch(path);
}

/** Check if there's a running task (for page reload recovery). */
export async function getRunningTask(): Promise<{
  taskId: number | null;
  type?: string;
  params?: any;
}> {
  return apiFetch("/api/tasks/running");
}

/** Stop a running task. */
export async function stopTask(taskId: number): Promise<void> {
  await apiFetch<{ status: string }>(`/api/tasks/${taskId}/stop`, {
    method: "POST",
  });
}

// ─── Chat SSE Stream ─────────────────────────────────────────────────

export interface StreamHandlers {
  onThinking?: () => void;
  onConfirmParams?: (data: ConfirmParamsData) => void;
  onResult?: (data: {
    callout?: CalloutData;
    summary?: string;
    taskId?: number;
  }) => void;
  onPipelineStarted?: (data: {
    taskId: number;
    type: string;
    title?: string;
  }) => void;
  onStepUpdate?: (data: {
    taskId: number;
    step: number;
    name: string;
    status: "pending" | "running" | "completed";
    progress?: number;
    message?: string;
    eta?: string;
  }) => void;
  onConfigRequired?: (data: {
    missingFields: string[];
    suggestion?: string;
  }) => void;
  onTaskCancelled?: (data: { taskId: number }) => void;
  onTaskStale?: (data: { taskId: number }) => void;
  onDone?: (data: { taskId?: number; conversationId?: number }) => void;
  onError?: (error: Error) => void;
}

/**
 * Parse SSE events from a ReadableStream reader.
 * Shared by streamChat() and reconnectStream().
 */
async function parseSSEStream(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  handlers: StreamHandlers,
  resolve: () => void,
  reject: (err: any) => void,
): Promise<void> {
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // Parse complete SSE blocks (separated by \n\n)
    const blocks = buffer.split("\n\n");
    // Keep the last (possibly incomplete) block in the buffer
    buffer = blocks.pop() || "";

    for (const block of blocks) {
      const lines = block.split("\n");
      let event = "";
      let dataStr = "";

      for (const line of lines) {
        if (line.startsWith("event: ")) {
          event = line.slice(7).trim();
        } else if (line.startsWith("data: ")) {
          dataStr = line.slice(6);
        }
      }

      if (!event) continue;

      let data: any = {};
      if (dataStr) {
        try {
          data = JSON.parse(dataStr);
        } catch {
          // Ignore malformed JSON
          continue;
        }
      }

      // Normalize taskId / task_id
      const taskId = data.taskId ?? data.task_id;

      switch (event) {
        case "thinking":
          handlers.onThinking?.();
          break;

        case "confirm_params":
          if (data.confirm_type === "email_craft") {
            handlers.onConfirmParams?.({
              industry: "",
              country: "",
              keywords: [],
              num: data.lead_count || 0,
              reply: data.reply || "",
              confirmType: "email_craft",
            });
          } else {
            handlers.onConfirmParams?.({
              industry: data.industry || "",
              country: data.country || "",
              keywords: data.keywords || [],
              num: data.num || 20,
              reply: data.reply || "",
            });
          }
          break;

        case "config_required":
          handlers.onConfigRequired?.({
            missingFields: data.missing_fields || [],
            suggestion: data.suggestion,
          });
          break;

        case "result": {
          const callout = data.callout
            ? {
                ...data.callout,
                taskId,
                actions: (data.callout.actions || []).map((a: any) => ({
                  label: a.label,
                  variant: a.variant,
                  type: a.type,
                })),
              }
            : undefined;
          handlers.onResult?.({
            callout: callout as CalloutData | undefined,
            summary: data.summary,
            taskId,
          });
          break;
        }

        case "pipeline_started":
          handlers.onPipelineStarted?.({
            taskId,
            type: data.type,
            title: data.title,
          });
          break;

        case "step_update":
          handlers.onStepUpdate?.({
            taskId,
            step: data.step,
            name: data.name,
            status: data.status,
            progress: data.progress,
            message: data.message,
            eta: data.eta,
          });
          break;

        case "task_cancelled":
          handlers.onTaskCancelled?.({ taskId });
          break;

        case "task_stale":
          handlers.onTaskStale?.({ taskId });
          break;

        case "done":
          handlers.onDone?.({ taskId, conversationId: data.conversationId });
          resolve();
          break;
      }
    }
  }

  // Stream ended without explicit "done" event
  resolve();
}

/**
 * Parse SSE stream from POST /api/chat.
 * Uses ReadableStream reader (not EventSource) because we need POST.
 */
export function streamChat(
  message: string,
  handlers: StreamHandlers,
  signal?: AbortSignal,
  images?: string[],
  files?: { filename: string; data: string }[],
  conversationId?: number,
  mode?: string
): Promise<void> {
  return new Promise(async (resolve, reject) => {
    try {
      const body: Record<string, unknown> = { message };
      if (conversationId !== undefined) {
        body.conversationId = conversationId;
      }
      if (mode) {
        body.mode = mode;
      }
      if (images && images.length > 0) {
        body.images = images;
      }
      if (files && files.length > 0) {
        body.files = files;
      }
      const res = await fetch(`${BASE_URL}/api/chat`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal,
      });

      if (!res.ok) {
        const body = await res.json().catch(() => null);
        const err = new Error(body?.detail || `Chat API error ${res.status}`);
        handlers.onError?.(err);
        reject(err);
        return;
      }

      const reader = res.body?.getReader();
      if (!reader) {
        const err = new Error("No response body");
        handlers.onError?.(err);
        reject(err);
        return;
      }

      await parseSSEStream(reader, handlers, resolve, reject);
    } catch (err: any) {
      if (err.name === "AbortError") {
        resolve(); // Cancelled, not an error
        return;
      }
      handlers.onError?.(err instanceof Error ? err : new Error(String(err)));
      reject(err);
    }
  });
}

/**
 * Reconnect to a running task's SSE stream (GET /api/tasks/{id}/stream).
 * Used when the page reloads while a pipeline is running in the background.
 */
export function reconnectStream(
  taskId: number,
  handlers: StreamHandlers,
  signal?: AbortSignal
): Promise<void> {
  return new Promise(async (resolve, reject) => {
    try {
      const res = await fetch(`${BASE_URL}/api/tasks/${taskId}/stream`, {
        credentials: "include",
        signal,
      });

      if (!res.ok) {
        const err = new Error(`Reconnect API error ${res.status}`);
        handlers.onError?.(err);
        reject(err);
        return;
      }

      const reader = res.body?.getReader();
      if (!reader) {
        const err = new Error("No response body");
        handlers.onError?.(err);
        reject(err);
        return;
      }

      await parseSSEStream(reader, handlers, resolve, reject);
    } catch (err: any) {
      if (err.name === "AbortError") {
        resolve();
        return;
      }
      handlers.onError?.(err instanceof Error ? err : new Error(String(err)));
      reject(err);
    }
  });
}

/**
 * Start a pipeline after user confirms parameters.
 * POST /api/tasks/start → SSE stream.
 * Supports both customer_acquisition and email_craft.
 */
export function startConfirmedPipeline(
  params: {
    industry?: string;
    country?: string;
    keywords?: string[];
    num?: number;
    confirmType?: string;
    language?: string;
    files?: { filename: string; data: string }[];
    leadIds?: number[];
    sourceTaskId?: number;
    conversationId?: number;
    delayMin?: number;
    delayMax?: number;
    dailyLimit?: number;
    dryRun?: boolean;
    sendMode?: string;
    customerTypes?: string[];
    userRequirements?: string;
  },
  handlers: StreamHandlers,
  signal?: AbortSignal
): Promise<void> {
  return new Promise(async (resolve, reject) => {
    try {
      const res = await fetch(`${BASE_URL}/api/tasks/start`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(params),
        signal,
      });

      if (!res.ok) {
        const body = await res.json().catch(() => null);
        const err = new Error(body?.detail || `Start pipeline API error ${res.status}`);
        handlers.onError?.(err);
        reject(err);
        return;
      }

      const reader = res.body?.getReader();
      if (!reader) {
        const err = new Error("No response body");
        handlers.onError?.(err);
        reject(err);
        return;
      }

      await parseSSEStream(reader, handlers, resolve, reject);
    } catch (err: any) {
      if (err.name === "AbortError") {
        resolve();
        return;
      }
      handlers.onError?.(err instanceof Error ? err : new Error(String(err)));
      reject(err);
    }
  });
}
