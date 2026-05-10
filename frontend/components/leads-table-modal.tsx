"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  X,
  Download,
  Search,
  ChevronDown,
  ChevronUp,
  ChevronLeft,
  ChevronRight,
  Loader2,
  ExternalLink,
} from "lucide-react";
import { getLeads, getLeadsWithEmails, exportLeadsExcel, exportEmailsExcel, type GetLeadsParams, type LeadWithEmail } from "@/lib/api";
import type { Lead } from "@/types";

interface LeadsTableModalProps {
  isOpen: boolean;
  onClose: () => void;
  taskId?: number | null;
  mode?: "leads" | "emails";
}

export default function LeadsTableModal({
  isOpen,
  onClose,
  taskId,
  mode = "leads",
}: LeadsTableModalProps) {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [sortBy, setSortBy] = useState("match_score");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [expandedCell, setExpandedCell] = useState<{
    leadId: number;
    field: "aiSummary" | "businessMatch" | "outreachSuggestion";
  } | null>(null);
  const [expandedEmailRowId, setExpandedEmailRowId] = useState<number | null>(null);
  const pageSize = 20;

  const debounceTimer = useRef<ReturnType<typeof setTimeout>>();

  // Debounce search input (300ms)
  useEffect(() => {
    if (debounceTimer.current) clearTimeout(debounceTimer.current);
    debounceTimer.current = setTimeout(() => {
      setDebouncedSearch(searchQuery);
      setPage(1);
    }, 300);
    return () => {
      if (debounceTimer.current) clearTimeout(debounceTimer.current);
    };
  }, [searchQuery]);

  // Fetch leads when modal opens or filters change
  const fetchLeads = useCallback(async () => {
    if (!isOpen) return;
    setIsLoading(true);
    try {
      if (mode === "emails" && taskId) {
        const res = await getLeadsWithEmails(taskId, {
          page,
          pageSize,
          search: debouncedSearch || undefined,
        });
        setLeads(res.items as Lead[]);
        setTotal(res.total);
        setTotalPages(res.totalPages);
      } else {
        const params: GetLeadsParams = {
          page,
          pageSize,
          taskId: taskId ?? undefined,
          sortBy,
          sortOrder,
        };
        if (debouncedSearch) params.search = debouncedSearch;

        const res = await getLeads(params);
        setLeads(res.items);
        setTotal(res.total);
        setTotalPages(res.totalPages);
      }
    } catch (err) {
      console.error("Failed to fetch leads:", err);
      setLeads([]);
      setTotal(0);
      setTotalPages(1);
    } finally {
      setIsLoading(false);
    }
  }, [isOpen, page, debouncedSearch, sortBy, sortOrder, pageSize, taskId, mode]);

  useEffect(() => {
    fetchLeads();
  }, [fetchLeads]);

  const handleSort = (field: string) => {
    if (sortBy === field) {
      setSortOrder((prev) => (prev === "desc" ? "asc" : "desc"));
    } else {
      setSortBy(field);
      setSortOrder("desc");
    }
    setPage(1);
  };

  const handleDownload = async () => {
    try {
      if (mode === "emails" && taskId) {
        await exportEmailsExcel(taskId);
      } else {
        await exportLeadsExcel({
          taskId: taskId ?? undefined,
          search: debouncedSearch || undefined,
        });
      }
    } catch {
      alert("Excel 导出失败");
    }
  };

  const getScoreClass = (score?: number | null) => {
    if (score == null) return "text-text-tertiary bg-gray-50 border-gray-200";
    if (score >= 80) return "text-green-700 bg-green-50 border-green-200";
    if (score >= 60) return "text-yellow-700 bg-yellow-50 border-yellow-200";
    return "text-red-600 bg-red-50 border-red-200";
  };

  const formatMatchScore = (score?: number | null) =>
    score == null ? "-" : score.toFixed(1);

  /** Extract display domain from full URL */
  const getDisplayDomain = (url: string) => {
    try {
      const hostname = new URL(url).hostname;
      return hostname.replace(/^www\./, "");
    } catch {
      return url.length > 30 ? url.substring(0, 27) + "..." : url;
    }
  };

  const toggleExpandedCell = (
    leadId: number,
    field: "aiSummary" | "businessMatch" | "outreachSuggestion"
  ) => {
    setExpandedCell((current) =>
      current?.leadId === leadId && current.field === field ? null : { leadId, field }
    );
  };

  const getExpandedCellValue = (lead: Lead) => {
    if (!expandedCell || expandedCell.leadId !== lead.id) return "";
    if (expandedCell.field === "aiSummary") return lead.aiSummary || "";
    if (expandedCell.field === "businessMatch") return lead.businessMatch || "";
    return lead.outreachSuggestion || "";
  };

  const getExpandedCellLabel = () => {
    if (!expandedCell) return "";
    if (expandedCell.field === "aiSummary") return "AI 分析摘要";
    if (expandedCell.field === "businessMatch") return "业务匹配点";
    return "开发建议";
  };

  const TruncatedCell = ({
    value,
    className = "",
    lines = 1,
  }: {
    value?: string | null;
    className?: string;
    lines?: 1 | 2;
  }) => (
    <span
      className={`block overflow-hidden text-ellipsis ${lines === 1 ? "whitespace-nowrap" : "cell-clamp-2"} ${className}`}
      title={value || ""}
    >
      {value || "-"}
    </span>
  );

  const ExpandableTextCell = ({
    lead,
    field,
    value,
  }: {
    lead: Lead;
    field: "aiSummary" | "businessMatch" | "outreachSuggestion";
    value?: string | null;
  }) => (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        toggleExpandedCell(lead.id, field);
      }}
      className={`block w-full text-left text-text-secondary hover:text-text-primary ${
        expandedCell?.leadId === lead.id && expandedCell.field === field
          ? "text-text-primary"
          : ""
      }`}
      title={value || ""}
    >
      <TruncatedCell value={value} lines={2} />
    </button>
  );

  const startIndex = (page - 1) * pageSize + 1;
  const endIndex = Math.min(page * pageSize, total);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Overlay */}
      <div
        className="absolute inset-0 bg-black/30 animate-[fade-in_0.15s_ease-out]"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative w-full max-w-[1300px] max-h-[85vh] bg-white rounded-2xl flex flex-col overflow-hidden animate-[fade-in-up_0.2s_ease-out] shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-text-border shrink-0">
          <div className="flex items-center gap-3">
            <h2 className="text-[18px] font-semibold text-text-primary">
              {mode === "emails" ? "邮件列表" : "客户线索"}
            </h2>
            <span className="px-2.5 py-0.5 bg-gray-100 text-[13px] text-text-secondary rounded-full">
              共 {total} 条
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleDownload}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-text-border text-[13px] text-text-secondary hover:bg-gray-50 transition-colors"
            >
              <Download size={14} strokeWidth={1.8} />
              <span>下载 Excel</span>
            </button>
            <button
              onClick={onClose}
              className="w-8 h-8 rounded-lg flex items-center justify-center hover:bg-gray-100 transition-colors"
            >
              <X size={18} strokeWidth={1.8} className="text-text-secondary" />
            </button>
          </div>
        </div>

        {/* Toolbar */}
        <div className="flex items-center justify-between px-6 py-3 border-b border-text-border shrink-0">
          <div className="relative">
            <Search
              size={14}
              strokeWidth={1.8}
              className="absolute left-2.5 top-1/2 -translate-y-1/2 text-text-tertiary"
            />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="搜索公司名、国家、行业..."
              className="w-[300px] h-8 pl-8 pr-3 bg-surface-input rounded-lg text-[13px] text-text-primary placeholder:text-text-tertiary outline-none border border-transparent focus:border-brand-blue/40"
            />
          </div>
          <div className="flex items-center gap-2">
            {/* Sort toggles */}
            <button
              onClick={() => handleSort("match_score")}
              className={`flex items-center gap-1 h-8 px-3 rounded-lg text-[13px] transition-colors ${
                sortBy === "match_score"
                  ? "text-brand-blue bg-brand-blue-light"
                  : "text-text-secondary hover:bg-gray-100"
              }`}
            >
              匹配度
              {sortBy === "match_score" &&
                (sortOrder === "desc" ? (
                  <ChevronDown size={14} />
                ) : (
                  <ChevronUp size={14} />
                ))}
            </button>
            <button
              onClick={() => handleSort("company_name")}
              className={`flex items-center gap-1 h-8 px-3 rounded-lg text-[13px] transition-colors ${
                sortBy === "company_name"
                  ? "text-brand-blue bg-brand-blue-light"
                  : "text-text-secondary hover:bg-gray-100"
              }`}
            >
              公司名称
              {sortBy === "company_name" &&
                (sortOrder === "desc" ? (
                  <ChevronDown size={14} />
                ) : (
                  <ChevronUp size={14} />
                ))}
            </button>
          </div>
        </div>

        {/* Table — 上下+左右均可滚动 */}
        <div className="flex-1 overflow-auto">
          {isLoading ? (
            <div className="flex items-center justify-center h-40 text-text-tertiary text-[14px] gap-2">
              <Loader2 size={16} className="animate-spin" />
              加载中...
            </div>
          ) : (
            <>
              <table className={`w-full table-fixed text-[13px] ${mode === "emails" ? "min-w-[1100px]" : "min-w-[1280px]"}`}>
                {mode === "emails" ? (
                  <>
                    <colgroup>
                      <col className="w-10" />
                      <col className="w-[180px]" />
                      <col className="w-[150px]" />
                      <col className="w-[110px]" />
                      <col className="w-[120px]" />
                      <col className="w-[150px]" />
                      <col className="w-[74px]" />
                      <col className="w-[220px]" />
                      <col className="w-[1fr]" />
                    </colgroup>
                    <thead className="sticky top-0 z-10">
                      <tr className="bg-white border-b border-text-border">
                        <th className="text-left py-3 px-3 font-semibold text-gray-700 w-10">
                          <input type="checkbox" className="accent-brand-blue" />
                        </th>
                        <th className="text-left py-3 px-3 font-semibold text-gray-700">公司名称</th>
                        <th className="text-left py-3 px-3 font-semibold text-gray-700">网站</th>
                        <th className="text-left py-3 px-3 font-semibold text-gray-700">国家/地区</th>
                        <th className="text-left py-3 px-3 font-semibold text-gray-700">行业</th>
                        <th className="text-left py-3 px-3 font-semibold text-gray-700">联系人</th>
                        <th className="text-left py-3 px-3 font-semibold text-gray-700 w-[70px]">匹配度</th>
                        <th className="text-left py-3 px-3 font-semibold text-gray-700">邮件主题</th>
                        <th className="text-left py-3 px-3 font-semibold text-gray-700">邮件正文</th>
                      </tr>
                    </thead>
                    <tbody>
                      {leads.map((lead, index) => {
                        const emailLead = lead as LeadWithEmail;
                        const isExpanded = expandedEmailRowId === lead.id;
                        return (
                          <React.Fragment key={lead.id}>
                            <tr
                              onClick={() => setExpandedEmailRowId(isExpanded ? null : lead.id)}
                              className={`h-[74px] border-b border-gray-50 cursor-pointer hover:bg-gray-50/70 transition-colors ${
                                index % 2 === 1 ? "bg-gray-50/30" : ""
                              } ${isExpanded ? "bg-brand-blue-light/30" : ""}`}
                            >
                              <td className="py-3 px-3">
                                <input type="checkbox" className="accent-brand-blue" onClick={(e) => e.stopPropagation()} />
                              </td>
                              <td className="py-3 px-3">
                                <TruncatedCell value={lead.companyName} className="text-brand-blue hover:underline font-medium" />
                              </td>
                              <td className="py-3 px-3">
                                <a
                                  href={lead.website.startsWith("http") ? lead.website : `https://${lead.website}`}
                                  target="_blank" rel="noopener noreferrer"
                                  onClick={(e) => e.stopPropagation()}
                                  className="inline-flex items-center gap-1 max-w-full truncate text-brand-blue hover:underline"
                                  title={lead.website}
                                >
                                  <span className="truncate">{getDisplayDomain(lead.website)}</span>
                                  <ExternalLink size={12} className="shrink-0 opacity-50" />
                                </a>
                              </td>
                              <td className="py-3 px-3 text-text-primary">
                                <TruncatedCell value={lead.country} />
                              </td>
                              <td className="py-3 px-3 text-text-secondary">
                                <TruncatedCell value={lead.industry} />
                              </td>
                              <td className="py-3 px-3 text-text-primary">
                                <TruncatedCell value={lead.contactName} />
                              </td>
                              <td className="py-3 px-3">
                                <span className={`inline-block px-2 py-0.5 rounded-md text-[12px] font-medium border ${getScoreClass(lead.matchScore)}`}>
                                  {formatMatchScore(lead.matchScore)}
                                </span>
                              </td>
                              <td className="py-3 px-3">
                                <TruncatedCell value={emailLead.emailSubject} />
                              </td>
                              <td className="py-3 px-3">
                                <TruncatedCell value={emailLead.emailBody} lines={2} />
                              </td>
                            </tr>
                            {isExpanded && (
                              <tr className="bg-surface-input/30 border-b border-gray-100">
                                <td colSpan={9} className="px-12 py-4">
                                  <div className="text-[13px] leading-relaxed">
                                    <div className="mb-3 flex items-center justify-between">
                                      <span className="text-[12px] text-text-tertiary">点击该行可收起</span>
                                    </div>
                                    <div className="mb-3">
                                      <span className="mb-1.5 block text-[12px] font-semibold text-text-tertiary uppercase tracking-wider">邮件主题</span>
                                      <div className="rounded-lg border border-text-border bg-white p-3 text-text-primary">
                                        {emailLead.emailSubject || "-"}
                                      </div>
                                    </div>
                                    <div className="mb-3">
                                      <span className="mb-1.5 block text-[12px] font-semibold text-text-tertiary uppercase tracking-wider">邮件正文</span>
                                      <div className="max-h-[320px] overflow-auto whitespace-pre-wrap rounded-lg border border-text-border bg-white p-3 text-text-primary leading-relaxed">
                                        {emailLead.emailBody || "-"}
                                      </div>
                                    </div>
                                    <div className="grid grid-cols-[60px_1fr_60px_1fr] gap-x-3 gap-y-2 border-t border-text-border pt-3">
                                      <span className="text-text-tertiary">邮箱</span>
                                      <span className="text-text-primary break-all">{lead.email || "-"}</span>
                                      <span className="text-text-tertiary">电话</span>
                                      <span className="text-text-primary">{lead.phone || "-"}</span>
                                    </div>
                                  </div>
                                </td>
                              </tr>
                            )}
                          </React.Fragment>
                        );
                      })}
                    </tbody>
                  </>
                ) : (
                  <>
                    <colgroup>
                      <col className="w-10" />
                      <col className="w-[180px]" />
                      <col className="w-[150px]" />
                      <col className="w-[110px]" />
                      <col className="w-[120px]" />
                      <col className="w-[105px]" />
                      <col className="w-[150px]" />
                      <col className="w-[74px]" />
                      <col className="w-[210px]" />
                      <col className="w-[180px]" />
                      <col className="w-[190px]" />
                    </colgroup>
                    <thead className="sticky top-0 z-10">
                      <tr className="bg-white border-b border-text-border">
                        <th className="text-left py-3 px-3 font-semibold text-gray-700 w-10">
                          <input type="checkbox" className="accent-brand-blue" />
                        </th>
                        <th className="text-left py-3 px-3 font-semibold text-gray-700">公司名称</th>
                        <th className="text-left py-3 px-3 font-semibold text-gray-700">网站</th>
                        <th className="text-left py-3 px-3 font-semibold text-gray-700">国家/地区</th>
                        <th className="text-left py-3 px-3 font-semibold text-gray-700">行业</th>
                        <th className="text-left py-3 px-3 font-semibold text-gray-700">公司角色</th>
                        <th className="text-left py-3 px-3 font-semibold text-gray-700">联系人</th>
                        <th className="text-left py-3 px-3 font-semibold text-gray-700 w-[70px]">匹配度</th>
                        <th className="text-left py-3 px-3 font-semibold text-gray-700 min-w-[280px]">AI 分析摘要</th>
                        <th className="text-left py-3 px-3 font-semibold text-gray-700 min-w-[220px]">业务匹配点</th>
                        <th className="text-left py-3 px-3 font-semibold text-gray-700 min-w-[220px]">开发建议</th>
                      </tr>
                    </thead>
                    <tbody>
                      {leads.map((lead, index) => (
                        <React.Fragment key={lead.id}>
                          <tr
                            className={`h-[74px] border-b border-gray-50 hover:bg-gray-50/70 transition-colors ${
                              index % 2 === 1 ? "bg-gray-50/30" : ""
                            } ${expandedCell?.leadId === lead.id ? "bg-brand-blue-light/30" : ""}`}
                          >
                            <td className="py-3 px-3">
                              <input type="checkbox" className="accent-brand-blue" onClick={(e) => e.stopPropagation()} />
                            </td>
                            <td className="py-3 px-3">
                              <TruncatedCell value={lead.companyName} className="text-brand-blue hover:underline font-medium" />
                            </td>
                            <td className="py-3 px-3">
                              <a
                                href={lead.website.startsWith("http") ? lead.website : `https://${lead.website}`}
                                target="_blank" rel="noopener noreferrer"
                                onClick={(e) => e.stopPropagation()}
                                className="inline-flex items-center gap-1 max-w-full truncate text-brand-blue hover:underline"
                                title={lead.website}
                              >
                                <span className="truncate">{getDisplayDomain(lead.website)}</span>
                                <ExternalLink size={12} className="shrink-0 opacity-50" />
                              </a>
                            </td>
                            <td className="py-3 px-3 text-text-primary">
                              <TruncatedCell value={lead.country} />
                            </td>
                            <td className="py-3 px-3 text-text-secondary">
                              <TruncatedCell value={lead.industry} />
                            </td>
                            <td className="py-3 px-3 text-text-secondary">
                                <TruncatedCell value={lead.companyRole} />
                              </td>
                            <td className="py-3 px-3 text-text-primary">
                              <TruncatedCell value={lead.contactName} />
                            </td>
                            <td className="py-3 px-3">
                              <span
                                className={`inline-block px-2 py-0.5 rounded-md text-[12px] font-medium border ${getScoreClass(lead.matchScore)}`}
                              >
                                {formatMatchScore(lead.matchScore)}
                              </span>
                            </td>
                            <td className="py-3 px-3 align-top">
                              <ExpandableTextCell lead={lead} field="aiSummary" value={lead.aiSummary} />
                            </td>
                            <td className="py-3 px-3 align-top">
                              <ExpandableTextCell lead={lead} field="businessMatch" value={lead.businessMatch} />
                            </td>
                            <td className="py-3 px-3 align-top">
                              <ExpandableTextCell lead={lead} field="outreachSuggestion" value={lead.outreachSuggestion} />
                            </td>
                          </tr>
                          {expandedCell?.leadId === lead.id && (
                            <tr className="bg-surface-input/50 border-b border-gray-100">
                              <td colSpan={11} className="px-12 py-4">
                                <div className="text-[13px] leading-relaxed">
                                  <div className="mb-2 flex items-center justify-between">
                                    <span className="font-semibold text-text-primary">{getExpandedCellLabel()}</span>
                                    <span className="text-[12px] text-text-tertiary">再次点击该格子可收起</span>
                                  </div>
                                  <div className="max-h-[260px] overflow-auto whitespace-pre-wrap rounded-lg border border-text-border bg-white p-3 text-text-primary">
                                    {getExpandedCellValue(lead) || "-"}
                                  </div>
                                  <div className="mt-3 grid grid-cols-[80px_1fr_80px_1fr] gap-x-3 gap-y-2 border-t border-text-border pt-3">
                                    <span className="text-text-tertiary">邮箱</span>
                                    <span className="text-text-primary break-all">{lead.email || "-"}</span>
                                    <span className="text-text-tertiary">电话</span>
                                    <span className="text-text-primary">{lead.phone || "-"}</span>
                                  </div>
                                </div>
                              </td>
                            </tr>
                          )}
                        </React.Fragment>
                      ))}
                    </tbody>
                  </>
                )}
              </table>

              {leads.length === 0 && (
                <div className="flex items-center justify-center h-40 text-text-tertiary text-[14px]">
                  暂无匹配结果
                </div>
              )}
            </>
          )}
        </div>

        {/* Pagination */}
        <div className="flex items-center justify-between px-6 py-3 border-t border-text-border shrink-0">
          <span className="text-[13px] text-text-secondary">
            {total > 0
              ? `显示 ${startIndex}-${endIndex} 条，共 ${total} 条`
              : "暂无数据"}
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1 || isLoading}
              className="h-8 px-3 rounded-lg text-[13px] text-text-secondary hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              上一页
            </button>
            {/* Show page numbers with ellipsis for large page counts */}
            {totalPages <= 7
              ? Array.from({ length: totalPages }, (_, i) => i + 1).map(
                  (p) => (
                    <button
                      key={p}
                      onClick={() => setPage(p)}
                      disabled={isLoading}
                      className={`w-8 h-8 rounded-full text-[13px] flex items-center justify-center transition-colors ${
                        p === page
                          ? "bg-brand-blue text-white"
                          : "text-text-secondary hover:bg-gray-100"
                      }`}
                    >
                      {p}
                    </button>
                  )
                )
              : // Show first, last, current and neighbors
                [
                  1,
                  ...(page > 3 ? ["..."] : []),
                  ...Array.from(
                    { length: Math.min(3, totalPages - 2) },
                    (_, i) => Math.max(2, Math.min(page - 1, totalPages - 3)) + i
                  ),
                  ...(page < totalPages - 2 ? ["..."] : []),
                  totalPages,
                ]
                  .filter((v, i, arr) => arr.indexOf(v) === i) // deduplicate
                  .map((p, i) =>
                    typeof p === "string" ? (
                      <span
                        key={`ellipsis-${i}`}
                        className="w-8 h-8 flex items-center justify-center text-text-tertiary"
                      >
                        ...
                      </span>
                    ) : (
                      <button
                        key={p}
                        onClick={() => setPage(p)}
                        disabled={isLoading}
                        className={`w-8 h-8 rounded-full text-[13px] flex items-center justify-center transition-colors ${
                          p === page
                            ? "bg-brand-blue text-white"
                            : "text-text-secondary hover:bg-gray-100"
                        }`}
                      >
                        {p}
                      </button>
                    )
                  )}
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages || isLoading}
              className="h-8 px-3 rounded-lg text-[13px] text-text-secondary hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              下一页
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
