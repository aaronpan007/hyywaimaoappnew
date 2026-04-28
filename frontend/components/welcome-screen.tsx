"use client";

import React from "react";
import FeatureCard from "./feature-card";
import ChatInput from "./chat-input";
import { featureCards } from "@/lib/mock-data";

interface WelcomeScreenProps {
  onSend: (message: string) => void;
  onCreateChat: (title?: string) => void;
  isLoading?: boolean;
  disabled?: boolean;
}

export default function WelcomeScreen({ onSend, onCreateChat, isLoading = false, disabled = false }: WelcomeScreenProps) {
  return (
    <div className="flex flex-col h-full">
      {isLoading && (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-text-tertiary text-[14px] animate-pulse">加载中...</div>
        </div>
      )}
      {!isLoading && <>
      {/* Content */}
      <div className="flex-1 flex items-center justify-center px-4">
        <div className="w-full max-w-[600px]">
          {/* Greeting */}
          <div className="text-center mb-8 animate-fade-in-up opacity-0">
            <h1 className="text-[20px] font-semibold text-text-primary mb-2">
              你好，我是你的外贸获客助手。
            </h1>
            <p className="text-[14px] text-text-secondary">
              告诉我你想找什么样的客户，我来帮你搞定。
            </p>
          </div>

          {/* Feature Cards Grid */}
          <div className="grid grid-cols-2 gap-3 mb-6">
            {featureCards.map((card, i) => (
              <FeatureCard
                key={card.title}
                data={card}
                index={i}
                onClick={() => onCreateChat(card.title)}
              />
            ))}
          </div>

          {/* Hint */}
          <div className="text-center animate-fade-in-up opacity-0" style={{ animationDelay: "500ms" }}>
            <p className="text-[13px] text-text-tertiary">
              试试直接输入：&ldquo;帮我找30个美国的LED分销商&rdquo;
            </p>
          </div>
        </div>
      </div>

      {/* Input */}
      <ChatInput onSend={onSend} disabled={disabled} />
      </>}
    </div>
  );
}
