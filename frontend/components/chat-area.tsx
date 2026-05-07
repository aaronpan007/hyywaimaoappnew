"use client";

import React from "react";
import type { ChatMessage, PageView, EmailSettings } from "@/types";
import WelcomeScreen from "./welcome-screen";
import MessageList from "./message-list";
import ChatInput from "./chat-input";
import CustomerListPage from "./customer-list";
import CompanyProfilePage from "./company-profile";
import EmailConfigPage from "./email-config";

interface ChatAreaProps {
  view: PageView;
  messages: ChatMessage[];
  onSendMessage: (message: string, files?: File[]) => void;
  onCreateChat: (title?: string) => void;
  onViewList: (taskId?: number) => void;
  onDownloadExcel: (taskId?: number) => void;
  onDownloadEmails?: (taskId?: number) => void;
  onViewProfile: () => void;
  onViewEmails?: (taskId?: number) => void;
  onStopTask?: () => void;
  onConfirmParams?: (params: {
    industry: string;
    country: string;
    keywords: string[];
    num: number;
    confirmType?: string;
    leadCount?: number;
    language?: string;
  }) => void;
  onConfirmEmailCraft?: (files?: { filename: string; data: string }[]) => void;
  onCancelConfirm?: () => void;
  companyProfile: any | null;
  emailSettings: EmailSettings | null;
  onBackToChat: () => void;
  onStartCollect: () => void;
  onSupplement: () => void;
  onRecollect: () => void;
  onExportProfile: () => void;
  onSaveEmailSettings: (settings: EmailSettings) => void;
  onGenerateEmails?: (leadIds: number[], language: string) => void;
  onGoToEmailConfig?: () => void;
  onSendEmails?: (
    leadIds: number[],
    settings: {
      delayMin: number;
      delayMax: number;
      dailyLimit: number;
      dryRun: false;
      sendMode: "immediate" | "auto";
    }
  ) => void;
  onGoToCustomerList?: () => void;
  isStreaming?: boolean;
  isLoading?: boolean;
  inputPlaceholder?: string;
  allowFileUpload?: boolean;
}

export default function ChatArea({
  view,
  messages,
  onSendMessage,
  onCreateChat,
  onViewList,
  onDownloadExcel,
  onDownloadEmails,
  onViewProfile,
  onViewEmails,
  onStopTask,
  onConfirmParams,
  onConfirmEmailCraft,
  onCancelConfirm,
  companyProfile,
  emailSettings,
  onBackToChat,
  onStartCollect,
  onSupplement,
  onRecollect,
  onExportProfile,
  onSaveEmailSettings,
  onGenerateEmails,
  onGoToEmailConfig,
  onSendEmails,
  onGoToCustomerList,
  isStreaming = false,
  isLoading = false,
  inputPlaceholder,
  allowFileUpload = false,
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
            onDownloadEmails={onDownloadEmails}
            onViewProfile={onViewProfile}
            onViewEmails={onViewEmails}
            onStopTask={onStopTask}
            onConfirmParams={onConfirmParams}
            onConfirmEmailCraft={onConfirmEmailCraft}
            onCancelConfirm={onCancelConfirm}
            onGoToCustomerList={onGoToCustomerList}
            isStreaming={isStreaming}
          />
          <ChatInput
            onSend={onSendMessage}
            placeholder={inputPlaceholder}
            allowFiles={allowFileUpload}
            disabled={isStreaming}
            isStreaming={isStreaming}
          />
        </div>
      );

    case "customer-list":
      return (
        <CustomerListPage
          onGenerateEmails={onGenerateEmails}
          emailSettings={emailSettings}
          onGoToEmailConfig={onGoToEmailConfig}
          onSendEmails={onSendEmails}
        />
      );

    case "company-profile":
      return (
        <div className="flex flex-col h-full">
          <CompanyProfilePage
            profile={companyProfile}
            onBack={onBackToChat}
            onStartCollect={onStartCollect}
            onSupplement={onSupplement}
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
