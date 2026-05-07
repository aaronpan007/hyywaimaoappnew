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
  const mailDomain = (settings?.mailDomain || "clientconnet.com").replace(/^@+/, "");
  const [senderName, setSenderName] = useState(settings?.senderName || "");
  const [replyToEmail, setReplyToEmail] = useState(
    settings?.replyToEmail || ""
  );
  const [prefix, setPrefix] = useState(settings?.fromEmailPrefix || "");
  const hasConfirmedConfig = Boolean(settings?.configuredAt);

  useEffect(() => {
    if (settings) {
      setSenderName(settings.senderName);
      setReplyToEmail(settings.replyToEmail);
      setPrefix(settings.fromEmailPrefix);
    }
  }, [settings]);

  const handleSave = () => {
    const cleanedPrefix = prefix.trim().replace(/^@+/, "").split("@", 1)[0];
    onSave({
      senderName: senderName.trim(),
      replyToEmail: replyToEmail.trim(),
      fromEmailPrefix: cleanedPrefix,
      mailDomain,
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
        {isConfigured && !hasConfirmedConfig && (
          <p className="text-[14px] text-text-secondary mb-6">
            系统已根据公司资料填好推荐配置，请确认后保存。之后发送开发信会使用这套发件信息。
          </p>
        )}

        {isConfigured && hasConfirmedConfig && <div className="h-px bg-text-border mb-6" />}
        {!isConfigured && <div className="mb-6" />}

        {/* Config Card */}
        <div className="border border-text-border rounded-xl p-5">
          {/* Sender Name */}
          <div className="mb-5">
            <label className="text-[13px] font-medium text-gray-700 block mb-1">
              发件人名称
            </label>
            <input
              type="text"
              value={senderName}
              onChange={(e) => setSenderName(e.target.value)}
              placeholder="如：PRANCE、Lisa from PRANCE"
              className="w-full h-11 px-3 bg-surface-input rounded-xl text-[14px] text-text-primary placeholder:text-text-tertiary outline-none border border-transparent focus:border-brand-blue/40 transition-colors"
            />
          </div>

          {/* From Email */}
          {isConfigured && (
            <div className="mb-5">
              <label className="text-[13px] font-medium text-gray-700 block mb-1">
                发件邮箱
              </label>
              <div className="flex items-center h-11 bg-surface-input rounded-xl overflow-hidden border border-transparent focus-within:border-brand-blue/40 transition-colors">
                <input
                  type="text"
                  value={prefix}
                  onChange={(e) => setPrefix(e.target.value)}
                  className="flex-1 h-full px-3 bg-transparent text-[14px] text-text-primary outline-none"
                />
                <span className="text-[14px] text-text-tertiary pr-3 whitespace-nowrap">
                  @{mailDomain}
                </span>
              </div>
            </div>
          )}

          {/* Reply-to Email */}
          <div className="mb-2">
            <label className="text-[13px] font-medium text-gray-700 block mb-1">
              回复接收邮箱
            </label>
            <input
              type="email"
              value={replyToEmail}
              onChange={(e) => setReplyToEmail(e.target.value)}
              placeholder="客户的回复会回传到填写的邮箱地址"
              className="w-full h-11 px-3 bg-surface-input rounded-xl text-[14px] text-text-primary placeholder:text-text-tertiary outline-none border border-transparent focus:border-brand-blue/40 transition-colors"
            />
          </div>
        </div>

        {/* Live Preview */}
        <div className="mt-4 border border-text-border rounded-xl p-4">
          <p className="text-[12px] text-text-tertiary mb-2">发件人预览</p>
          <div className="flex items-center gap-2 min-h-[28px]">
            {senderName.trim() || prefix.trim() ? (
              <>
                <span className="text-[14px] font-semibold text-text-primary">
                  {senderName.trim() || "发件人名称"}
                </span>
                {prefix.trim() && (
                  <span className="text-[14px] text-text-tertiary">
                    &lt;{prefix.trim()}@{mailDomain}&gt;
                  </span>
                )}
              </>
            ) : (
              <span className="text-[14px] text-text-tertiary">
                输入名称或邮箱后将在此预览
              </span>
            )}
          </div>
        </div>

        {/* Save Button */}
        <button
          onClick={handleSave}
          className="w-full h-11 bg-brand-blue text-white text-[14px] font-medium rounded-xl hover:bg-brand-blue-hover transition-colors active:scale-[0.98] mt-4 flex items-center justify-center gap-1.5"
        >
          <Save size={15} />
          <span>{isConfigured ? "保存修改" : "保存配置"}</span>
        </button>

      </div>
    </div>
  );
}
