"use client";

import React, { useState } from "react";
import {
  BadgeCheck,
  Boxes,
  BriefcaseBusiness,
  Building2,
  Calendar,
  ChevronDown,
  ChevronLeft,
  ChevronUp,
  CircleAlert,
  CircleCheck,
  Download,
  ExternalLink,
  Factory,
  FileText,
  Globe2,
  Lightbulb,
  MapPin,
  Package,
  Plus,
  ShieldCheck,
  Sparkles,
  Trash2,
  Users,
  XCircle,
} from "lucide-react";
import type { CompanyProfile } from "@/types";

interface CompanyProfilePageProps {
  profile: CompanyProfile | null;
  onBack: () => void;
  onStartCollect: () => void;
  onSupplement: () => void;
  onClearProfile: () => void;
  onExport: () => void;
}

function asArray(value: any): any[] {
  if (Array.isArray(value)) return value;
  if (!value) return [];
  return [value];
}

function textOf(value: any, fallback = ""): string {
  if (value === null || value === undefined) return fallback;
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return fallback;
}

function labelOf(value: any, fallback = ""): string {
  if (typeof value === "string") return value;
  if (!value || typeof value !== "object") return fallback;
  return (
    value.name ||
    value.model ||
    value.competency ||
    value.customer_type ||
    value.type ||
    value.project ||
    value.title ||
    fallback
  );
}

function compactList(values: any[], limit = 4): string {
  return values
    .map((v) => labelOf(v, textOf(v)))
    .filter(Boolean)
    .slice(0, limit)
    .join("、");
}

function productDescription(product: any): string {
  if (typeof product === "string") return "";
  return product?.description || product?.target_customers || "";
}

function competencyDescription(item: any): string {
  if (typeof item === "string") return item;
  return item?.description || item?.evidence || "";
}

function caseSummary(item: any): string {
  if (typeof item === "string") return item;
  return item?.key_highlight || item?.result || item?.problem_solved || "";
}

function StatCard({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ElementType;
  label: string;
  value?: string;
}) {
  return (
    <div className="min-h-[78px] rounded-lg border border-text-border bg-white px-4 py-3 flex items-center gap-3">
      <div className="w-10 h-10 rounded-lg bg-brand-blue-light text-brand-blue flex items-center justify-center shrink-0">
        <Icon size={20} strokeWidth={1.8} />
      </div>
      <div className="min-w-0">
        <p className="text-[12px] text-text-tertiary mb-1">{label}</p>
        <p className="text-[15px] text-text-primary font-medium truncate">{value || "-"}</p>
      </div>
    </div>
  );
}

function SectionTitle({
  children,
  count,
}: {
  children: React.ReactNode;
  count?: number;
}) {
  return (
    <div className="flex items-center gap-2 mb-4">
      <span className="w-1 h-6 rounded-full bg-brand-blue" />
      <h3 className="text-[18px] font-semibold text-text-primary">
        {children}
        {typeof count === "number" ? `（${count}）` : ""}
      </h3>
    </div>
  );
}

function InfoCard({
  icon: Icon,
  title,
  body,
  tone = "blue",
}: {
  icon: React.ElementType;
  title: string;
  body?: string;
  tone?: "blue" | "green" | "violet";
}) {
  const toneClass =
    tone === "green"
      ? "bg-emerald-50 text-emerald-600"
      : tone === "violet"
        ? "bg-violet-50 text-violet-600"
        : "bg-brand-blue-light text-brand-blue";

  return (
    <div className="rounded-lg border border-text-border bg-white p-4 min-h-[106px] flex gap-3">
      <div className={`w-11 h-11 rounded-xl ${toneClass} flex items-center justify-center shrink-0`}>
        <Icon size={22} strokeWidth={1.8} />
      </div>
      <div className="min-w-0">
        <h4 className="text-[15px] font-semibold text-text-primary mb-1 line-clamp-1">{title}</h4>
        {body && <p className="text-[13px] leading-6 text-text-secondary line-clamp-2">{body}</p>}
      </div>
    </div>
  );
}

