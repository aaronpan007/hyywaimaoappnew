"use client";

import React from "react";
import type { ChatMessage, PageView, EmailSettings } from "@/types";
import WelcomeScreen from "./welcome-screen";
import MessageList from "./message-list";
import ChatInput from "./chat-input";
import CompanyProfilePage from "./company-profile";
import EmailConfigPage from "./email-config";

interface ChatAreaProps {
  view: PageView;
  messages: ChatMessage[];
  onSendMessage: (message: string) => void;
  onCreateChat: (title?: string) => void;
  onViewList: () => void;
  onDownloadExcel: () => void;
  onStopTask?: () => void;
  onConfirmParams?: (params: {
    industry: string;
    country: string;
    keywords: string[];
    num: number;
  }) => void;
  onCancelConfirm?: () => void;
  companyProfile: any | null;
  emailSettings: EmailSettings | null;
  onBackToChat: () => void;
  onStartCollect: () => void;
  onRecollect: () => void;
  onExportProfile: () => void;
  onSaveEmailSettings: (settings: EmailSettings) => void;
  isStreaming?: boolean;
  isLoading?: boolean;
}

export default function ChatArea({
  view,
  messages,
  onSendMessage,
  onCreateChat,
  onViewList,
  onDownloadExcel,
  onStopTask,
  onConfirmParams,
  onCancelConfirm,
  companyProfile,
  emailSettings,
  onBackToChat,
  onStartCollect,
  onRecollect,
  onExportProfile,
  onSaveEmailSettings,
  isStreaming = false,
  isLoading = false,
}: ChatAreaProps) {
  switch (view) {
    case "welcome":
      return <WelcomeScreen onSend={onSendMessage} onCreateChat={onCreateChat} isLoading={isLoading} disabled={isStreaming} />;

    case "chat":
      return (
        <div className="flex flex-col h-full">
          <MessageList
            messages={messages}
            onViewList={onViewList}
            onDownloadExcel={onDownloadExcel}
            onStopTask={onStopTask}
            onConfirmParams={onConfirmParams}
            onCancelConfirm={onCancelConfirm}
            isStreaming={isStreaming}
          />
          <ChatInput
            onSend={onSendMessage}
            disabled={isStreaming}
            isStreaming={isStreaming}
          />
        </div>
      );

    case "company-profile":
      return (
        <div className="flex flex-col h-full">
          <CompanyProfilePage
            profile={companyProfile}
            onBack={onBackToChat}
            onStartCollect={onStartCollect}
            onRecollect={onRecollect}
            onExport={onExportProfile}
          />
        </div>
      );

    case "email-config":
      return (
        <div className="flex flex-col h-full">
          <EmailConfigPage
            settings={emailSettings}
            onBack={onBackToChat}
            onSave={onSaveEmailSettings}
          />
        </div>
      );
  }
}
