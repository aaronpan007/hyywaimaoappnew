"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  Check,
  CheckSquare,
  Copy,
  Download,
  ExternalLink,
  Loader2,
  Pencil,
  Search,
  Send,
  Trash2,
  X,
} from "lucide-react";
import { deleteLeads, exportLeadsExcel, getLeads, updateLead, updateLeadEmail, type GetLeadsParams } from "@/lib/api";
import type { EmailSettings, Lead } from "@/types";

interface CustomerListPageProps {
  onGenerateEmails?: (leadIds: number[], language: string) => void;
  emailSettings?: EmailSettings | null;
  onGoToEmailConfig?: () => void;
  onSendEmails?: (
    leadIds: number[],
    settings: {
      delayMin: number;
      delayMax: number;
      dailyLimit: number;
      dryRun: false;
      sendMode: "immediate" | "auto";
    }
  ) => void;
}

type EmailStatusKey =
  | "unwritten"
  | "draft"
  | "sending"
  | "sent"
  | "delivered"
  | "failed"
  | "bounced"
  | "complained";
type StatusFilter = "all" | "unwritten" | "draft" | "sent" | "failed";
type StatusDisplayKey = StatusFilter | EmailStatusKey;

const statusFilters: StatusFilter[] = [
  "all",
  "unwritten",
  "draft",
  "sent",
  "failed",
];

const statusConfig: Record<
  StatusDisplayKey,
  { label: string; className: string }
> = {
  all: { label: "全部", className: "bg-gray-100 text-text-secondary border-gray-200" },
  unwritten: { label: "未写", className: "bg-gray-100 text-gray-700 border-gray-200" },
  draft: { label: "已写", className: "bg-blue-50 text-brand-blue border-blue-100" },
  sending: { label: "发送中", className: "bg-amber-50 text-amber-700 border-amber-100" },
  sent: { label: "已发送", className: "bg-green-50 text-green-700 border-green-100" },
  delivered: { label: "已送达", className: "bg-emerald-50 text-emerald-700 border-emerald-100" },
  failed: { label: "失败", className: "bg-red-50 text-red-600 border-red-100" },
  bounced: { label: "退信", className: "bg-orange-50 text-orange-700 border-orange-100" },
  complained: { label: "投诉", className: "bg-rose-50 text-rose-700 border-rose-100" },
};

function normalizeEmailStatus(status?: string): EmailStatusKey {
  const value = (status || "").toLowerCase();
  if (value === "failed") return "failed";
  if (value === "bounced") return "bounced";
  if (value === "complained") return "complained";
  if (value === "delivered") return "delivered";
  if (value === "sending" || value === "pending") return "sending";
  if (value === "sent") return "sent";
  if (value === "unwritten") return "unwritten";
  return "draft";
}

function getStatusFilterKey(status?: string): Exclude<StatusFilter, "all"> | null {
  const normalized = normalizeEmailStatus(status);
  if (normalized === "delivered") return "sent";
  if (normalized === "bounced" || normalized === "complained") return "failed";
  if (normalized === "sending") return null;
  return normalized;
}

function getScoreClass(score: number) {
  if (score >= 80) return "text-green-700 bg-green-50 border-green-200";
  if (score >= 60) return "text-yellow-700 bg-yellow-50 border-yellow-200";
  return "text-red-600 bg-red-50 border-red-200";
}