export default function CompanyProfilePage({
  profile,
  onBack,
  onStartCollect,
  onSupplement,
  onClearProfile,
  onExport,
}: CompanyProfilePageProps) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const toggle = (key: string) => setExpanded(prev => {
    const next = new Set(prev);
    next.has(key) ? next.delete(key) : next.add(key);
    return next;
  });

  if (!profile) {
    return (
      <div className="flex-1 flex items-center justify-center px-4">
        <div className="w-full max-w-[480px] text-center">
          <div className="flex justify-center mb-4">
            <Building2 size={48} strokeWidth={1} className="text-gray-300" />
          </div>
          <h2 className="text-[20px] font-semibold text-text-primary mb-2">
            公司资料
          </h2>
          <p className="text-[14px] text-text-secondary leading-7 mb-6">
            还没有公司画像。AI 会根据官网和您补充的信息，整理产品、优势、案例、客户类型和信息边界。
          </p>
          <button
            onClick={onStartCollect}
            className="w-full h-11 bg-brand-blue text-white text-[14px] font-medium rounded-lg hover:bg-brand-blue-hover transition-colors active:scale-[0.98]"
          >
            开始采集公司画像
          </button>
        </div>
      </div>
    );
  }

  const products = asArray(profile.products);
  const competencies = asArray(profile.competencies);
  const cases = asArray(profile.caseStudies);
  const cooperationModels = asArray(profile.cooperationModels);
  const certifications = asArray(profile.certifications);
  const usps = asArray(profile.uniqueSellingPoints);
  const targetTypes = asArray(profile.targetCustomerTypes);
  const boundaries = profile.boundaries || {};
  const sourceUrls = asArray(profile.metadata?.sourceUrls || profile.metadata?.source_urls);

  return (
    <div className="flex-1 overflow-y-auto bg-white px-4 py-6">
      <div className="max-w-[1040px] mx-auto pb-8">
        <div className="flex items-center justify-between mb-5">
          <button
            onClick={onBack}
            className="flex items-center gap-1 text-[14px] text-brand-blue hover:text-brand-blue-hover transition-colors"
          >
            <ChevronLeft size={16} />
            <span>返回对话</span>
          </button>
          <div className="flex items-center gap-2">
            <button
              onClick={onSupplement}
              className="h-9 px-3 rounded-lg border border-brand-blue text-[13px] text-brand-blue hover:bg-brand-blue-light transition-colors inline-flex items-center gap-1.5"
            >
              <Plus size={14} />
              <span>补充资料</span>
            </button>
            <button
              onClick={onClearProfile}
              className="h-9 px-3 rounded-lg border border-red-200 text-[13px] text-red-600 hover:bg-red-50 transition-colors inline-flex items-center gap-1.5"
            >
              <Trash2 size={14} />
              <span>清空公司资料</span>
            </button>
            <button
              onClick={onExport}
              className="h-9 px-3 rounded-lg bg-brand-blue text-white text-[13px] font-medium hover:bg-brand-blue-hover transition-colors inline-flex items-center gap-1.5"
            >
              <Download size={14} />
              <span>导出画像</span>
            </button>
          </div>
        </div>

        <section className="relative overflow-hidden rounded-lg border border-text-border bg-gradient-to-br from-white via-blue-50/40 to-white px-5 py-6 mb-6">
          <div className="absolute right-6 top-5 hidden md:grid grid-cols-2 gap-2 opacity-80">
            {[Package, Factory, ShieldCheck, Globe2].map((Icon, index) => (
              <div key={index} className="w-14 h-14 rounded-xl bg-white/80 border border-blue-100 text-brand-blue flex items-center justify-center shadow-sm">
                <Icon size={24} strokeWidth={1.6} />
              </div>
            ))}
          </div>
          <div className="max-w-[680px]">
            <div className="w-12 h-12 rounded-xl bg-brand-blue text-white flex items-center justify-center mb-4">
              <Building2 size={25} strokeWidth={1.8} />
            </div>
            <h1 className="text-[28px] leading-tight font-semibold text-text-primary mb-1">
              {profile.companyName || "未命名公司"}
            </h1>
            {profile.website && (
              <a
                href={profile.website}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[14px] text-brand-blue hover:underline inline-flex items-center gap-1 mb-3"
              >
                {profile.website}
                <ExternalLink size={13} />
              </a>
            )}
            <p className="text-[15px] leading-7 text-text-secondary">
              {profile.oneLineIntro || profile.fullIntro || profile.industry || "暂无公司简介"}
            </p>
          </div>
        </section>

        <section className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-7">
          <StatCard icon={BriefcaseBusiness} label="行业" value={profile.industry} />
          <StatCard icon={MapPin} label="地区" value={profile.location} />
          <StatCard icon={Calendar} label="成立时间" value={profile.established} />
          <StatCard icon={Users} label="规模" value={profile.scale || profile.employees} />
        </section>

        <section className="mb-7">
          <SectionTitle count={products.length}>主营产品与服务</SectionTitle>
          <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
            {products.slice(0, expanded.has("products") ? undefined : 6).map((product, index) => (
              <InfoCard
                key={`${labelOf(product, "产品")}-${index}`}
                icon={index % 3 === 0 ? Package : index % 3 === 1 ? Boxes : Sparkles}
                title={labelOf(product, "未命名产品")}
                body={productDescription(product)}
                tone={index % 3 === 0 ? "green" : index % 3 === 1 ? "blue" : "violet"}
              />
            ))}
          </div>
          {products.length > 6 && (
            <button onClick={() => toggle("products")} className="mt-3 text-[13px] text-brand-blue hover:text-brand-blue-hover transition-colors inline-flex items-center gap-1">
              {expanded.has("products") ? "收起" : `展开全部 ${products.length} 个`}
              {expanded.has("products") ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>
          )}
        </section>

        <section className="grid lg:grid-cols-[1fr_360px] gap-4 mb-7">
          <div>
            <SectionTitle>核心竞争力</SectionTitle>
            <div className="grid md:grid-cols-2 gap-4">
              {competencies.slice(0, expanded.has("competencies") ? undefined : 4).map((item, index) => (
                <InfoCard
                  key={`${labelOf(item, "竞争力")}-${index}`}
                  icon={index % 2 === 0 ? Lightbulb : BadgeCheck}
                  title={labelOf(item, "核心能力")}
                  body={competencyDescription(item)}
                  tone={index % 2 === 0 ? "blue" : "violet"}
                />
              ))}
            </div>
            {competencies.length > 4 && (
              <button onClick={() => toggle("competencies")} className="mt-3 text-[13px] text-brand-blue hover:text-brand-blue-hover transition-colors inline-flex items-center gap-1">
                {expanded.has("competencies") ? "收起" : `展开全部 ${competencies.length} 个`}
                {expanded.has("competencies") ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              </button>
            )}
          </div>
          <div className="rounded-lg border border-text-border bg-white p-4">
            <SectionTitle>画像摘要</SectionTitle>
            <div className="grid grid-cols-3 gap-2 text-center mb-4">
              <div>
                <p className="text-[20px] font-semibold text-brand-blue">{products.length}</p>
                <p className="text-[12px] text-text-tertiary">产品</p>
              </div>
              <div>
                <p className="text-[20px] font-semibold text-brand-blue">{cases.length}</p>
                <p className="text-[12px] text-text-tertiary">案例</p>
              </div>
              <div>
                <p className="text-[20px] font-semibold text-brand-blue">{certifications.length}</p>
                <p className="text-[12px] text-text-tertiary">资质</p>
              </div>
            </div>
            <p className="text-[13px] leading-6 text-text-secondary">
              适合开发：{compactList(targetTypes, 3) || "待补充"}
            </p>
          </div>
        </section>

        <section className="mb-7">
          <SectionTitle count={cases.length}>成功案例</SectionTitle>
          {cases.length > 0 ? (
            <div className="grid md:grid-cols-2 gap-4">
              {cases.slice(0, expanded.has("cases") ? undefined : 4).map((item, index) => (
                <div key={index} className="rounded-lg border border-text-border bg-white p-4 min-h-[142px]">
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <h4 className="text-[15px] font-semibold text-text-primary line-clamp-1">
                      {labelOf(item, "未命名案例")}
                    </h4>
                    {item?.industry && (
                      <span className="shrink-0 rounded-md bg-emerald-50 px-2 py-1 text-[12px] text-emerald-700">
                        {item.industry}
                      </span>
                    )}
                  </div>
                  <p className="text-[13px] leading-6 text-text-secondary line-clamp-2">
                    {caseSummary(item)}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2 text-[12px] text-text-tertiary">
                    {item?.country && <span>{item.country}</span>}
                    {item?.client_type && <span>{item.client_type}</span>}
                    {item?.area_or_quantity && <span>{item.area_or_quantity}</span>}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-lg border border-dashed border-text-border bg-gray-50 px-4 py-5 text-[14px] text-text-secondary">
              暂无明确可用案例。重新采集时可以补充 Projects、Case Studies、客户项目页面，AI 会优先提取。
            </div>
          )}
          {cases.length > 4 && (
            <button onClick={() => toggle("cases")} className="mt-3 text-[13px] text-brand-blue hover:text-brand-blue-hover transition-colors inline-flex items-center gap-1">
              {expanded.has("cases") ? "收起" : `展开全部 ${cases.length} 个`}
              {expanded.has("cases") ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>
          )}
        </section>

        <section className="grid lg:grid-cols-2 gap-4 mb-7">
          <div className="rounded-lg border border-text-border bg-white p-4">
            <SectionTitle>资质与合作模式</SectionTitle>
            <div className="rounded-lg border border-blue-100 bg-blue-50/40 p-3 mb-3">
              <div className="flex items-center gap-2 text-brand-blue text-[13px] font-medium mb-2">
                <ShieldCheck size={16} />
                <span>资质认证</span>
              </div>
              <p className="text-[13px] text-text-secondary leading-6">
                {compactList(certifications, expanded.has("certifications") ? undefined : 8) || "待补充"}
              </p>
              {certifications.length > 8 && (
                <button onClick={() => toggle("certifications")} className="mt-1 text-[12px] text-brand-blue hover:text-brand-blue-hover transition-colors inline-flex items-center gap-1">
                  {expanded.has("certifications") ? "收起" : `展开全部 ${certifications.length} 项`}
                  {expanded.has("certifications") ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                </button>
              )}
            </div>
            <div className="rounded-lg border border-text-border p-3">
              <div className="flex items-center gap-2 text-brand-blue text-[13px] font-medium mb-2">
                <FileText size={16} />
                <span>合作模式</span>
              </div>
              <p className="text-[13px] text-text-secondary leading-6">
                {compactList(cooperationModels, expanded.has("cooperationModels") ? undefined : 6) || "待补充"}
              </p>
              {cooperationModels.length > 6 && (
                <button onClick={() => toggle("cooperationModels")} className="mt-1 text-[12px] text-brand-blue hover:text-brand-blue-hover transition-colors inline-flex items-center gap-1">
                  {expanded.has("cooperationModels") ? "收起" : `展开全部 ${cooperationModels.length} 项`}
                  {expanded.has("cooperationModels") ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                </button>
              )}
            </div>
          </div>

          <div className="rounded-lg border border-text-border bg-white p-4">
            <SectionTitle>独特卖点</SectionTitle>
            <div className="space-y-3">
              {usps.slice(0, expanded.has("usps") ? undefined : 5).map((item, index) => (
                <div key={index} className="flex gap-3">
                  <div className="w-7 h-7 rounded-lg bg-brand-blue-light text-brand-blue flex items-center justify-center shrink-0">
                    <Sparkles size={15} />
                  </div>
                  <p className="text-[13px] leading-6 text-text-secondary">
                    {textOf(item, labelOf(item))}
                  </p>
                </div>
              ))}
              {usps.length === 0 && <p className="text-[13px] text-text-tertiary">待补充</p>}
              {usps.length > 5 && (
                <button onClick={() => toggle("usps")} className="text-[13px] text-brand-blue hover:text-brand-blue-hover transition-colors inline-flex items-center gap-1">
                  {expanded.has("usps") ? "收起" : `展开全部 ${usps.length} 个`}
                  {expanded.has("usps") ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                </button>
              )}
            </div>
          </div>
        </section>

        <section className="mb-5">
          <SectionTitle>信息边界（可服务范围）</SectionTitle>
          <div className="grid lg:grid-cols-3 gap-3">
            <div className="rounded-lg border border-emerald-200 bg-emerald-50/60 p-4 flex gap-3">
              <CircleCheck className="text-emerald-600 shrink-0 mt-0.5" size={22} />
              <div>
                <h4 className="text-[14px] font-semibold text-emerald-700 mb-1">可以说</h4>
                <p className="text-[13px] leading-6 text-text-secondary">
                  {compactList(asArray(boundaries.claims_we_can_make), 5) || "待补充"}
                </p>
              </div>
            </div>
            <div className="rounded-lg border border-amber-200 bg-amber-50/70 p-4 flex gap-3">
              <CircleAlert className="text-amber-600 shrink-0 mt-0.5" size={22} />
              <div>
                <h4 className="text-[14px] font-semibold text-amber-700 mb-1">不能乱说</h4>
                <p className="text-[13px] leading-6 text-text-secondary">
                  {compactList(asArray(boundaries.claims_we_cannot_make), 5) || "待补充"}
                </p>
              </div>
            </div>
            <div className="rounded-lg border border-blue-200 bg-blue-50/60 p-4 flex gap-3">
              <XCircle className="text-brand-blue shrink-0 mt-0.5" size={22} />
              <div>
                <h4 className="text-[14px] font-semibold text-brand-blue mb-1">敏感话题</h4>
                <p className="text-[13px] leading-6 text-text-secondary">
                  {compactList(asArray(boundaries.sensitive_topics), 5) || "待补充"}
                </p>
              </div>
            </div>
          </div>
        </section>

        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 text-[12px] text-text-tertiary">
          <span>更新时间：{profile.collectedAt || profile.metadata?.updatedAt || profile.metadata?.updated_at || "-"}</span>
          <span>来源页面：{sourceUrls.length || 0} 个，完整内容请导出 Word 查看</span>
        </div>
      </div>
    </div>
  );
}
