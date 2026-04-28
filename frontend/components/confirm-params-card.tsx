"use client";

import React, { useState } from "react";
import { Search, Plus, X } from "lucide-react";
import type { ConfirmParamsData } from "@/types";

interface ConfirmParamsCardProps {
  initialParams: ConfirmParamsData;
  onConfirm: (params: {
    industry: string;
    country: string;
    keywords: string[];
    num: number;
  }) => void;
  onCancel: () => void;
}

export default function ConfirmParamsCard({
  initialParams,
  onConfirm,
  onCancel,
}: ConfirmParamsCardProps) {
  const [industry, setIndustry] = useState(initialParams.industry);
  const [country, setCountry] = useState(initialParams.country);
  const [keywords, setKeywords] = useState<string[]>(initialParams.keywords);
  const [num, setNum] = useState(initialParams.num);
  const [newKeyword, setNewKeyword] = useState("");

  const handleAddKeyword = () => {
    const trimmed = newKeyword.trim();
    if (trimmed && !keywords.includes(trimmed)) {
      setKeywords((prev) => [...prev, trimmed]);
      setNewKeyword("");
    }
  };

  const handleRemoveKeyword = (kw: string) => {
    setKeywords((prev) => prev.filter((k) => k !== kw));
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleAddKeyword();
    }
  };

  const handleConfirm = () => {
    if (!industry.trim() || !country.trim() || keywords.length === 0 || num < 1) return;
    onConfirm({
      industry: industry.trim(),
      country: country.trim(),
      keywords,
      num,
    });
  };

  const inputClass =
    "w-full px-3 py-1.5 border border-text-border rounded-lg text-[13px] text-text-primary bg-white focus:outline-none focus:border-brand-blue transition-colors";

  return (
    <div className="border border-text-border rounded-xl p-4 bg-surface-white">
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <div className="w-7 h-7 rounded-lg bg-brand-blue-light flex items-center justify-center">
          <Search size={15} strokeWidth={2} className="text-brand-blue" />
        </div>
        <span className="text-[14px] font-semibold text-text-primary">
          请确认搜索参数
        </span>
      </div>

      {/* Reply text */}
      {initialParams.reply && (
        <p className="text-[13px] text-text-secondary mb-3 pl-1">
          {initialParams.reply}
        </p>
      )}

      {/* Fields */}
      <div className="space-y-2.5 pl-1">
        {/* Industry */}
        <div className="flex items-center gap-2">
          <span className="text-[13px] text-text-secondary w-10 shrink-0">
            行业
          </span>
          <input
            className={inputClass}
            value={industry}
            onChange={(e) => setIndustry(e.target.value)}
            placeholder="如 LED, Solar Panel"
          />
        </div>

        {/* Country */}
        <div className="flex items-center gap-2">
          <span className="text-[13px] text-text-secondary w-10 shrink-0">
            国家
          </span>
          <input
            className={inputClass}
            value={country}
            onChange={(e) => setCountry(e.target.value)}
            placeholder="如 USA, Germany"
          />
        </div>

        {/* Num */}
        <div className="flex items-center gap-2">
          <span className="text-[13px] text-text-secondary w-10 shrink-0">
            数量
          </span>
          <input
            type="number"
            min={1}
            max={100}
            className={`${inputClass} w-24`}
            value={num}
            onChange={(e) => setNum(Math.max(1, Math.min(100, parseInt(e.target.value) || 1)))}
          />
        </div>

        {/* Keywords */}
        <div>
          <span className="text-[13px] text-text-secondary mb-1.5 block">
            关键词
          </span>
          <div className="flex flex-wrap gap-1.5 mb-2">
            {keywords.map((kw) => (
              <span
                key={kw}
                className="inline-flex items-center gap-1 px-2.5 py-1 bg-gray-100 rounded-md text-[12px] text-text-primary"
              >
                {kw}
                <button
                  onClick={() => handleRemoveKeyword(kw)}
                  className="text-text-tertiary hover:text-red-500 transition-colors"
                >
                  <X size={12} />
                </button>
              </span>
            ))}
          </div>
          <div className="flex gap-2">
            <input
              className={inputClass}
              value={newKeyword}
              onChange={(e) => setNewKeyword(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入新关键词"
            />
            <button
              onClick={handleAddKeyword}
              disabled={!newKeyword.trim()}
              className="px-2.5 py-1.5 border border-brand-blue text-brand-blue rounded-lg text-[12px] font-medium hover:bg-brand-blue-light transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1 shrink-0"
            >
              <Plus size={12} />
              添加
            </button>
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center justify-end gap-2 mt-4">
        <button
          onClick={onCancel}
          className="px-3.5 py-1.5 border border-text-border rounded-lg text-[13px] font-medium text-text-secondary hover:bg-gray-50 transition-colors"
        >
          取消
        </button>
        <button
          onClick={handleConfirm}
          disabled={!industry.trim() || !country.trim() || keywords.length === 0}
          className="px-3.5 py-1.5 bg-brand-blue text-white rounded-lg text-[13px] font-medium hover:bg-brand-blue-hover transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          确认搜索
        </button>
      </div>
    </div>
  );
}
