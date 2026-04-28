"use client";

import React from "react";
import type { ChatMessage } from "@/types";
import CalloutCard from "./callout-card";
import ConfirmParamsCard from "./confirm-params-card";
import PipelineTimeline from "./pipeline-timeline";

interface MessageBubbleProps {
  message: ChatMessage;
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
}

export default function MessageBubble({
  message,
  onViewList,
  onDownloadExcel,
  onStopTask,
  onConfirmParams,
  onCancelConfirm,
}: MessageBubbleProps) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end animate-fade-in-up">
        <div className="max-w-[70%] bg-surface-msg-user rounded-xl px-4 py-2.5">
          <p className="text-[14px] text-text-primary leading-relaxed whitespace-pre-wrap">
            {message.content}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1 animate-fade-in-up max-w-[600px]">
      {/* Text content */}
      {message.content && (
        <p className="text-[14px] text-text-primary leading-relaxed whitespace-pre-wrap">
          {message.content}
        </p>
      )}

      {/* Callout card */}
      {message.callout && (
        <div className="mt-2">
          <CalloutCard
            data={message.callout}
            onViewList={onViewList}
            onDownloadExcel={onDownloadExcel}
          />
        </div>
      )}

      {/* Confirm params card */}
      {message.confirmParams && (
        <div className="mt-2">
          <ConfirmParamsCard
            initialParams={message.confirmParams}
            onConfirm={onConfirmParams || (() => {})}
            onCancel={onCancelConfirm || (() => {})}
          />
        </div>
      )}

      {/* Timeline */}
      {message.timeline && (
        <div className="mt-2">
          <PipelineTimeline data={message.timeline} onStopTask={onStopTask} />
        </div>
      )}

      {/* Timestamp — hidden for now, no real time data */}
    </div>
  );
}
