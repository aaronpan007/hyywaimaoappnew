"use client";

import React from "react";
import {
  Search,
  Building2,
  PenLine,
  Send,
  CheckCircle,
  Settings,
  AlertCircle,
  MessageCircle,
} from "lucide-react";
import type { CalloutData } from "@/types";

const iconMap: Record<string, React.ElementType> = {
  search: Search,
  building2: Building2,
  "pen-line": PenLine,
  send: Send,
  "check-circle": CheckCircle,
  settings: Settings,
  "alert-circle": AlertCircle,
  "message-circle": MessageCircle,
};

interface CalloutCardProps {
  data: CalloutData;
  onViewList?: (taskId?: number) => void;
  onDownloadExcel?: (taskId?: number) => void;
  onDownloadEmails?: (taskId?: number) => void;
  onViewProfile?: () => void;
  onViewEmails?: (taskId?: number) => void;
  onGoSettings?: () => void;
  onGoToCustomerList?: () => void;
}

export default function CalloutCard({
  data,
  onViewList,
  onDownloadExcel,
  onDownloadEmails,
  onViewProfile,
  onViewEmails,
  onGoSettings,
  onGoToCustomerList,
}: CalloutCardProps) {
  const Icon = iconMap[data.icon] || CheckCircle;

  const handleAction = (type: string) => {
    switch (type) {
      case "view-list":
        onViewList?.(data.taskId);
        break;
      case "download-excel":
        onDownloadExcel?.(data.taskId);
        break;
      case "download-emails":
        onDownloadEmails?.(data.taskId);
        break;
      case "view-profile":
        onViewProfile?.();
        break;
      case "view-emails":
        onViewEmails?.(data.taskId);
        break;
      case "go-settings":
        onGoSettings?.();
        break;
      case "go-customer-list":
        onGoToCustomerList?.();
        break;
    }
  };

  return (
    <div className="border border-text-border rounded-xl p-4 bg-surface-white">
      {/* Header */}
      <div className="flex items-center gap-2 mb-2">
        <div className="w-7 h-7 rounded-lg bg-brand-blue-light flex items-center justify-center">
          <Icon size={15} strokeWidth={2} className="text-brand-blue" />
        </div>
        <span className="text-[14px] font-semibold text-text-primary">
          {data.title}
        </span>
      </div>

      {/* Stats */}
      <div className="flex flex-col gap-0.5 mb-3 pl-1">
        {data.summary && (
          <span className="text-[13px] text-text-secondary">
            {data.summary}
          </span>
        )}
        {data.stats.map((stat, i) => (
          <span key={i} className="text-[13px] text-text-secondary">
            {stat}
          </span>
        ))}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2">
        {data.actions.map((action) => (
          <button
            key={action.label}
            onClick={() => handleAction(action.type)}
            className={`px-3.5 py-1.5 rounded-lg text-[13px] font-medium transition-colors duration-150 ${
              action.variant === "filled"
                ? "bg-brand-blue text-white hover:bg-brand-blue-hover"
                : "border border-brand-blue text-brand-blue hover:bg-brand-blue-light"
            }`}
          >
            {action.label}
          </button>
        ))}
      </div>
    </div>
  );
}
