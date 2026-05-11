"use client";

import React, { useRef, useState, useCallback } from "react";
import { PenLine, Upload, Users } from "lucide-react";
import type { EmailCraftConfirmData } from "@/types";

interface EmailCraftConfirmCardProps {
  data: EmailCraftConfirmData;
  onConfirm: (files?: { filename: string; data: string }[], userRequirements?: string) => void;
  onCancel: () => void;
  onGoToCustomerList?: (userRequirements?: string) => void;
}

export default function EmailCraftConfirmCard({
  data,
  onConfirm,
  onCancel,
  onGoToCustomerList,
}: EmailCraftConfirmCardProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [userRequirements, setUserRequirements] = useState(
    data.userRequirements || ""
  );

  const langText = data.language === "cn" ? "中文" : "英文";

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const triggerConfirm = useCallback(
    (files?: { filename: string; data: string }[]) => {
      onConfirm(files, userRequirements);
    },
    [onConfirm, userRequirements]
  );

  const handleFileChange = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (!files || files.length === 0) return;

      const filePromises = Array.from(files).map(
        (file) =>
          new Promise<{ filename: string; data: string }>((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => {
              const base64 = (reader.result as string).split(",")[1] || "";
              resolve({ filename: file.name, data: base64 });
            };
            reader.onerror = reject;
            reader.readAsDataURL(file);
          })
      );

      try {
        const uploadedFiles = await Promise.all(filePromises);
        triggerConfirm(uploadedFiles);
      } catch {
        alert("文件读取失败，请重试");
      }

      // Reset input
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    },
    [triggerConfirm]
  );

  return (
    <div className="border border-text-border rounded-xl p-4 bg-surface-white">
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <div className="w-7 h-7 rounded-lg bg-brand-blue-light flex items-center justify-center">
          <PenLine size={15} strokeWidth={2} className="text-brand-blue" />
        </div>
        <span className="text-[14px] font-semibold text-text-primary">
          开始生成开发信
        </span>
      </div>

      {/* Reply text */}
      {data.reply && (
        <p className="text-[13px] text-text-secondary mb-3 pl-1">
          {data.reply}
        </p>
      )}

      {/* Stats */}
      <div className="pl-1 mb-3">
        <span className="text-[13px] text-text-secondary">
          您有 <span className="font-medium text-text-primary">{data.leadCount}</span> 条线索，{langText}开发信
        </span>
      </div>

      {/* User requirements input */}
      <div className="mb-3 pl-1">
        <label className="block text-[12px] text-text-secondary mb-1">
          补充要求（可选）
        </label>
        <textarea
          value={userRequirements}
          onChange={(e) => setUserRequirements(e.target.value)}
          placeholder="例如：邮件中提到我们做过白云机场项目、语气正式一些..."
          rows={2}
          className="w-full px-3 py-2 text-[13px] text-text-primary border border-text-border rounded-lg resize-none focus:outline-none focus:ring-1 focus:ring-brand-blue focus:border-brand-blue placeholder:text-text-placeholder bg-transparent"
        />
      </div>

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".xlsx,.xls,.csv,.docx"
        multiple
        onChange={handleFileChange}
        className="hidden"
      />

      {/* Actions */}
      <div className="flex items-center gap-2">
        <button
          onClick={handleUploadClick}
          className="flex items-center gap-1.5 px-3.5 py-1.5 border border-brand-blue text-brand-blue rounded-lg text-[13px] font-medium hover:bg-brand-blue-light transition-colors"
        >
          <Upload size={14} />
          上传客户资料并开始
        </button>
        <button
          onClick={() => {
            onCancel();
            onGoToCustomerList?.(userRequirements);
          }}
          className="flex items-center gap-1.5 px-3.5 py-1.5 bg-brand-blue text-white rounded-lg text-[13px] font-medium hover:bg-brand-blue-hover transition-colors"
        >
          <Users size={14} />
          前往客户名单选择
        </button>
        <button
          onClick={onCancel}
          className="px-3.5 py-1.5 border border-text-border rounded-lg text-[13px] font-medium text-text-secondary hover:bg-gray-50 transition-colors ml-auto"
        >
          取消
        </button>
      </div>
    </div>
  );
}
