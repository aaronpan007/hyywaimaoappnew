"use client";

import React from "react";
import { Check, Circle, Loader2, X, XCircle } from "lucide-react";
import type { TimelineData } from "@/types";

interface PipelineTimelineProps {
  data: TimelineData;
  onStopTask?: () => void;
}

export default function PipelineTimeline({ data, onStopTask }: PipelineTimelineProps) {
  const isCancelled = data.status === "cancelled";

  return (
    <div className="border border-text-border rounded-xl p-4 bg-surface-white">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          {data.status === "running" && (
            <Loader2
              size={16}
              strokeWidth={2}
              className="text-brand-blue animate-spin-slow"
            />
          )}
          {data.status === "completed" && (
            <Check size={16} strokeWidth={2} className="text-green-500" />
          )}
          {isCancelled && (
            <XCircle size={16} strokeWidth={2} className="text-amber-500" />
          )}
          {data.status === "failed" && (
            <XCircle size={16} strokeWidth={2} className="text-red-500" />
          )}
          <span className="text-[14px] font-semibold text-text-primary">
            {data.title}
          </span>
          {data.status === "running" && (
            <span className="text-[12px] text-brand-blue ml-1">执行中...</span>
          )}
          {isCancelled && (
            <span className="text-[12px] text-amber-500 ml-1">已取消</span>
          )}
          {data.status === "failed" && (
            <span className="text-[12px] text-red-500 ml-1">失败</span>
          )}
        </div>

        {/* Cancel button - top right, only when running */}
        {data.status === "running" && onStopTask && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onStopTask();
            }}
            className="inline-flex items-center gap-1 px-2 py-1 text-[12px] text-red-600 bg-red-50 border border-red-200 rounded-md hover:bg-red-100 transition-colors"
          >
            <X size={12} />
            取消任务
          </button>
        )}
      </div>

      {/* Steps */}
      <div className="flex flex-col">
        {data.steps.map((step, index) => {
          // Determine effective step status when timeline is cancelled
          const effectiveStatus = isCancelled && step.status !== "completed"
            ? "cancelled"
            : step.status;

          return (
            <div key={step.number} className="flex gap-3">
              {/* Left column: icons + vertical line */}
              <div className="flex flex-col items-center">
                <div className="w-5 h-5 flex items-center justify-center shrink-0">
                  {effectiveStatus === "completed" && (
                    <div className="w-5 h-5 rounded-full bg-green-500 flex items-center justify-center">
                      <Check size={12} strokeWidth={3} className="text-white" />
                    </div>
                  )}
                  {effectiveStatus === "running" && (
                    <div className="w-5 h-5 rounded-full bg-brand-blue flex items-center justify-center">
                      <Loader2
                        size={12}
                        strokeWidth={2.5}
                        className="text-white animate-spin-slow"
                      />
                    </div>
                  )}
                  {effectiveStatus === "pending" && (
                    <Circle
                      size={20}
                      strokeWidth={1.5}
                      className="text-gray-300"
                    />
                  )}
                  {effectiveStatus === "cancelled" && (
                    <XCircle size={20} strokeWidth={1.5} className="text-amber-400" />
                  )}
                </div>
                {index < data.steps.length - 1 && (
                  <div
                    className={`w-px flex-1 min-h-[20px] ${
                      effectiveStatus === "completed"
                        ? "bg-green-400"
                        : effectiveStatus === "running"
                        ? "bg-brand-blue/30"
                        : effectiveStatus === "cancelled"
                        ? "bg-amber-300"
                        : "bg-gray-200"
                    }`}
                  />
                )}
              </div>

              {/* Right column: content */}
              <div className="flex-1 pb-4">
                <div className="flex items-baseline justify-between">
                  <span
                    className={`text-[14px] ${
                      effectiveStatus === "pending" || effectiveStatus === "cancelled"
                        ? "text-text-tertiary"
                        : "text-text-primary font-medium"
                    }`}
                  >
                    {step.name}
                  </span>
                  {step.message && effectiveStatus !== "pending" && (
                    <span className={`text-[13px] ml-3 shrink-0 ${
                      effectiveStatus === "cancelled"
                        ? "text-amber-500"
                        : "text-text-secondary"
                    }`}>
                      {step.message}
                    </span>
                  )}
                </div>

                {/* Progress bar for running step */}
                {effectiveStatus === "running" && step.progress !== undefined && (
                  <div className="mt-2">
                    <div className="h-1.5 bg-brand-blue-light rounded-full overflow-hidden">
                      <div
                        className="h-full bg-brand-blue rounded-full transition-all duration-500"
                        style={{ width: `${step.progress}%` }}
                      />
                    </div>
                    {step.eta && (
                      <span className="text-[12px] text-text-tertiary mt-1 inline-block">
                        {step.eta}
                      </span>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
