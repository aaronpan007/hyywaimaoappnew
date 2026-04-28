"use client";

import React, { useState, useEffect } from "react";
import { Mail, ChevronLeft, Save } from "lucide-react";
import type { EmailSettings } from "@/types";

interface EmailConfigPageProps {
  settings: EmailSettings | null;
  onBack: () => void;
  onSave: (settings: EmailSettings) => void;
}

export default function EmailConfigPage({
  settings,
  onBack,
  onSave,
}: EmailConfigPageProps) {
  const [senderName, setSenderName] = useState(settings?.senderName || "");
  const [replyToEmail, setReplyToEmail] = useState(
    settings?.replyToEmail || ""
  );
  const [prefix, setPrefix] = useState(settings?.fromEmailPrefix || "");

  useEffect(() => {
    if (settings) {
      setSenderName(settings.senderName);
      setReplyToEmail(settings.replyToEmail);
      setPrefix(settings.fromEmailPrefix);
    }
  }, [settings]);

  const handleSave = () => {
    onSave({
      senderName,
      replyToEmail,
      fromEmailPrefix: prefix,
      mailDomain: settings?.mailDomain || "mail.yourdomain.com",
      configuredAt: new Date().toISOString().split("T")[0],
    });
  };

  const isConfigured = !!settings;

  return (
    <div className="flex-1 flex items-center justify-center px-4">
      <div className="w-full max-w-[480px]">
        {isConfigured && (
          <button
            onClick={onBack}
            className="flex items-center gap-1 text-[14px] text-brand-blue hover:text-brand-blue-hover transition-colors mb-6"
          >
            <ChevronLeft size={16} />
            <span>返回对话</span>
          </button>
        )}

        {!isConfigured && (
          <div className="flex justify-center mb-4">
            <Mail size={48} strokeWidth={1} className="text-gray-300" />
          </div>
        )}

        <h2 className="text-[20px] font-semibold text-text-primary mb-1">
          {isConfigured ? "邮箱配置" : "邮箱配置"}
        </h2>

        {!isConfigured && (
          <p className="text-[14px] text-text-secondary mb-6">
            配置后即可通过 AI 批量发送开发信。
          </p>
        )}

        {isConfigured && <div className="h-px bg-text-border mb-6" />}
        {!isConfigured && <div className="mb-6" />}

        {/* Config Card */}
        <div className="border border-text-border rounded-xl p-5">
          {/* Sender Name */}
          <div className="mb-5">
            <label className="text-[13px] font-medium text-gray-700 block mb-1">
              发件人名称
            </label>
            <p className="text-[12px] text-text-tertiary mb-2">
              客户收到邮件时看到的发件人名称
            </p>
            <input
              type="text"
              value={senderName}
              onChange={(e) => setSenderName(e.target.value)}
              placeholder="如：张经理、Lisa from GMLight"
              className="w-full h-11 px-3 bg-surface-input rounded-xl text-[14px] text-text-primary placeholder:text-text-tertiary outline-none border border-transparent focus:border-brand-blue/40 transition-colors"
            />
          </div>

          {/* Reply-to Email */}
          <div className="mb-5">
            <label className="text-[13px] font-medium text-gray-700 block mb-1">
              回复接收邮箱
            </label>
            <p className="text-[12px] text-text-tertiary mb-2">
              客户回复邮件时发送到此地址
            </p>
            <input
              type="email"
              value={replyToEmail}
              onChange={(e) => setReplyToEmail(e.target.value)}
              placeholder="如：zhang@gmail.com"
              className="w-full h-11 px-3 bg-surface-input rounded-xl text-[14px] text-text-primary placeholder:text-text-tertiary outline-none border border-transparent focus:border-brand-blue/40 transition-colors"
            />
          </div>

          {/* From Email (only if configured) */}
          {isConfigured && (
            <div className="mb-2">
              <label className="text-[13px] font-medium text-gray-700 block mb-1">
                发件邮箱（系统自动生成）
              </label>
              <div className="flex items-center h-11 bg-surface-input rounded-xl overflow-hidden border border-transparent focus-within:border-brand-blue/40 transition-colors">
                <input
                  type="text"
                  value={prefix}
                  onChange={(e) => setPrefix(e.target.value)}
                  className="flex-1 h-full px-3 bg-transparent text-[14px] text-text-primary outline-none"
                />
                <span className="text-[14px] text-text-tertiary pr-3 whitespace-nowrap">
                  @{settings?.mailDomain || "mail.yourdomain.com"}
                </span>
              </div>
              <p className="text-[12px] text-text-tertiary mt-2 leading-relaxed">
                域名由平台统一管理，您只需设定前缀。默认前缀取自您公司名，可自行修改。
              </p>
            </div>
          )}
        </div>

        {/* Save Button */}
        <button
          onClick={handleSave}
          className="w-full h-11 bg-brand-blue text-white text-[14px] font-medium rounded-xl hover:bg-brand-blue-hover transition-colors active:scale-[0.98] mt-4 flex items-center justify-center gap-1.5"
        >
          <Save size={15} />
          <span>{isConfigured ? "保存修改" : "保存配置"}</span>
        </button>

        {isConfigured && settings.configuredAt && (
          <p className="text-[12px] text-text-tertiary text-center mt-3">
            配置时间：{settings.configuredAt}
          </p>
        )}
      </div>
    </div>
  );
}
