"use client";

import React from "react";
import { Building2, Search, PenLine, Send, ArrowRight } from "lucide-react";
import type { FeatureCardData } from "@/types";

const iconMap: Record<string, React.ElementType> = {
  "building2": Building2,
  "search": Search,
  "pen-line": PenLine,
  "send": Send,
};

interface FeatureCardProps {
  data: FeatureCardData;
  index: number;
  onClick: () => void;
}

export default function FeatureCard({ data, index, onClick }: FeatureCardProps) {
  const Icon = iconMap[data.icon] || Building2;

  return (
    <button
      onClick={onClick}
      className="animate-fade-in-up opacity-0 group flex flex-col items-start p-4 rounded-xl border border-text-border bg-surface-white hover:border-brand-blue/30 hover:shadow-sm transition-all duration-200 text-left"
      style={{ animationDelay: `${(index + 1) * 80}ms` }}
    >
      <div className="flex items-start justify-between w-full">
        <div className="w-9 h-9 rounded-lg bg-brand-blue-light flex items-center justify-center mb-3">
          <Icon size={18} strokeWidth={1.8} className="text-brand-blue" />
        </div>
        <ArrowRight
          size={16}
          strokeWidth={1.8}
          className="text-text-tertiary group-hover:text-brand-blue group-hover:translate-x-0.5 transition-all duration-200 mt-0.5"
        />
      </div>
      <span className="text-[14px] font-medium text-text-primary mb-1">
        {data.title}
      </span>
      <span className="text-[12px] text-text-secondary leading-relaxed">
        {data.description}
      </span>
    </button>
  );
}
