"use client";

import React from "react";
import {
  Plus,
  Building2,
  Mail,
  Search,
  UsersRound,
  ChevronRight,
  LogOut,
  CircleUserRound,
  MoreHorizontal,
  Pencil,
  Trash2,
} from "lucide-react";
import type { NavItem, ChatHistoryItem } from "@/types";

interface SidebarProps {
  activeNav: NavItem;
  onNavChange: (nav: NavItem) => void;
  chatHistory: ChatHistoryItem[];
  activeSessionId: string | null;
  onSelectChat: (sessionId: string) => void;
  onRenameChat: (sessionId: string, title: string) => void;
  onDeleteChat: (sessionId: string) => void;
  userEmail?: string;
  onSignOut: () => void;
}

export default function Sidebar({
  activeNav,
  onNavChange,
  chatHistory,
  activeSessionId,
  onSelectChat,
  onRenameChat,
  onDeleteChat,
  userEmail,
  onSignOut,
}: SidebarProps) {
  const [openMenuId, setOpenMenuId] = React.useState<string | null>(null);

  const handleRename = (item: ChatHistoryItem) => {
    setOpenMenuId(null);
    const nextTitle = window.prompt("重命名聊天记录", item.title)?.trim();
    if (nextTitle && nextTitle !== item.title) {
      onRenameChat(item.id, nextTitle);
    }
  };

  const handleDelete = (item: ChatHistoryItem) => {
    setOpenMenuId(null);
    if (window.confirm(`删除“${item.title}”这条聊天记录吗？`)) {
      onDeleteChat(item.id);
    }
  };

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
          onClick={() => onNavChange("customer-list")}
          className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-[14px] transition-colors duration-150 ${
            activeNav === "customer-list"
              ? "bg-brand-blue-light text-brand-blue"
              : "text-text-primary hover:bg-gray-100"
          }`}
        >
          <UsersRound size={16} strokeWidth={1.8} />
          <span>客户名单</span>
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
        {chatHistory.map((item) => (
          <div
            key={item.id}
            className="relative group"
          >
            <button
              onClick={() => onSelectChat(item.id)}
              className={`w-full flex items-center px-3 py-1.5 pr-8 rounded-lg text-[13px] transition-colors duration-150 ${
              item.id === activeSessionId
                ? "bg-brand-blue-light text-brand-blue"
                : "text-text-secondary hover:bg-gray-100"
              }`}
            >
              <span className="truncate flex-1 text-left">{item.title}</span>
            </button>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setOpenMenuId((current) => (current === item.id ? null : item.id));
              }}
              className={`absolute right-1.5 top-1/2 flex h-6 w-6 -translate-y-1/2 items-center justify-center rounded-md text-text-tertiary transition hover:bg-white hover:text-text-primary ${
                openMenuId === item.id ? "opacity-100" : "opacity-0 group-hover:opacity-100"
              }`}
              aria-label="聊天记录操作"
            >
              <MoreHorizontal size={16} />
            </button>
            {openMenuId === item.id && (
              <div
                className="absolute right-1.5 top-7 z-20 w-32 rounded-lg border border-text-border bg-white py-1 shadow-lg"
                onClick={(e) => e.stopPropagation()}
              >
                <button
                  type="button"
                  onClick={() => handleRename(item)}
                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-[13px] text-text-primary hover:bg-gray-50"
                >
                  <Pencil size={14} />
                  重命名
                </button>
                <button
                  type="button"
                  onClick={() => handleDelete(item)}
                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-[13px] text-red-600 hover:bg-red-50"
                >
                  <Trash2 size={14} />
                  删除
                </button>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Bottom */}
      <div className="space-y-2 border-t border-text-border px-3 py-3">
        <button className="flex items-center gap-1.5 px-1 text-[13px] text-brand-blue transition-colors hover:text-brand-blue-hover">
          <span>升级计划</span>
          <ChevronRight size={14} />
        </button>
        <div className="flex items-center gap-2 rounded-lg bg-white px-2 py-2">
          <CircleUserRound size={17} className="shrink-0 text-text-secondary" />
          <span className="min-w-0 flex-1 truncate text-[12px] text-text-secondary">
            {userEmail || "已登录"}
          </span>
          <button
            type="button"
            onClick={onSignOut}
            className="rounded-md p-1 text-text-tertiary transition hover:bg-gray-100 hover:text-text-primary"
            title="退出登录"
            aria-label="退出登录"
          >
            <LogOut size={15} />
          </button>
        </div>
      </div>
    </aside>
  );
}
