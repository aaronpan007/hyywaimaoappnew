"use client";

import React from "react";
import type { ChatMessage } from "@/types";
import MessageBubble from "./message-bubble";

interface MessageListProps {
  messages: ChatMessage[];
  onViewList?: () => void;
  onDownloadExcel?: () => void;
  onStopTask?: () => void;
  onConfirmParams?: (params: {
    industry: string;
    country: string;
    keywords: string[];
    num: number;
  }) => void;
  onCancelConfirm?: () => void;
  isStreaming?: boolean;
}

export default function MessageList({
  messages,
  onViewList,
  onDownloadExcel,
  onStopTask,
  onConfirmParams,
  onCancelConfirm,
  isStreaming = false,
}: MessageListProps) {
  const scrollRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  return (
    <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 pt-12 pb-6">
      <div className="max-w-[800px] mx-auto flex flex-col gap-6">
        {messages.map((msg) => (
          <MessageBubble
            key={msg.id}
            message={msg}
            onViewList={onViewList}
            onDownloadExcel={onDownloadExcel}
            onStopTask={onStopTask}
            onConfirmParams={onConfirmParams}
            onCancelConfirm={onCancelConfirm}
          />
        ))}
      </div>
    </div>
  );
}
