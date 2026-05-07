"use client";

import React, { useState, useRef, KeyboardEvent } from "react";
import { Paperclip, SendHorizontal, X } from "lucide-react";

interface ChatInputProps {
  onSend: (message: string, files?: File[]) => void;
  placeholder?: string;
  disabled?: boolean;
  isStreaming?: boolean;
  allowFiles?: boolean;
}

export default function ChatInput({
  onSend,
  placeholder = "告诉我你想找什么样的客户...",
  disabled = false,
  isStreaming = false,
  allowFiles = false,
}: ChatInputProps) {
  const [value, setValue] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSend = () => {
    const trimmed = value.trim();
    if ((!trimmed && files.length === 0) || disabled) return;
    onSend(trimmed, files);
    setValue("");
    setFiles([]);
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (isStreaming) return;
      handleSend();
    }
  };

  const handleInput = () => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = Math.min(el.scrollHeight, 160) + "px";
    }
  };

  return (
    <div className="px-4 pb-6 pt-0">
      <div className="max-w-[800px] mx-auto border border-text-border rounded-xl bg-surface-white px-3 py-2 transition-colors focus-within:border-brand-blue/40">
        {files.length > 0 && (
          <div className="flex flex-wrap gap-2 pb-2">
            {files.map((file, index) => (
              <div
                key={`${file.name}-${index}`}
                className="inline-flex items-center gap-1.5 max-w-[260px] rounded-md bg-surface-input px-2 py-1 text-[12px] text-text-secondary"
              >
                <Paperclip size={12} />
                <span className="truncate">{file.name}</span>
                <button
                  type="button"
                  onClick={() => setFiles((prev) => prev.filter((_, i) => i !== index))}
                  className="text-text-tertiary hover:text-text-primary"
                >
                  <X size={12} />
                </button>
              </div>
            ))}
          </div>
        )}

        <div className="flex items-end gap-2">
          {allowFiles && (
            <>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                className="hidden"
                accept=".pdf,.doc,.docx,.xls,.xlsx,.csv,.txt,.md,.json,.png,.jpg,.jpeg"
                onChange={(e) => {
                  const selected = Array.from(e.target.files || []);
                  setFiles((prev) => [...prev, ...selected].slice(0, 8));
                  e.target.value = "";
                }}
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={disabled || isStreaming}
                className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 mb-1 text-text-tertiary hover:text-brand-blue hover:bg-brand-blue-light disabled:opacity-40"
                title="上传公司资料"
              >
                <Paperclip size={16} />
              </button>
            </>
          )}

          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={disabled || isStreaming}
            onInput={handleInput}
            placeholder={isStreaming ? "任务执行中..." : placeholder}
            rows={1}
            className="flex-1 resize-none bg-transparent text-[14px] text-text-primary placeholder:text-text-tertiary outline-none py-2 leading-relaxed max-h-40"
          />
        <button
          onClick={handleSend}
            disabled={(!value.trim() && files.length === 0) || disabled || isStreaming}
          className="w-8 h-8 rounded-full bg-brand-blue flex items-center justify-center shrink-0 mb-1 transition-all duration-150 disabled:opacity-30 disabled:cursor-not-allowed hover:bg-brand-blue-hover active:scale-95"
        >
          <SendHorizontal size={16} className="text-white" />
        </button>
        </div>
      </div>
    </div>
  );
}