function displayDomain(url?: string) {
  if (!url) return "-";
  try {
    const hostname = new URL(url.startsWith("http") ? url : `https://${url}`).hostname;
    return hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

function TruncatedCell({ value, className = "" }: { value?: string | null; className?: string }) {
  return (
    <span className={`block truncate ${className}`} title={value || ""}>
      {value || "-"}
    </span>
  );
}

export default function CustomerListPage({
  onGenerateEmails,
  emailSettings,
  onGoToEmailConfig,
  onSendEmails,
}: CustomerListPageProps) {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  const [selectedLeadIds, setSelectedLeadIds] = useState<Set<number>>(new Set());
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [sortBy, setSortBy] = useState("created_at");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [isLoading, setIsLoading] = useState(false);
  const debounceTimer = useRef<ReturnType<typeof setTimeout>>();
  const [copiedEmailId, setCopiedEmailId] = useState<number | null>(null);
  const [editingCell, setEditingCell] = useState<{ leadId: number; field: string; scope: "table" | "drawer" } | null>(null);
  const [editingValue, setEditingValue] = useState("");
  const [editingEmailField, setEditingEmailField] = useState<"emailSubject" | "emailBody" | null>(null);
  const [editingEmailValue, setEditingEmailValue] = useState("");
  const [isSavingEmail, setIsSavingEmail] = useState(false);
  const [editingEmailError, setEditingEmailError] = useState("");
  const justFinishedRef = useRef(false);
  const [selectedLanguage, setSelectedLanguage] = useState<"en" | "cn">("en");
  const [showSendConfirm, setShowSendConfirm] = useState(false);
  const [sendDelayMin, setSendDelayMin] = useState(60);
  const [sendDelayMax, setSendDelayMax] = useState(120);
  const [sendDailyLimit, setSendDailyLimit] = useState(50);
  const [sendDryRun] = useState(false);
  const [sendMode, setSendMode] = useState<"immediate" | "auto">("auto");
  const pageSize = 20;

  useEffect(() => {
    if (debounceTimer.current) clearTimeout(debounceTimer.current);
    debounceTimer.current = setTimeout(() => {
      setDebouncedSearch(searchQuery);
      setPage(1);
    }, 250);
    return () => {
      if (debounceTimer.current) clearTimeout(debounceTimer.current);
    };
  }, [searchQuery]);

  const fetchLeads = useCallback(async () => {
    setIsLoading(true);
    try {
      const params: GetLeadsParams = {
        page,
        pageSize,
        sortBy,
        sortOrder,
      };
      if (debouncedSearch) params.search = debouncedSearch;
      const res = await getLeads(params);
      setLeads(res.items);
      setTotal(res.total);
      setTotalPages(Math.max(res.totalPages, 1));
    } catch (error) {
      console.error("Failed to load customer list:", error);
      setLeads([]);
      setTotal(0);
      setTotalPages(1);
    } finally {
      setIsLoading(false);
    }
  }, [page, pageSize, sortBy, sortOrder, debouncedSearch]);

  useEffect(() => {
    fetchLeads();
  }, [fetchLeads]);

  const filteredLeads = useMemo(() => {
    if (statusFilter === "all") return leads;
    return leads.filter((lead) => getStatusFilterKey(lead.emailStatus) === statusFilter);
  }, [leads, statusFilter]);

  // Auto-select all failed customers when switching to "失败" filter
  useEffect(() => {
    if (statusFilter === "failed" && filteredLeads.length > 0 && selectedLeadIds.size === 0) {
      setSelectedLeadIds(new Set(filteredLeads.map((lead) => lead.id)));
    }
  }, [statusFilter, filteredLeads]);

  const selectedCount = selectedLeadIds.size;
  const allVisibleSelected =
    filteredLeads.length > 0 && filteredLeads.every((lead) => selectedLeadIds.has(lead.id));
  const selectedVisibleLeads = useMemo(
    () => leads.filter((lead) => selectedLeadIds.has(lead.id)),
    [leads, selectedLeadIds]
  );
  const sendStats = useMemo(() => {
    return selectedVisibleLeads.reduce(
      (acc, lead) => {
        const status = normalizeEmailStatus(lead.emailStatus);
        const hasEmail = Boolean((lead.email || "").trim());
        const hasDraft = Boolean((lead.emailSubject || "").trim() && (lead.emailBody || "").trim());
        if ((status === "draft" || status === "failed") && hasEmail && hasDraft) {
          acc.sendable += 1;
          if (status === "failed") acc.retryable += 1;
        } else if (!hasEmail) {
          acc.missingEmail += 1;
        } else if (!hasDraft || status === "unwritten") {
          acc.missingDraft += 1;
        } else if (status === "sent" || status === "delivered") {
          acc.alreadySent += 1;
        } else {
          acc.notSendable += 1;
        }
        return acc;
      },
      {
        sendable: 0,
        retryable: 0,
        missingEmail: 0,
        missingDraft: 0,
        alreadySent: 0,
        notSendable: 0,
      }
    );
  }, [selectedVisibleLeads]);
  const canSendSelected = Boolean(onSendEmails && sendStats.sendable > 0);
  const mailDomain = (emailSettings?.mailDomain || "clientconnet.com").replace(/^@+/, "");
  const senderName = (emailSettings?.senderName || "").trim();
  const fromEmailPrefix = (emailSettings?.fromEmailPrefix || "").trim().replace(/^@+/, "").split("@", 1)[0];
  const replyToEmail = (emailSettings?.replyToEmail || "").trim();
  const fromEmail = fromEmailPrefix ? `${fromEmailPrefix}@${mailDomain}` : "未配置";
  const hasConfirmedEmailConfig = Boolean(emailSettings?.configuredAt);

  const toggleLeadSelection = (leadId: number) => {
    setSelectedLeadIds((current) => {
      const next = new Set(current);
      if (next.has(leadId)) {
        next.delete(leadId);
      } else {
        next.add(leadId);
      }
      return next;
    });
  };

  const toggleVisibleSelection = () => {
    setSelectedLeadIds((current) => {
      const next = new Set(current);
      if (allVisibleSelected) {
        filteredLeads.forEach((lead) => next.delete(lead.id));
      } else {
        filteredLeads.forEach((lead) => next.add(lead.id));
      }
      return next;
    });
  };

  const statusCounts = useMemo(() => {
    return leads.reduce(
      (acc, lead) => {
        const status = getStatusFilterKey(lead.emailStatus);
        if (status) acc[status] += 1;
        return acc;
      },
      {
        unwritten: 0,
        draft: 0,
        sent: 0,
        failed: 0,
      } as Record<Exclude<StatusFilter, "all">, number>
    );
  }, [leads]);

  const handleSort = (field: string) => {
    if (sortBy === field) {
      setSortOrder((current) => (current === "desc" ? "asc" : "desc"));
    } else {
      setSortBy(field);
      setSortOrder("desc");
    }
    setPage(1);
  };

  const handleExport = async () => {
    try {
      await exportLeadsExcel({ search: debouncedSearch || undefined });
    } catch {
      alert("客户名单导出失败，请稍后重试");
    }
  };

  const handleGenerateEmails = () => {
    if (!onGenerateEmails || selectedCount === 0) return;
    onGenerateEmails(Array.from(selectedLeadIds), selectedLanguage);
  };

  const handleOpenSendConfirm = () => {
    if (!canSendSelected) return;
    if (!senderName || !fromEmailPrefix || !hasConfirmedEmailConfig) {
      alert("首次发送前请先确认邮箱配置。系统已根据公司资料推荐默认值，您可以直接修改后保存。");
      onGoToEmailConfig?.();
      return;
    }
    setShowSendConfirm(true);
  };

  const handleConfirmSend = () => {
    if (!onSendEmails || !canSendSelected) return;
    onSendEmails(Array.from(selectedLeadIds), {
      delayMin: sendDelayMin,
      delayMax: Math.max(sendDelayMin, sendDelayMax),
      dailyLimit: sendDailyLimit,
      dryRun: false,
      sendMode,
    });
    setShowSendConfirm(false);
  };

  const handleDeleteSelected = async () => {
    if (selectedCount === 0) return;
    const leadIds = Array.from(selectedLeadIds);
    const confirmed = window.confirm(`确定删除选中的 ${leadIds.length} 个客户吗？相关开发信记录也会一起删除。`);
    if (!confirmed) return;

    try {
      await deleteLeads(leadIds);
      setSelectedLeadIds(new Set());
      if (selectedLead && leadIds.includes(selectedLead.id)) {
        setSelectedLead(null);
      }
      await fetchLeads();
    } catch (error) {
      console.error("Failed to delete leads:", error);
      alert("删除客户失败，请稍后重试");
    }
  };

  type EditableField = "contactName" | "email" | "userNote";

  const fieldKeyMap: Record<string, string> = {
    contactName: "contact_name",
    email: "email",
    userNote: "user_note",
  };

  const handleSaveCell = async (leadId: number, field: EditableField) => {
    const value = editingValue.trim();
    if (!value) {
      setEditingCell(null);
      justFinishedRef.current = true;
      setTimeout(() => { justFinishedRef.current = false; }, 200);
      return;
    }
    try {
      await updateLead(leadId, { [field]: value });
      setLeads((prev) =>
        prev.map((l) => (l.id === leadId ? { ...l, [field]: value } : l))
      );
      setSelectedLead((current) =>
        current?.id === leadId ? { ...current, [field]: value } : current
      );
    } catch {
      // 静默失败
    } finally {
      setEditingCell(null);
      justFinishedRef.current = true;
      setTimeout(() => { justFinishedRef.current = false; }, 200);
    }
  };

  const startEditing = (
    leadId: number,
    field: EditableField,
    currentValue: string,
    scope: "table" | "drawer" = "table"
  ) => {
    setEditingCell({ leadId, field, scope });
    setEditingValue(currentValue || "");
  };

  const finishEditing = () => {
    setEditingCell(null);
    justFinishedRef.current = true;
    setTimeout(() => { justFinishedRef.current = false; }, 200);
  };

  const startEditingEmail = (field: "emailSubject" | "emailBody", currentValue?: string | null) => {
    setEditingEmailField(field);
    setEditingEmailValue(currentValue || "");
    setEditingEmailError("");
  };

  const finishEditingEmail = () => {
    setEditingEmailField(null);
    setEditingEmailValue("");
    setEditingEmailError("");
  };

  const closeDrawer = () => {
    setSelectedLead(null);
    setEditingCell(null);
    setEditingValue("");
    finishEditingEmail();
  };

  const handleSaveEmailField = async () => {
    if (!selectedLead || !editingEmailField || isSavingEmail) return;
    const value = editingEmailValue.trim();
    if (!value) {
      finishEditingEmail();
      return;
    }

    setIsSavingEmail(true);
    setEditingEmailError("");
    try {
      const updated = await updateLeadEmail(selectedLead.id, { [editingEmailField]: value });
      const nextEmailStatus = updated.sendStatus || selectedLead.emailStatus;
      setLeads((prev) =>
        prev.map((lead) =>
          lead.id === selectedLead.id
            ? {
                ...lead,
                emailSubject: updated.emailSubject,
                emailBody: updated.emailBody,
                emailStatus: nextEmailStatus,
              }
            : lead
        )
      );
      setSelectedLead((current) =>
        current?.id === selectedLead.id
          ? {
              ...current,
              emailSubject: updated.emailSubject,
              emailBody: updated.emailBody,
              emailStatus: nextEmailStatus,
            }
          : current
      );
      finishEditingEmail();
    } catch (error) {
      console.error("Failed to update email content:", error);
      const message = error instanceof Error ? error.message : "";
      setEditingEmailError(
        message.includes("Not Found")
          ? "保存失败：后端邮件编辑接口未加载，或当前客户还没有开发信。请重启后端后重试。"
          : message || "保存失败，请稍后重试"
      );
    } finally {
      setIsSavingEmail(false);
    }
  };

  const isEditing = (leadId: number, field: string, scope: "table" | "drawer" = "table") =>
    editingCell?.leadId === leadId && editingCell.field === field && editingCell.scope === scope;

  const EditableCell = ({ lead, field, displayValue }: { lead: Lead; field: EditableField; displayValue?: string | null }) => {
    if (isEditing(lead.id, field, "table")) {
      return (
        <input
          autoFocus
          value={editingValue}
          onChange={(e) => setEditingValue(e.target.value)}
          onBlur={() => handleSaveCell(lead.id, field)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleSaveCell(lead.id, field);
            if (e.key === "Escape") finishEditing();
          }}
          className="w-full rounded border border-brand-blue/40 px-2 py-0.5 text-[13px] text-text-primary outline-none"
        />
      );
    }
    return (
      <div
        className="group/cell flex items-center gap-1"
        onMouseDown={(e) => { e.preventDefault(); e.stopPropagation(); }}
        onClick={(e) => {
          e.stopPropagation();
          startEditing(lead.id, field, displayValue || "", "table");
        }}
      >
        <TruncatedCell value={displayValue} className="flex-1" />
        <Pencil size={12} className="shrink-0 opacity-0 transition-opacity group-hover/cell:opacity-30 hover:!opacity-70" />
      </div>
    );
  };

  const EditableDetailField = ({ label, lead, field, displayValue }: { label: string; lead: Lead; field: EditableField; displayValue?: string | null }) => {
    const active = isEditing(lead.id, field, "drawer");

    return (
      <div
        className="rounded-lg border border-text-border bg-surface-input px-3 py-2"
        onClick={(e) => e.stopPropagation()}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="text-[12px] text-text-tertiary">{label}</div>
        <div className="mt-1">
          {active ? (
            <div className="flex items-center gap-1.5">
              <input
                autoFocus
                value={editingValue}
                onChange={(e) => setEditingValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleSaveCell(lead.id, field);
                  if (e.key === "Escape") finishEditing();
                }}
                className="min-w-0 flex-1 rounded border border-brand-blue/40 bg-white px-2 py-0.5 text-[13px] text-text-primary outline-none"
              />
              <button
                type="button"
                onClick={() => handleSaveCell(lead.id, field)}
                className="flex h-6 w-6 shrink-0 items-center justify-center rounded text-brand-blue transition-colors hover:bg-blue-50"
                aria-label="保存"
              >
                <Check size={14} />
              </button>
              <button
                type="button"
                onClick={finishEditing}
                className="flex h-6 w-6 shrink-0 items-center justify-center rounded text-text-tertiary transition-colors hover:bg-gray-100"
                aria-label="取消"
              >
                <X size={14} />
              </button>
            </div>
          ) : (
            <button
              type="button"
              onPointerDown={(e) => {
                e.preventDefault();
                e.stopPropagation();
                startEditing(lead.id, field, displayValue || "", "drawer");
              }}
              onClick={(e) => e.stopPropagation()}
              className="group/cell flex w-full items-center gap-1 text-left"
            >
              <TruncatedCell value={displayValue} className="flex-1" />
              <Pencil size={12} className="shrink-0 opacity-0 transition-opacity group-hover/cell:opacity-30 hover:!opacity-70" />
            </button>
          )}
        </div>
      </div>
    );
  };

  const EditableEmailSection = ({
    title,
    field,
    content,
    compact = false,
    action,
  }: {
    title: string;
    field: "emailSubject" | "emailBody";
    content?: string | null;
    compact?: boolean;
    action?: React.ReactNode;
  }) => {
    const active = editingEmailField === field;

    return (
      <section className="mt-5" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-[14px] font-semibold text-text-primary">{title}</h3>
          <div className="flex items-center gap-2">
            {action}
            {!active && (
              <button
                type="button"
                onClick={() => startEditingEmail(field, content)}
                className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-[13px] text-text-secondary transition-colors hover:bg-gray-100"
              >
                <Pencil size={13} />
                修改
              </button>
            )}
          </div>
        </div>
        <div className="mt-2">
          {active ? (
            <div className="rounded-lg border border-brand-blue/30 bg-white p-2">
              {field === "emailSubject" ? (
                <input
                  autoFocus
                  value={editingEmailValue}
                  onChange={(e) => setEditingEmailValue(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") handleSaveEmailField();
                    if (e.key === "Escape") finishEditingEmail();
                  }}
                  className="w-full rounded-md border border-transparent px-2 py-1 text-[13px] text-text-primary outline-none focus:border-brand-blue/30"
                />
              ) : (
                <textarea
                  autoFocus
                  value={editingEmailValue}
                  onChange={(e) => setEditingEmailValue(e.target.value)}
                  onKeyDown={(e) => {
                    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") handleSaveEmailField();
                    if (e.key === "Escape") finishEditingEmail();
                  }}
                  className="min-h-[300px] w-full resize-y rounded-md border border-transparent px-2 py-1 text-[13px] leading-relaxed text-text-primary outline-none focus:border-brand-blue/30"
                />
              )}
              <div className="mt-2 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={finishEditingEmail}
                  disabled={isSavingEmail}
                  className="rounded-md px-3 py-1 text-[13px] text-text-secondary transition-colors hover:bg-gray-100 disabled:opacity-50"
                >
                  取消
                </button>
                <button
                  type="button"
                  onClick={handleSaveEmailField}
                  disabled={isSavingEmail}
                  className="inline-flex items-center gap-1 rounded-md bg-brand-blue px-3 py-1 text-[13px] font-medium text-white transition-colors hover:bg-brand-blue/90 disabled:opacity-50"
                >
                  {isSavingEmail && <Loader2 size={13} className="animate-spin" />}
                  保存
                </button>
              </div>
              {editingEmailError && (
                <div className="mt-2 rounded-md bg-red-50 px-2 py-1 text-[12px] text-red-600">
                  {editingEmailError}
                </div>
              )}
            </div>
          ) : (
            <button
              type="button"
              onClick={() => startEditingEmail(field, content)}
              className={`block w-full whitespace-pre-wrap rounded-lg border border-text-border bg-white p-3 text-left text-[13px] leading-relaxed text-text-secondary transition-colors hover:border-brand-blue/30 hover:bg-brand-blue-light/30 ${
                compact ? "min-h-[44px]" : "min-h-[96px]"
              }`}
            >
              {content || "-"}
            </button>
          )}
        </div>
      </section>
    );
  };

  const startIndex = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const endIndex = Math.min(page * pageSize, total);

  return (
    <section className="flex h-full flex-col bg-white">
      <div className="shrink-0 border-b border-text-border px-6 py-5">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h1 className="text-[20px] font-semibold text-text-primary">客户名单</h1>
            <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px] text-text-secondary">
              <span>共 {total} 条客户</span>
              <span className="text-text-tertiary">/</span>
              <span>当前页未写 {statusCounts.unwritten}</span>
              <span>已写 {statusCounts.draft}</span>
              <span>已发送 {statusCounts.sent}</span>
              <span>失败 {statusCounts.failed}</span>
            </div>
          </div>
          <button
            onClick={handleExport}
            className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-text-border px-3 text-[13px] font-medium text-text-secondary transition-colors hover:bg-gray-50"
          >
            <Download size={15} />
            导出 Excel
          </button>
        </div>
      </div>

      <div className="shrink-0 border-b border-text-border px-6 py-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="relative">
            <Search
              size={15}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-text-tertiary"
            />
            <input
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="搜索公司、网站、国家、行业、邮箱"
              className="h-9 w-[360px] rounded-lg border border-transparent bg-surface-input pl-9 pr-3 text-[13px] text-text-primary outline-none transition-colors placeholder:text-text-tertiary focus:border-brand-blue/40"
            />
          </div>

          <div className="flex flex-wrap items-center gap-1 rounded-lg bg-surface-input p-1">
            {statusFilters.map((status) => (
              <button
                key={status}
                onClick={() => setStatusFilter(status)}
                className={`h-7 rounded-md px-3 text-[13px] transition-colors ${
                  statusFilter === status
                    ? "bg-white text-brand-blue shadow-sm"
                    : "text-text-secondary hover:text-text-primary"
                }`}
              >
                {statusConfig[status].label}
              </button>
            ))}
          </div>
        </div>
        {selectedCount > 0 && (
          <div className={`mt-3 flex items-center justify-between rounded-lg border px-3 py-2 ${
            statusFilter === "failed" ? "border-red-300 bg-red-50" : "border-brand-blue/20 bg-brand-blue-light"
          }`}>
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px] text-brand-blue">
              <CheckSquare size={15} />
              <span>已选择 {selectedCount} 个客户</span>
              {statusFilter === "failed" && sendStats.retryable > 0 && (
                <span className="ml-2 rounded bg-red-100 px-2 py-0.5 text-[12px] font-medium text-red-700">
                  已选中 {sendStats.retryable} 个失败客户，点击「发送邮件」即可重发
                </span>
              )}
              <span className="text-text-tertiary">/</span>
              <span>可发送 {sendStats.sendable}</span>
              <span>已发送跳过 {sendStats.alreadySent}</span>
              <span>缺邮箱 {sendStats.missingEmail}</span>
              <span>缺开发信 {sendStats.missingDraft}</span>
              <span>需处理 {sendStats.notSendable}</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-0.5 rounded-md bg-white/60 p-0.5">
                <button
                  onClick={() => setSelectedLanguage("en")}
                  className={`rounded px-2 py-0.5 text-[12px] transition-colors ${
                    selectedLanguage === "en"
                      ? "bg-brand-blue text-white"
                      : "text-text-secondary hover:text-text-primary"
                  }`}
                >
                  EN
                </button>
                <button
                  onClick={() => setSelectedLanguage("cn")}
                  className={`rounded px-2 py-0.5 text-[12px] transition-colors ${
                    selectedLanguage === "cn"
                      ? "bg-brand-blue text-white"
                      : "text-text-secondary hover:text-text-primary"
                  }`}
                >
                  中文
                </button>
              </div>
              <button
                onClick={() => setSelectedLeadIds(new Set())}
                className="rounded-md px-2 py-1 text-[13px] text-text-secondary transition-colors hover:bg-white/70"
              >
                清空选择
              </button>
              <button
                onClick={handleDeleteSelected}
                className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-[13px] text-red-600 transition-colors hover:bg-red-50"
              >
                <Trash2 size={14} />
                删除客户
              </button>
              <button
                onClick={handleGenerateEmails}
                disabled={!onGenerateEmails}
                className="rounded-md bg-brand-blue px-3 py-1 text-[13px] font-medium text-white transition-colors hover:bg-brand-blue/90 disabled:cursor-not-allowed disabled:opacity-50"
              >
                生成开发信
              </button>
              <button
                onClick={handleOpenSendConfirm}
                disabled={!canSendSelected}
                title={!canSendSelected ? "选中的客户暂无可发送开发信" : "发送选中的开发信"}
                className="inline-flex items-center gap-1 rounded-md bg-emerald-600 px-3 py-1 text-[13px] font-medium text-white transition-colors hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Send size={14} />
                发送邮件
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="min-h-0 flex-1 overflow-auto">
        {isLoading ? (
          <div className="flex h-48 items-center justify-center gap-2 text-[14px] text-text-tertiary">
            <Loader2 size={16} className="animate-spin" />
            加载客户名单...
          </div>
        ) : (
          <table className="min-w-[1230px] w-full table-fixed text-[13px]">
            <colgroup>
              <col className="w-[52px]" />
              <col className="w-[190px]" />
              <col className="w-[170px]" />
              <col className="w-[120px]" />
              <col className="w-[130px]" />
              <col className="w-[120px]" />
              <col className="w-[130px]" />
              <col className="w-[190px]" />
              <col className="w-[210px]" />
              <col className="w-[110px]" />
              <col className="w-[100px]" />
            </colgroup>
            <thead className="sticky top-0 z-10 bg-white">
              <tr className="border-b border-text-border text-left">
                <th className="px-4 py-3 font-semibold text-gray-700">
                  <input
                    type="checkbox"
                    checked={allVisibleSelected}
                    onChange={toggleVisibleSelection}
                    className="accent-brand-blue"
                    aria-label="选择当前页客户"
                  />
                </th>
                <th className="px-4 py-3 font-semibold text-gray-700">公司名称</th>
                <th className="px-4 py-3 font-semibold text-gray-700">网站</th>
                <th className="px-4 py-3 font-semibold text-gray-700">国家/地区</th>
                <th className="px-4 py-3 font-semibold text-gray-700">行业</th>
                <th className="px-4 py-3 font-semibold text-gray-700">公司角色</th>
                <th className="px-4 py-3 font-semibold text-gray-700">联系人</th>
                <th className="px-4 py-3 font-semibold text-gray-700">邮箱</th>
                <th className="px-4 py-3 font-semibold text-gray-700">来源/备注</th>
                <th className="px-4 py-3 font-semibold text-gray-700">
                  <button
                    onClick={() => handleSort("match_score")}
                    className="flex items-center gap-1"
                  >
                    匹配度
                    {sortBy === "match_score" &&
                      (sortOrder === "desc" ? <ChevronDown size={14} /> : <ChevronUp size={14} />)}
                  </button>
                </th>
                <th className="px-4 py-3 font-semibold text-gray-700">开发信状态</th>
              </tr>
            </thead>
            <tbody>
              {filteredLeads.map((lead, index) => {
                const status = normalizeEmailStatus(lead.emailStatus);
                return (
                  <tr
                    key={lead.id}
                    onClick={() => {
                      if (editingCell?.leadId === lead.id || justFinishedRef.current) return;
                      setSelectedLead(lead);
                    }}
                    className={`h-[62px] ${editingCell?.leadId !== lead.id ? "cursor-pointer hover:bg-gray-50" : ""} border-b border-gray-100 transition-colors ${
                      index % 2 === 1 ? "bg-gray-50/30" : ""
                    }`}
                  >
                    <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={selectedLeadIds.has(lead.id)}
                        onChange={() => toggleLeadSelection(lead.id)}
                        className="accent-brand-blue"
                        aria-label={`选择 ${lead.companyName}`}
                      />
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className="block max-w-full truncate text-left font-medium text-brand-blue hover:underline"
                        title={lead.companyName || ""}
                      >
                        {lead.companyName || "-"}
                      </span>
                    </td>
                    <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                      {lead.website ? (
                        <a
                          href={lead.website.startsWith("http") ? lead.website : `https://${lead.website}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex max-w-full items-center gap-1 text-brand-blue hover:underline"
                          title={lead.website}
                        >
                          <span className="truncate">{displayDomain(lead.website)}</span>
                          <ExternalLink size={12} className="shrink-0 opacity-60" />
                        </a>
                      ) : (
                        <span className="text-text-tertiary">-</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-text-primary">
                      <TruncatedCell value={lead.country} />
                    </td>
                    <td className="px-4 py-3 text-text-secondary">
                      <TruncatedCell value={lead.industry} />
                    </td>
                    <td className="px-4 py-3 text-text-secondary">
                      <TruncatedCell value={lead.companyRole} />
                    </td>
                    <td className="px-4 py-3 text-text-primary">
                      <EditableCell lead={lead} field="contactName" displayValue={lead.contactName} />
                    </td>
                    <td className="px-4 py-3 text-text-secondary">
                      <EditableCell lead={lead} field="email" displayValue={lead.email} />
                    </td>
                    <td className="px-4 py-3 text-text-secondary">
                      <EditableCell lead={lead} field="userNote" displayValue={lead.userNote || lead.sourceList} />
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-block rounded-md border px-2 py-0.5 text-[12px] font-medium ${getScoreClass(lead.matchScore)}`}>
                        {lead.matchScore.toFixed(1)}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex rounded-full border px-2.5 py-0.5 text-[12px] font-medium ${statusConfig[status].className}`}>
                        {statusConfig[status].label}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}

        {!isLoading && filteredLeads.length === 0 && (
          <div className="flex h-48 items-center justify-center text-[14px] text-text-tertiary">
            暂无客户记录
          </div>
        )}
      </div>

      <div className="flex shrink-0 items-center justify-between border-t border-text-border px-6 py-3">
        <span className="text-[13px] text-text-secondary">
          {total > 0 ? `显示 ${startIndex}-${endIndex} 条，共 ${total} 条` : "暂无数据"}
        </span>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setPage((current) => Math.max(1, current - 1))}
            disabled={page === 1 || isLoading}
            className="inline-flex h-8 items-center gap-1 rounded-lg px-3 text-[13px] text-text-secondary transition-colors hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <ChevronLeft size={14} />
            上一页
          </button>
          <span className="px-3 text-[13px] text-text-secondary">
            {page} / {totalPages}
          </span>
          <button
            onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
            disabled={page === totalPages || isLoading}
            className="inline-flex h-8 items-center gap-1 rounded-lg px-3 text-[13px] text-text-secondary transition-colors hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-40"
          >
            下一页
            <ChevronRight size={14} />
          </button>
        </div>
      </div>

      {showSendConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 px-4">
          <div className="w-full max-w-[520px] rounded-xl bg-white shadow-2xl">
            <div className="border-b border-text-border px-5 py-4">
              <h2 className="text-[17px] font-semibold text-text-primary">确认发送开发信</h2>
              <p className="mt-1 text-[13px] text-text-secondary">
                本次将发送 {sendStats.sendable} 封开发信
              </p>
            </div>

            <div className="space-y-5 px-5 py-4">
              <div className="grid grid-cols-3 gap-2">
                {[
                  ["可发送", sendStats.sendable],
                  ["已发送跳过", sendStats.alreadySent],
                  ["缺邮箱", sendStats.missingEmail],
                  ["缺开发信", sendStats.missingDraft],
                  ["失败可重发", sendStats.retryable],
                  ["需处理", sendStats.notSendable],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-lg border border-text-border px-2 py-2 text-center">
                    <div className="text-[16px] font-semibold text-text-primary">{value}</div>
                    <div className="mt-0.5 text-[11px] text-text-tertiary">{label}</div>
                  </div>
                ))}
              </div>

              <div className="rounded-lg bg-amber-50 px-3 py-2 text-[13px] leading-5 text-amber-800">
                已发送、已送达、退信/投诉、缺邮箱或缺开发信的客户会自动跳过。
              </div>

              <div className="rounded-lg border border-text-border px-3 py-3">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <div className="text-[13px] font-medium text-gray-700">发件信息</div>
                  {onGoToEmailConfig && (
                    <button
                      type="button"
                      onClick={() => {
                        setShowSendConfirm(false);
                        onGoToEmailConfig();
                      }}
                      className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-[12px] text-brand-blue transition-colors hover:bg-blue-50"
                    >
                      <Pencil size={13} />
                      修改
                    </button>
                  )}
                </div>
                <div className="space-y-1.5 text-[13px] text-text-secondary">
                  <div className="flex justify-between gap-3">
                    <span className="shrink-0 text-text-tertiary">发件人</span>
                    <span className="truncate text-text-primary">{senderName || "未配置"}</span>
                  </div>
                  <div className="flex justify-between gap-3">
                    <span className="shrink-0 text-text-tertiary">发件邮箱</span>
                    <span className="truncate text-text-primary">{fromEmail}</span>
                  </div>
                  <div className="flex justify-between gap-3">
                    <span className="shrink-0 text-text-tertiary">回复邮箱</span>
                    <span className="truncate text-text-primary">{replyToEmail || "未单独设置"}</span>
                  </div>
                </div>
              </div>

              <div>
                <div className="mb-2 text-[13px] font-medium text-gray-700">发送设置</div>
                <div className="grid grid-cols-2 gap-3">
                  <label className="text-[12px] text-text-secondary">
                    发送策略
                    <select
                      value={sendMode}
                      onChange={(e) => setSendMode(e.target.value as "immediate" | "auto")}
                      className="mt-1 h-9 w-full rounded-lg border border-text-border px-3 text-[13px] text-text-primary outline-none focus:border-brand-blue/40"
                    >
                      <option value="auto">按客户当地工作时间</option>
                      <option value="immediate">立即发送</option>
                    </select>
                  </label>
                  <label className="text-[12px] text-text-secondary">
                    每日上限
                    <input
                      type="number"
                      min={1}
                      max={500}
                      value={sendDailyLimit}
                      onChange={(e) => setSendDailyLimit(Number(e.target.value) || 1)}
                      className="mt-1 h-9 w-full rounded-lg border border-text-border px-3 text-[13px] text-text-primary outline-none focus:border-brand-blue/40"
                    />
                  </label>
                  <label className="text-[12px] text-text-secondary">
                    最小间隔（秒）
                    <input
                      type="number"
                      min={0}
                      max={600}
                      value={sendDelayMin}
                      onChange={(e) => setSendDelayMin(Number(e.target.value) || 0)}
                      className="mt-1 h-9 w-full rounded-lg border border-text-border px-3 text-[13px] text-text-primary outline-none focus:border-brand-blue/40"
                    />
                  </label>
                  <label className="text-[12px] text-text-secondary">
                    最大间隔（秒）
                    <input
                      type="number"
                      min={0}
                      max={600}
                      value={sendDelayMax}
                      onChange={(e) => setSendDelayMax(Number(e.target.value) || 0)}
                      className="mt-1 h-9 w-full rounded-lg border border-text-border px-3 text-[13px] text-text-primary outline-none focus:border-brand-blue/40"
                    />
                  </label>
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-2 border-t border-text-border px-5 py-4">
              <button
                onClick={() => setShowSendConfirm(false)}
                className="rounded-lg border border-text-border px-4 py-2 text-[13px] font-medium text-text-secondary transition-colors hover:bg-gray-50"
              >
                取消
              </button>
              <button
                onClick={handleConfirmSend}
                disabled={!canSendSelected}
                className="rounded-lg bg-emerald-600 px-4 py-2 text-[13px] font-medium text-white transition-colors hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                确认发送
              </button>
            </div>
          </div>
        </div>
      )}

      {selectedLead && (
        <div
          className="fixed inset-0 z-50 flex justify-end bg-black/25"
          onClick={() => {
            if (isSavingEmail || editingCell || justFinishedRef.current) return;
            closeDrawer();
          }}
        >
          <aside
            className="relative flex h-full w-full max-w-[640px] flex-col bg-white shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex shrink-0 items-start justify-between border-b border-text-border px-6 py-5">
              <div className="min-w-0">
                <h2 className="truncate text-[18px] font-semibold text-text-primary">
                  {selectedLead.companyName || "客户详情"}
                </h2>
                <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[13px] text-text-secondary">
                  <span>{selectedLead.country || "未知地区"}</span>
                  <span>{selectedLead.industry || "未知行业"}</span>
                  <span>{selectedLead.sourceList || "未知来源"}</span>
                </div>
              </div>
              <button
                onClick={closeDrawer}
                className="ml-4 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-text-secondary transition-colors hover:bg-gray-100"
              >
                <X size={18} />
              </button>
            </div>

            <div className="min-h-0 flex-1 overflow-auto px-6 py-5">
              <div className="grid grid-cols-2 gap-3 text-[13px]">
                <DetailField label="网站" value={selectedLead.website} />
                <DetailField label="公司角色" value={selectedLead.companyRole} />
                <EditableDetailField label="联系人" lead={selectedLead} field="contactName" displayValue={selectedLead.contactName} />
                <EditableDetailField label="邮箱" lead={selectedLead} field="email" displayValue={selectedLead.email} />
                <DetailField label="匹配度" value={selectedLead.matchScore.toFixed(1)} />
                <DetailField
                  label="开发信状态"
                  value={statusConfig[normalizeEmailStatus(selectedLead.emailStatus)].label}
                />
              </div>

              <DetailSection
                title="AI 分析摘要"
                content={selectedLead.aiSummary}
              />
              <DetailSection
                title="业务匹配点"
                content={selectedLead.businessMatch}
              />
              <DetailSection
                title="开发建议"
                content={selectedLead.outreachSuggestion}
              />
              <EditableEmailSection
                title="邮件主题"
                field="emailSubject"
                content={selectedLead.emailSubject}
                compact
              />
              <EditableEmailSection
                title="开发信正文"
                field="emailBody"
                content={selectedLead.emailBody}
                action={
                  <div className="flex items-center gap-2">
                    {onSendEmails && ["draft", "failed"].includes(normalizeEmailStatus(selectedLead.emailStatus)) && selectedLead.email && selectedLead.emailBody ? (
                      <button
                        onClick={() => {
                          setSelectedLeadIds(new Set([selectedLead.id]));
                          setShowSendConfirm(true);
                        }}
                        className="inline-flex items-center gap-1 rounded-md bg-emerald-600 px-3 py-1 text-[13px] font-medium text-white transition-colors hover:bg-emerald-700"
                      >
                        <Send size={14} />
                        发送这封
                      </button>
                    ) : null}
                    {onGenerateEmails ? (
                      <button
                        onClick={() => onGenerateEmails([selectedLead.id], selectedLanguage)}
                        className="rounded-md bg-brand-blue px-3 py-1 text-[13px] font-medium text-white transition-colors hover:bg-brand-blue/90"
                      >
                        重写开发信
                      </button>
                    ) : null}
                  </div>
                }
              />

              {selectedLead.emailBody && (
                <button
                  onClick={() => {
                    const text = [
                      selectedLead.emailSubject ? `Subject: ${selectedLead.emailSubject}` : null,
                      selectedLead.emailBody,
                    ].filter(Boolean).join("\n\n");
                    navigator.clipboard.writeText(text).catch(() => {});
                    setCopiedEmailId(selectedLead.id);
                    setTimeout(() => setCopiedEmailId(null), 2000);
                  }}
                  className="mt-4 inline-flex items-center gap-1.5 rounded-lg border border-text-border px-3 py-1.5 text-[13px] text-text-secondary transition-colors hover:bg-gray-50"
                >
                  {copiedEmailId === selectedLead.id ? (
                    <>
                      <Check size={14} className="text-green-600" />
                      <span className="text-green-600">已复制</span>
                    </>
                  ) : (
                    <>
                      <Copy size={14} />
                      复制邮件
                    </>
                  )}
                </button>
              )}
            </div>
          </aside>
        </div>
      )}
    </section>
  );
}

function DetailField({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="rounded-lg border border-text-border bg-surface-input px-3 py-2">
      <div className="text-[12px] text-text-tertiary">{label}</div>
      <div className="mt-1 truncate text-text-primary" title={value || ""}>
        {value || "-"}
      </div>
    </div>
  );
}

function DetailSection({
  title,
  content,
  compact = false,
  action,
}: {
  title: string;
  content?: string | null;
  compact?: boolean;
  action?: React.ReactNode;
}) {
  return (
    <section className="mt-5">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-[14px] font-semibold text-text-primary">{title}</h3>
        {action}
      </div>
      <div
        className={`mt-2 whitespace-pre-wrap rounded-lg border border-text-border bg-white p-3 text-[13px] leading-relaxed text-text-secondary ${
          compact ? "min-h-[44px]" : "min-h-[96px]"
        }`}
      >
        {content || "-"}
      </div>
    </section>
  );
}
