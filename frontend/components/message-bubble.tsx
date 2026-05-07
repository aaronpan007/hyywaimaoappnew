"use client";

import React from "react";
import { Paperclip } from "lucide-react";
import type { ChatMessage } from "@/types";
import CalloutCard from "./callout-card";
import ConfirmParamsCard from "./confirm-params-card";
import EmailCraftConfirmCard from "./email-craft-confirm-card";
import PipelineTimeline from "./pipeline-timeline";

interface MessageBubbleProps {
  message: ChatMessage;
  onViewList?: (taskId?: number) => void;
  onDownloadExcel?: (taskId?: number) => void;
  onDownloadEmails?: (taskId?: number) => void;
  onViewProfile?: () => void;
  onViewEmails?: (taskId?: number) => void;
  onStopTask?: () => void;
  onConfirmParams?: (params: {
    industry: string;
    country: string;
    keywords: string[];
    num: number;
  }) => void;
  onConfirmEmailCraft?: (files?: { filename: string; data: string }[]) => void;
  onCancelConfirm?: () => void;
  onGoToCustomerList?: () => void;
}

export default function MessageBubble({
  message,
  onViewList,
  onDownloadExcel,
  onDownloadEmails,
  onViewProfile,
  onViewEmails,
  onStopTask,
  onConfirmParams,
  onConfirmEmailCraft,
  onCancelConfirm,
  onGoToCustomerList,
}: MessageBubbleProps) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end animate-fade-in-up">
        <div className="max-w-[70%] bg-surface-msg-user rounded-xl px-4 py-2.5">
          <p className="text-[14px] text-text-primary leading-relaxed whitespace-pre-wrap">
            {message.content}
          </p>
          {message.attachments && message.attachments.length > 0 && (
            <div className="mt-2 flex flex-col gap-1">
              {message.attachments.map((file, index) => (
                <div
                  key={`${file.name}-${index}`}
                  className="inline-flex max-w-full items-center gap-1.5 rounded-md bg-white/70 px-2 py-1 text-[12px] text-text-secondary"
                >
                  <Paperclip size={12} />
                  <span className="truncate">{file.name}</span>
                  <span className="shrink-0 text-text-tertiary">
                    {Math.round(file.size / 1024)} KB
                  </span>
                </div>
              ))}
            </div>
          )}
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
            onDownloadEmails={onDownloadEmails}
            onViewProfile={onViewProfile}
            onViewEmails={onViewEmails}
            onGoToCustomerList={onGoToCustomerList}
          />
        </div>
      )}

      {/* Confirm params card */}
      {message.confirmParams && (
        <div className="mt-2">
          {message.confirmParams.confirmType === "email_craft" ? (
            <EmailCraftConfirmCard
              data={message.confirmParams as any}
              onConfirm={onConfirmEmailCraft || (() => {})}
              onCancel={onCancelConfirm || (() => {})}
              onGoToCustomerList={onGoToCustomerList}
            />
          ) : (
            <ConfirmParamsCard
              initialParams={message.confirmParams}
              onConfirm={onConfirmParams || (() => {})}
              onCancel={onCancelConfirm || (() => {})}
            />
          )}
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
