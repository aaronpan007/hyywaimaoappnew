"use client";

import React from "react";
import {
  Plus,
  Building2,
  Mail,
  Search,
  ChevronRight,
} from "lucide-react";
import type { NavItem, ChatHistoryItem } from "@/types";

interface SidebarProps {
  activeNav: NavItem;
  onNavChange: (nav: NavItem) => void;
  chatHistory: ChatHistoryItem[];
  activeSessionId: string | null;
  onSelectChat: (sessionId: string) => void;
}

export default function Sidebar({
  activeNav,
  onNavChange,
  chatHistory,
  activeSessionId,
  onSelectChat,
}: SidebarProps) {
  return (
    <aside className="w-sidebar h-full bg-surface-side-bg flex flex-col border-r border-text-border shrink-0">
      {/* Brand */}
      <div className="px-4 pt-5 pb-3">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-full bg-brand-blue flex items-center justify-center">
            <span className="text-white text-xs font-bold">W</span>
          </div>
          <span className="text-[15px] font-semibold text-text-primary truncate">
            你的AI外贸业务员
          </span>
        </div>
      </div>

      <div className="h-px bg-text-border mx-3" />

      {/* Navigation */}
      <nav className="px-2 py-2">
        <button
          onClick={() => onNavChange("new-chat")}
          className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-[14px] transition-colors duration-150 ${
            activeNav === "new-chat" && !activeSessionId
              ? "bg-brand-blue-light text-brand-blue"
              : "text-text-primary hover:bg-gray-100"
          }`}
        >
          <Plus size={16} strokeWidth={1.8} />
          <span>新对话</span>
        </button>
        <button
          onClick={() => onNavChange("company-profile")}
          className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-[14px] transition-colors duration-150 ${
            activeNav === "company-profile"
              ? "bg-brand-blue-light text-brand-blue"
              : "text-text-primary hover:bg-gray-100"
          }`}
        >
          <Building2 size={16} strokeWidth={1.8} />
          <span>公司资料</span>
        </button>
        <button
          onClick={() => onNavChange("email-config")}
          className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-[14px] transition-colors duration-150 ${
            activeNav === "email-config"
              ? "bg-brand-blue-light text-brand-blue"
              : "text-text-primary hover:bg-gray-100"
          }`}
        >
          <Mail size={16} strokeWidth={1.8} />
          <span>邮箱配置</span>
        </button>
      </nav>

      <div className="h-px bg-text-border mx-3" />

      {/* Search */}
      <div className="px-3 py-2.5">
        <div className="relative">
          <Search
            size={14}
            strokeWidth={1.8}
            className="absolute left-2.5 top-1/2 -translate-y-1/2 text-text-tertiary"
          />
          <input
            type="text"
            placeholder="搜索对话..."
            className="w-full h-8 pl-8 pr-3 bg-surface-input rounded-lg text-[13px] text-text-primary placeholder:text-text-tertiary outline-none border-none focus:ring-1 focus:ring-brand-blue/30"
          />
        </div>
      </div>

      <div className="h-px bg-text-border mx-3" />

      {/* Chat History */}
      <div className="flex-1 overflow-y-auto px-2 py-2">
        {chatHistory.length > 0 && (
          <div className="px-3 py-1.5">
            <span className="text-[12px] text-text-tertiary font-medium">今天</span>
          </div>
        )}
        {chatHistory.map((item) => (
          <button
            key={item.id}
            onClick={() => onSelectChat(item.id)}
            className={`w-full flex items-center justify-between px-3 py-1.5 rounded-lg text-[13px] transition-colors duration-150 group ${
              item.id === activeSessionId
                ? "bg-brand-blue-light text-brand-blue"
                : "text-text-secondary hover:bg-gray-100"
            }`}
          >
            <span className="truncate flex-1 text-left">{item.title}</span>
            <span className="text-[11px] text-text-tertiary ml-2 shrink-0">
              {item.timestamp.replace("分钟前", "m").replace("小时前", "h").replace("昨天", "1d").replace("天前", "d")}
            </span>
          </button>
        ))}
      </div>

      {/* Bottom */}
      <div className="px-4 py-3 border-t border-text-border">
        <button className="flex items-center gap-1.5 text-[13px] text-brand-blue hover:text-brand-blue-hover transition-colors">
          <span>升级计划</span>
          <ChevronRight size={14} />
        </button>
      </div>
    </aside>
  );
}
