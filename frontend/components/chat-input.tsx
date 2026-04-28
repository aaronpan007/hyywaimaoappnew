"use client";

import React, { useState, useRef, KeyboardEvent } from "react";
import { SendHorizontal } from "lucide-react";

interface ChatInputProps {
  onSend: (message: string) => void;
  placeholder?: string;
  disabled?: boolean;
  isStreaming?: boolean;
}

export default function ChatInput({
  onSend,
  placeholder = "告诉我你想找什么样的客户...",
  disabled = false,
  isStreaming = false,
}: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
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
      <div className="flex items-end gap-2 max-w-[800px] mx-auto border border-text-border rounded-xl bg-surface-white px-4 py-2 transition-colors focus-within:border-brand-blue/40">
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
          disabled={!value.trim() || disabled || isStreaming}
          className="w-8 h-8 rounded-full bg-brand-blue flex items-center justify-center shrink-0 mb-1 transition-all duration-150 disabled:opacity-30 disabled:cursor-not-allowed hover:bg-brand-blue-hover active:scale-95"
        >
          <SendHorizontal size={16} className="text-white" />
        </button>
      </div>
    </div>
  );
}
