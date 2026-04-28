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
import { getLeads, exportLeadsExcel, type GetLeadsParams } from "@/lib/api";
import type { Lead } from "@/types";

interface LeadsTableModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function LeadsTableModal({
  isOpen,
  onClose,
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
      setTotalPages(res.totalPages);
    } catch (err) {
      console.error("Failed to fetch leads:", err);
      setLeads([]);
      setTotal(0);
      setTotalPages(1);
    } finally {
      setIsLoading(false);
    }
  }, [isOpen, page, debouncedSearch, sortBy, sortOrder, pageSize]);

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
      await exportLeadsExcel();
    } catch {
      alert("Excel 导出失败");
    }
  };

  const getScoreClass = (score: number) => {
    if (score >= 80) return "text-green-700 bg-green-50 border-green-200";
    if (score >= 60) return "text-yellow-700 bg-yellow-50 border-yellow-200";
    return "text-red-600 bg-red-50 border-red-200";
  };

  /** Extract display domain from full URL */
  const getDisplayDomain = (url: string) => {
    try {
      const hostname = new URL(url).hostname;
      return hostname.replace(/^www\./, "");
    } catch {
      return url.length > 30 ? url.substring(0, 27) + "..." : url;
    }
  };

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
              客户线索
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
              <table className="w-full text-[13px] min-w-[1600px]">
                <thead className="sticky top-0 z-10">
                  <tr className="bg-white border-b border-text-border">
                    <th className="text-left py-3 px-3 font-semibold text-gray-700 w-10">
                      <input type="checkbox" className="accent-brand-blue" />
                    </th>
                    <th className="text-left py-3 px-3 font-semibold text-gray-700">
                      公司名称
                    </th>
                    <th className="text-left py-3 px-3 font-semibold text-gray-700">
                      网站
                    </th>
                    <th className="text-left py-3 px-3 font-semibold text-gray-700">
                      国家/地区
                    </th>
                    <th className="text-left py-3 px-3 font-semibold text-gray-700">
                      行业
                    </th>
                    <th className="text-left py-3 px-3 font-semibold text-gray-700">
                      公司角色
                    </th>
                    <th className="text-left py-3 px-3 font-semibold text-gray-700">
                      联系人
                    </th>
                    <th className="text-left py-3 px-3 font-semibold text-gray-700">
                      邮箱
                    </th>
                    <th className="text-left py-3 px-3 font-semibold text-gray-700">
                      电话
                    </th>
                    <th className="text-left py-3 px-3 font-semibold text-gray-700 w-[70px]">
                      匹配度
                    </th>
                    <th className="text-left py-3 px-3 font-semibold text-gray-700 min-w-[280px]">
                      AI 分析摘要
                    </th>
                    <th className="text-left py-3 px-3 font-semibold text-gray-700 min-w-[220px]">
                      业务匹配点
                    </th>
                    <th className="text-left py-3 px-3 font-semibold text-gray-700 min-w-[220px]">
                      开发建议
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {leads.map((lead, index) => (
                    <tr
                      key={lead.id}
                      className={`border-b border-gray-50 hover:bg-gray-50/50 transition-colors ${
                        index % 2 === 1 ? "bg-gray-50/30" : ""
                      }`}
                    >
                      <td className="py-3 px-3">
                        <input type="checkbox" className="accent-brand-blue" />
                      </td>
                      {/* 公司名称 */}
                      <td className="py-3 px-3">
                        <span
                          className="block max-w-[180px] truncate text-brand-blue hover:underline cursor-pointer font-medium"
                          title={lead.companyName}
                        >
                          {lead.companyName}
                        </span>
                      </td>
                      {/* 网站：域名 + 可点击 */}
                      <td className="py-3 px-3">
                        <a
                          href={
                            lead.website.startsWith("http")
                              ? lead.website
                              : `https://${lead.website}`
                          }
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 max-w-[160px] truncate text-brand-blue hover:underline"
                          title={lead.website}
                        >
                          {getDisplayDomain(lead.website)}
                          <ExternalLink size={12} className="shrink-0 opacity-50" />
                        </a>
                      </td>
                      {/* 国家/地区 */}
                      <td className="py-3 px-3 text-text-primary whitespace-nowrap">
                        {lead.country}
                      </td>
                      {/* 行业 */}
                      <td className="py-3 px-3 text-text-secondary">
                        <span className="block max-w-[100px] truncate" title={lead.industry}>
                          {lead.industry}
                        </span>
                      </td>
                      {/* 公司角色 */}
                      <td className="py-3 px-3 text-text-secondary whitespace-nowrap">
                        {lead.companyRole || "-"}
                      </td>
                      {/* 联系人 */}
                      <td className="py-3 px-3 text-text-primary whitespace-nowrap">
                        {lead.contactName || "-"}
                      </td>
                      {/* 邮箱 */}
                      <td className="py-3 px-3 text-text-secondary">
                        <span className="block max-w-[180px] truncate" title={lead.email}>
                          {lead.email}
                        </span>
                      </td>
                      {/* 电话 */}
                      <td className="py-3 px-3 text-text-secondary whitespace-nowrap">
                        {lead.phone || "-"}
                      </td>
                      {/* 匹配度 */}
                      <td className="py-3 px-3">
                        <span
                          className={`inline-block px-2 py-0.5 rounded-md text-[12px] font-medium border ${getScoreClass(
                            lead.matchScore
                          )}`}
                        >
                          {lead.matchScore.toFixed(1)}
                        </span>
                      </td>
                      {/* AI 分析摘要 */}
                      <td className="py-3 px-3 text-text-secondary">
                        <span className="block max-w-[280px] whitespace-pre-line line-clamp-3" title={lead.aiSummary}>
                          {lead.aiSummary || "-"}
                        </span>
                      </td>
                      {/* 业务匹配点 */}
                      <td className="py-3 px-3 text-text-secondary">
                        <span className="block max-w-[220px] whitespace-pre-line line-clamp-3" title={lead.businessMatch}>
                          {lead.businessMatch || "-"}
                        </span>
                      </td>
                      {/* 开发建议 */}
                      <td className="py-3 px-3 text-text-secondary">
                        <span className="block max-w-[220px] whitespace-pre-line line-clamp-3" title={lead.outreachSuggestion}>
                          {lead.outreachSuggestion || "-"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
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
