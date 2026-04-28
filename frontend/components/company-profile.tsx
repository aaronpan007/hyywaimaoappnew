"use client";

import React from "react";
import {
  Building2,
  ChevronLeft,
  RefreshCw,
  Download,
  ExternalLink,
} from "lucide-react";
import type { CompanyProfile } from "@/types";

interface CompanyProfilePageProps {
  profile: CompanyProfile | null;
  onBack: () => void;
  onStartCollect: () => void;
  onRecollect: () => void;
  onExport: () => void;
}

export default function CompanyProfilePage({
  profile,
  onBack,
  onStartCollect,
  onRecollect,
  onExport,
}: CompanyProfilePageProps) {
  if (!profile) {
    return (
      <div className="flex-1 flex items-center justify-center px-4">
        <div className="w-full max-w-[480px] text-center">
          {/* Empty State */}
          <div className="flex justify-center mb-4">
            <Building2 size={48} strokeWidth={1} className="text-gray-300" />
          </div>
          <h2 className="text-[20px] font-semibold text-text-primary mb-2">
            公司资料
          </h2>
          <div className="flex flex-col items-center gap-1 mb-6">
            <p className="text-[14px] text-text-secondary">
              还没有采集您的企业信息。
            </p>
            <p className="text-[14px] text-text-secondary">
              AI 会通过对话引导您完成信息收集，
            </p>
            <p className="text-[14px] text-text-secondary">
              并自动爬取网站生成结构化画像。
            </p>
          </div>

          <button
            onClick={onStartCollect}
            className="w-full h-11 bg-brand-blue text-white text-[14px] font-medium rounded-xl hover:bg-brand-blue-hover transition-colors active:scale-[0.98] mb-8"
          >
            开始采集我的企业信息
          </button>

          <div className="h-px bg-text-border mb-4" />

          <div className="text-left">
            <p className="text-[13px] text-text-tertiary mb-3">需要准备：</p>
            <div className="flex flex-col gap-1.5">
              {[
                "公司名称和所属行业",
                "公司官网地址",
                "主要产品/服务信息",
                "核心优势和资质认证",
              ].map((item) => (
                <div key={item} className="flex items-center gap-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-text-tertiary" />
                  <span className="text-[13px] text-text-secondary">{item}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Collected state
  return (
    <div className="flex-1 overflow-y-auto px-4 py-6">
      <div className="max-w-[640px] mx-auto">
        {/* Back link */}
        <button
          onClick={onBack}
          className="flex items-center gap-1 text-[14px] text-brand-blue hover:text-brand-blue-hover transition-colors mb-6"
        >
          <ChevronLeft size={16} />
          <span>返回对话</span>
        </button>

        {/* Company Header */}
        <div className="flex items-start gap-3 mb-6">
          <div className="w-8 h-8 rounded-lg bg-brand-blue-light flex items-center justify-center mt-0.5 shrink-0">
            <Building2 size={18} strokeWidth={1.8} className="text-brand-blue" />
          </div>
          <div>
            <h2 className="text-[20px] font-semibold text-text-primary">
              {profile.companyName}
            </h2>
            <p className="text-[14px] text-text-secondary mt-0.5">
              {profile.industry}
            </p>
            <a
              href={profile.website}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[14px] text-brand-blue hover:underline inline-flex items-center gap-1 mt-1"
            >
              {profile.website}
              <ExternalLink size={12} />
            </a>
          </div>
        </div>

        {/* Basic Info Card */}
        <div className="border border-text-border rounded-xl p-4 mb-3">
          <h3 className="text-[13px] font-semibold text-gray-700 mb-3">
            基本信息
          </h3>
          <div className="grid grid-cols-2 gap-x-6 gap-y-2">
            <div>
              <span className="text-[12px] text-text-tertiary">成立年份</span>
              <p className="text-[14px] text-text-primary">{profile.established}</p>
            </div>
            <div>
              <span className="text-[12px] text-text-tertiary">员工规模</span>
              <p className="text-[14px] text-text-primary">{profile.employees}</p>
            </div>
            <div>
              <span className="text-[12px] text-text-tertiary">认证资质</span>
              <p className="text-[14px] text-text-primary">{profile.certifications}</p>
            </div>
            <div>
              <span className="text-[12px] text-text-tertiary">合作模式</span>
              <p className="text-[14px] text-text-primary">{profile.cooperationModels}</p>
            </div>
          </div>
        </div>

        {/* Products Card */}
        <div className="border border-text-border rounded-xl p-4 mb-3">
          <h3 className="text-[13px] font-semibold text-gray-700 mb-3">
            主要产品
          </h3>
          <div className="flex flex-wrap gap-2">
            {profile.products.map((product) => (
              <span
                key={product}
                className="px-3 py-1 bg-brand-blue-light text-brand-blue text-[13px] rounded-md"
              >
                {product}
              </span>
            ))}
          </div>
        </div>

        {/* Core Competencies Card */}
        <div className="border border-text-border rounded-xl p-4 mb-3">
          <h3 className="text-[13px] font-semibold text-gray-700 mb-3">
            核心优势
          </h3>
          <div className="flex flex-col gap-1.5">
            {profile.competencies.map((item) => (
              <div key={item} className="flex items-start gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-brand-blue mt-1.5 shrink-0" />
                <span className="text-[13px] text-text-primary leading-relaxed">
                  {item}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Case Studies Card */}
        <div className="border border-text-border rounded-xl p-4 mb-6">
          <h3 className="text-[13px] font-semibold text-gray-700 mb-3">
            案例研究（{profile.caseStudies.length}个）
          </h3>
          <div className="flex flex-col gap-2 mb-3">
            {profile.caseStudies.slice(0, 2).map((cs) => (
              <div key={cs.project} className="flex items-start gap-2 py-1">
                <div className="w-1.5 h-1.5 rounded-full bg-text-tertiary mt-1.5 shrink-0" />
                <div>
                  <p className="text-[13px] text-text-primary font-medium">
                    {cs.project}
                  </p>
                  <p className="text-[12px] text-text-secondary">{cs.description}</p>
                </div>
              </div>
            ))}
          </div>
          {profile.caseStudies.length > 2 && (
            <button className="text-[13px] text-brand-blue hover:text-brand-blue-hover transition-colors">
              展开查看全部案例 →
            </button>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between mb-8">
          <span className="text-[12px] text-text-tertiary">
            采集时间：{profile.collectedAt}
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={onRecollect}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg border border-text-border text-[13px] text-text-secondary hover:bg-gray-50 transition-colors"
            >
              <RefreshCw size={14} strokeWidth={1.8} />
              <span>重新采集</span>
            </button>
            <button
              onClick={onExport}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-brand-blue text-white text-[13px] font-medium hover:bg-brand-blue-hover transition-colors"
            >
              <Download size={14} strokeWidth={1.8} />
              <span>导出画像</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
