"use client";

import React, { useState, useCallback, useEffect, useRef } from "react";
import Sidebar from "@/components/sidebar";
import ChatArea from "@/components/chat-area";
import LeadsTableModal from "@/components/leads-table-modal";
import {
  getSettings,
  updateSettings,
  getProfile,
  exportLeadsExcel,
  streamChat,
  startConfirmedPipeline,
  stopTask,
} from "@/lib/api";
import type {
  PageView,
  NavItem,
  ChatMessage,
  ChatSession,
  EmailSettings,
  CalloutData,
  TimelineStep,
} from "@/types";

export default function Home() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [activeNav, setActiveNav] = useState<NavItem>("new-chat");
  const [view, setView] = useState<PageView>("welcome");
  const [companyProfile, setCompanyProfile] = useState<any>(null);
  const [emailSettings, setEmailSettings] = useState<EmailSettings | null>(null);
  const [showLeadsModal, setShowLeadsModal] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  const streamingSessionRef = useRef<string | null>(null);
  const isStreamingRef = useRef(false);
  const calloutDataRef = useRef<CalloutData | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const currentTaskIdRef = useRef<number | null>(null);
  const pendingConfirmRef = useRef<{ confirmMsgId: string; sessionId: string } | null>(null);

  // ─── Derived state ───────────────────────────────────────────────
  const isStreaming = streamingSessionRef.current === activeSessionId;

  const getActiveMessages = useCallback((): ChatMessage[] => {
    if (!activeSessionId) return [];
    const session = sessions.find((s) => s.id === activeSessionId);
    return session?.messages ?? [];
  }, [activeSessionId, sessions]);

  const chatHistory = sessions.map((s) => ({
    id: s.id,
    title: s.title,
    timestamp: "刚刚",
  }));

  // ─── Session helpers (using functional setState to avoid stale closures) ──
  const updateSessionMessages = useCallback(
    (sessionId: string, updater: (msgs: ChatMessage[]) => ChatMessage[]) => {
      setSessions((prev) =>
        prev.map((s) =>
          s.id === sessionId ? { ...s, messages: updater(s.messages) } : s
        )
      );
    },
    []
  );

  const updateSessionTitle = useCallback(
    (sessionId: string, title: string) => {
      setSessions((prev) =>
        prev.map((s) => (s.id === sessionId ? { ...s, title } : s))
      );
    },
    []
  );

  // ─── Initial data loading ────────────────────────────────────────
  useEffect(() => {
    async function loadInitialData() {
      try {
        const [settings, profile] = await Promise.all([
          getSettings(),
          getProfile(),
        ]);
        setEmailSettings(settings);
        setCompanyProfile(profile);
      } catch (err) {
        console.error("Failed to load initial data:", err);
      } finally {
        setIsLoading(false);
      }
    }
    loadInitialData();
  }, []);

  // ─── Navigation handler ──────────────────────────────────────────
  const handleNavChange = useCallback(
    (nav: NavItem) => {
      setActiveNav(nav);
      switch (nav) {
        case "new-chat":
          setView("welcome");
          setActiveSessionId(null);
          abortRef.current?.abort();
          abortRef.current = null;
          // Don't reset streaming state — let the streaming session continue in background
          currentTaskIdRef.current = null;
          break;
        case "company-profile":
          setView("company-profile");
          break;
        case "email-config":
          setView("email-config");
          break;
      }
    },
    []
  );

  const handleBackToChat = useCallback(() => {
    setActiveNav("new-chat");
    const hasMessages = sessions.find((s) => s.id === activeSessionId)?.messages.length ?? 0 > 0;
    setView(hasMessages ? "chat" : "welcome");
  }, [activeSessionId, sessions]);

  // ─── Create session ──────────────────────────────────────────────
  const handleCreateSession = useCallback(
    (title?: string) => {
      const id = `session-${Date.now()}`;
      const newSession: ChatSession = {
        id,
        title: title ?? "新聊天",
        messages: [],
      };
      setSessions((prev) => [newSession, ...prev]);
      setActiveSessionId(id);
      setView("chat");
      setActiveNav("new-chat");
      streamingSessionRef.current = null;
      isStreamingRef.current = false;
      abortRef.current?.abort();
      abortRef.current = null;
      currentTaskIdRef.current = null;
    },
    []
  );

  // ─── Select session ──────────────────────────────────────────────
  const handleSelectSession = useCallback(
    (sessionId: string) => {
      setActiveSessionId(sessionId);
      setView("chat");
      setActiveNav("new-chat");
      // Restore streaming state for the selected session
      const session = sessions.find((s) => s.id === sessionId);
      const hasRunningTimeline = session?.messages.some(
        (m) => m.timeline?.status === "running"
      );
      if (hasRunningTimeline && streamingSessionRef.current === sessionId) {
        isStreamingRef.current = true;
      } else {
        isStreamingRef.current = false;
      }
      // Abort previous stream if switching away from a streaming session
      if (streamingSessionRef.current && streamingSessionRef.current !== sessionId) {
        abortRef.current?.abort();
        abortRef.current = null;
        currentTaskIdRef.current = null;
      }
    },
    [sessions]
  );

  // ─── Helper: update a message by id in the active session ────────
  const updateMessage = useCallback(
    (sessionId: string, id: string, updates: Partial<ChatMessage>) => {
      updateSessionMessages(sessionId, (prev) =>
        prev.map((m) => (m.id === id ? { ...m, ...updates } : m))
      );
    },
    [updateSessionMessages]
  );

  // ─── Helper: update a timeline step in the active session ────────
  const updateTimelineStep = useCallback(
    (sessionId: string, timelineMsgId: string, stepData: Omit<TimelineStep, "number"> & { step: number }) => {
      updateSessionMessages(sessionId, (prev) =>
        prev.map((m) => {
          if (m.id !== timelineMsgId || !m.timeline) return m;
          const existing = m.timeline!.steps.find(
            (s) => s.number === stepData.step
          );
          let newSteps: TimelineStep[];
          if (existing) {
            newSteps = m.timeline!.steps.map((s) =>
              s.number === stepData.step
                ? {
                    ...s,
                    status: stepData.status,
                    message: stepData.message ?? s.message,
                    progress: stepData.progress ?? s.progress,
                    eta: stepData.eta ?? s.eta,
                  }
                : s
            );
          } else {
            const newStep: TimelineStep = {
              number: stepData.step,
              name: stepData.name,
              status: stepData.status,
              message: stepData.message,
              progress: stepData.progress,
              eta: stepData.eta,
            };
            newSteps = [...m.timeline!.steps, newStep];
          }
          return {
            ...m,
            timeline: { ...m.timeline!, steps: newSteps },
          };
        })
      );
    },
    [updateSessionMessages]
  );

  // ─── Stop task handler ────────────────────────────────────────────
  const handleStopTask = useCallback(async () => {
    const taskId = currentTaskIdRef.current;
    if (taskId) {
      try {
        await stopTask(taskId);
      } catch {
        // Ignore — best-effort stop
      }
    }

    // Abort SSE connection
    abortRef.current?.abort();
    abortRef.current = null;

    // Update timeline status to cancelled in the streaming session
    const sid = streamingSessionRef.current;
    if (sid) {
      updateSessionMessages(sid, (prev) =>
        prev.map((m) => {
          if (!m.timeline || m.timeline.status !== "running") return m;
          return {
            ...m,
            timeline: { ...m.timeline, status: "cancelled" },
          };
        })
      );
    }

    isStreamingRef.current = false;
    streamingSessionRef.current = null;
    currentTaskIdRef.current = null;
    // Force re-render
    setSessions((prev) => [...prev]);
  }, [updateSessionMessages]);

  // ─── Helper: pipeline SSE handlers (shared by handleSendMessage and handleConfirmParams) ──
  const getPipelineHandlers = useCallback(
    (sessionId: string, timelineMsgIdRef: React.MutableRefObject<string | null>) => ({
      onPipelineStarted: (data: { taskId: number; type: string; title?: string }) => {
        const tlId = `timeline-${Date.now()}`;
        timelineMsgIdRef.current = tlId;
        currentTaskIdRef.current = data.taskId;
        updateSessionMessages(sessionId, (prev) => [
          ...prev,
          {
            id: tlId,
            role: "assistant",
            content: "",
            timestamp: "刚刚",
            timeline: {
              taskType: data.type,
              title:
                data.type === "customer-acquisition"
                  ? "客户搜索"
                  : data.type === "company-profile"
                    ? "公司画像"
                    : data.type === "email-craft"
                      ? "开发信撰写"
                      : data.type === "email-blast"
                        ? "邮件发送"
                        : data.type,
              status: "running",
              steps: [],
            },
          },
        ]);
      },

      onStepUpdate: (data: any) => {
        if (timelineMsgIdRef.current) {
          updateTimelineStep(sessionId, timelineMsgIdRef.current, data);
        }
      },

      onTaskCancelled: () => {
        const tlId = timelineMsgIdRef.current;
        if (tlId) {
          updateSessionMessages(sessionId, (prev) =>
            prev.map((m) => {
              if (m.id !== tlId || !m.timeline) return m;
              return { ...m, timeline: { ...m.timeline, status: "cancelled" } };
            })
          );
        }
        isStreamingRef.current = false;
        streamingSessionRef.current = null;
        currentTaskIdRef.current = null;
        setSessions((prev) => [...prev]);
      },

      onTaskStale: () => {
        const tlId = timelineMsgIdRef.current;
        if (tlId) {
          updateSessionMessages(sessionId, (prev) =>
            prev.map((m) => {
              if (m.id !== tlId || !m.timeline) return m;
              return { ...m, timeline: { ...m.timeline, status: "failed" } };
            })
          );
        }
        isStreamingRef.current = false;
        streamingSessionRef.current = null;
        currentTaskIdRef.current = null;
        setSessions((prev) => [...prev]);
      },

      onError: (err: Error) => {
        updateSessionMessages(sessionId, (prev) => [
          ...prev,
          {
            id: `error-${Date.now()}`,
            role: "assistant",
            content: `出错了：${err.message}`,
            timestamp: "刚刚",
          },
        ]);
        isStreamingRef.current = false;
        streamingSessionRef.current = null;
        currentTaskIdRef.current = null;
        setSessions((prev) => [...prev]);
      },
    }),
    [updateSessionMessages, updateTimelineStep]
  );

  // ─── Confirm params handler ──────────────────────────────────────
  const handleConfirmParams = useCallback(
    async (confirmMsgId: string, sessionId: string, params: {
      industry: string;
      country: string;
      keywords: string[];
      num: number;
    }) => {
      // Update confirm card message to "starting..."
      updateMessage(sessionId, confirmMsgId, {
        content: "正在启动搜索...",
        confirmParams: undefined,
      });

      isStreamingRef.current = true;
      streamingSessionRef.current = sessionId;

      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      const timelineMsgIdRef = { current: null as string | null };
      const pipelineHandlers = getPipelineHandlers(sessionId, timelineMsgIdRef);

      await startConfirmedPipeline(
        params,
        {
          ...pipelineHandlers,
          onResult: (data) => {
            if (data.callout) {
              calloutDataRef.current = data.callout;
            }
          },
          onDone: () => {
            const tlId = timelineMsgIdRef.current;
            if (tlId) {
              updateSessionMessages(sessionId, (prev) =>
                prev.map((m) => {
                  if (m.id !== tlId || !m.timeline) return m;
                  return { ...m, timeline: { ...m.timeline, status: "completed" } };
                })
              );
            }
            const callout = calloutDataRef.current;
            if (callout) {
              updateSessionMessages(sessionId, (prev) => [
                ...prev,
                {
                  id: `callout-${Date.now()}`,
                  role: "assistant",
                  content: "",
                  timestamp: "刚刚",
                  callout: callout as CalloutData,
                },
              ]);
            }
            isStreamingRef.current = false;
            streamingSessionRef.current = null;
            currentTaskIdRef.current = null;
            setSessions((prev) => [...prev]);
          },
        },
        controller.signal
      );
    },
    [updateMessage, getPipelineHandlers]
  );

  // ─── Cancel confirm handler ──────────────────────────────────────
  const handleCancelConfirm = useCallback(
    (confirmMsgId: string, sessionId: string) => {
      updateMessage(sessionId, confirmMsgId, {
        content: "已取消搜索",
        confirmParams: undefined,
      });
    },
    [updateMessage]
  );

  // ─── Send message handler (SSE streaming) ────────────────────────
  const handleSendMessage = useCallback(
    async (message: string) => {
      if (isStreamingRef.current) return;

      // Ensure we have an active session
      let sid = activeSessionId;
      if (!sid) {
        // Auto-create session
        const id = `session-${Date.now()}`;
        const newSession: ChatSession = {
          id,
          title: "新聊天",
          messages: [],
        };
        setSessions((prev) => [newSession, ...prev]);
        setActiveSessionId(id);
        sid = id;
      }

      const sessionId = sid; // capture for closures

      // Add user message
      const userMsg: ChatMessage = {
        id: `user-${Date.now()}`,
        role: "user",
        content: message,
      };

      // Add thinking placeholder
      const thinkingId = `thinking-${Date.now()}`;
      const thinkingMsg: ChatMessage = {
        id: thinkingId,
        role: "assistant",
        content: "思考中...",
        timestamp: "刚刚",
      };

      // Update session: add messages + set title if first message
      setSessions((prev) =>
        prev.map((s) => {
          if (s.id !== sessionId) return s;
          const isFirstMessage = s.messages.length === 0;
          return {
            ...s,
            title: isFirstMessage
              ? message.length > 20 ? message.slice(0, 20) + "..." : message
              : s.title,
            messages: [...s.messages, userMsg, thinkingMsg],
          };
        })
      );

      setView("chat");
      setActiveNav("new-chat");
      isStreamingRef.current = true;
      streamingSessionRef.current = sessionId;
      calloutDataRef.current = null;
      currentTaskIdRef.current = null;

      // Abort previous stream if any
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      let timelineMsgId: string | null = null;
      let confirmMsgId: string | null = null;

      await streamChat(
        message,
        {
          onThinking: () => {
            updateMessage(sessionId, thinkingId, { content: "正在分析您的需求..." });
          },

          onConfirmParams: (data) => {
            const cfmId = `confirm-${Date.now()}`;
            confirmMsgId = cfmId;
            pendingConfirmRef.current = { confirmMsgId: cfmId, sessionId };
            // Replace thinking message with confirm params card
            updateSessionMessages(sessionId, (prev) =>
              prev.map((m) =>
                m.id === thinkingId
                  ? {
                      ...m,
                      id: cfmId,
                      content: "",
                      confirmParams: data,
                    }
                  : m
              )
            );
            // Confirm card is shown — allow user interaction
            isStreamingRef.current = false;
            streamingSessionRef.current = null;
            setSessions((prev) => [...prev]); // force re-render
          },

          onResult: (data) => {
            updateSessionMessages(sessionId, (prev) => {
              const withoutThinking = prev.filter((m) => m.id !== thinkingId);
              return [
                ...withoutThinking,
                {
                  id: `result-${Date.now()}`,
                  role: "assistant" as const,
                  content: data.summary || data.callout?.title || "处理中...",
                  timestamp: "刚刚",
                },
              ];
            });
            if (data.callout) {
              calloutDataRef.current = data.callout;
            }
          },

          onPipelineStarted: (data) => {
            const tlId = `timeline-${Date.now()}`;
            timelineMsgId = tlId;
            currentTaskIdRef.current = data.taskId;
            updateSessionMessages(sessionId, (prev) => [
              ...prev,
              {
                id: tlId,
                role: "assistant",
                content: "",
                timestamp: "刚刚",
                timeline: {
                  taskType: data.type,
                  title:
                    data.type === "customer-acquisition"
                      ? "客户搜索"
                      : data.type === "company-profile"
                        ? "公司画像"
                        : data.type === "email-craft"
                          ? "开发信撰写"
                          : data.type === "email-blast"
                            ? "邮件发送"
                            : data.type,
                  status: "running",
                  steps: [],
                },
              },
            ]);
          },

          onStepUpdate: (data) => {
            if (timelineMsgId) {
              updateTimelineStep(sessionId, timelineMsgId, data);
            }
          },

          onConfigRequired: (data) => {
            updateSessionMessages(sessionId, (prev) => {
              const withoutThinking = prev.filter((m) => m.id !== thinkingId);
              return [
                ...withoutThinking,
                {
                  id: `config-${Date.now()}`,
                  role: "assistant",
                  content: `请先在设置页面配置以下 API 密钥：${data.missingFields.join("、")}`,
                  timestamp: "刚刚",
                  callout: {
                    icon: "settings",
                    title: "配置缺失",
                    summary: data.suggestion || "请先配置 API 密钥",
                    stats: data.missingFields,
                    actions: [
                      {
                        label: "前往设置",
                        variant: "filled" as const,
                        type: "go-settings",
                      },
                    ],
                  } as CalloutData,
                },
              ];
            });
          },

          onDone: () => {
            if (timelineMsgId) {
              updateSessionMessages(sessionId, (prev) =>
                prev.map((m) => {
                  if (m.id !== timelineMsgId || !m.timeline) return m;
                  return {
                    ...m,
                    timeline: { ...m.timeline, status: "completed" },
                  };
                })
              );
            }

            const callout = calloutDataRef.current;
            if (callout) {
              updateSessionMessages(sessionId, (prev) => [
                ...prev,
                {
                  id: `callout-${Date.now()}`,
                  role: "assistant",
                  content: "",
                  timestamp: "刚刚",
                  callout: callout as CalloutData,
                },
              ]);
            }

            isStreamingRef.current = false;
            streamingSessionRef.current = null;
            currentTaskIdRef.current = null;
            setSessions((prev) => [...prev]); // force re-render for isStreaming
          },

          onTaskCancelled: () => {
            if (timelineMsgId) {
              updateSessionMessages(sessionId, (prev) =>
                prev.map((m) => {
                  if (m.id !== timelineMsgId || !m.timeline) return m;
                  return {
                    ...m,
                    timeline: { ...m.timeline, status: "cancelled" },
                  };
                })
              );
            }
            isStreamingRef.current = false;
            streamingSessionRef.current = null;
            currentTaskIdRef.current = null;
            setSessions((prev) => [...prev]);
          },

          onTaskStale: () => {
            if (timelineMsgId) {
              updateSessionMessages(sessionId, (prev) =>
                prev.map((m) => {
                  if (m.id !== timelineMsgId || !m.timeline) return m;
                  return {
                    ...m,
                    timeline: { ...m.timeline, status: "failed" },
                  };
                })
              );
            }
            isStreamingRef.current = false;
            streamingSessionRef.current = null;
            currentTaskIdRef.current = null;
            setSessions((prev) => [...prev]);
          },

          onError: (err) => {
            updateSessionMessages(sessionId, (prev) => {
              const withoutThinking = prev.filter((m) => m.id !== thinkingId);
              return [
                ...withoutThinking,
                {
                  id: `error-${Date.now()}`,
                  role: "assistant",
                  content: `出错了：${err.message}`,
                  timestamp: "刚刚",
                },
              ];
            });
            isStreamingRef.current = false;
            streamingSessionRef.current = null;
            currentTaskIdRef.current = null;
            setSessions((prev) => [...prev]);
          },
        },
        controller.signal
      );
    },
    [activeSessionId, updateMessage, updateTimelineStep, updateSessionMessages]
  );

  // ─── Other handlers ──────────────────────────────────────────────
  const handleViewList = useCallback(() => setShowLeadsModal(true), []);

  const handleDownloadExcel = useCallback(async () => {
    try {
      await exportLeadsExcel();
    } catch {
      alert("Excel 导出失败，请重试");
    }
  }, []);

  const handleStartCollect = useCallback(() => {
    handleSendMessage("帮我建立一个公司画像");
  }, [handleSendMessage]);

  const handleRecollect = useCallback(() => {
    handleSendMessage("帮我建立一个公司画像");
  }, [handleSendMessage]);

  const handleExportProfile = useCallback(() => {
    alert("画像导出功能将在后续版本中启用");
  }, []);

  const handleSaveEmailSettings = useCallback(
    async (settings: EmailSettings) => {
      try {
        const updated = await updateSettings(settings);
        setEmailSettings(updated);
        alert("邮箱配置已保存！");
      } catch (err: any) {
        alert(`保存失败：${err.message}`);
      }
    },
    []
  );

  const messages = getActiveMessages();

  // ─── Props for confirm params card (via ChatArea → MessageList → MessageBubble) ──
  const onConfirmParamsProp = useCallback(
    (params: { industry: string; country: string; keywords: string[]; num: number }) => {
      const pending = pendingConfirmRef.current;
      if (!pending) return;
      pendingConfirmRef.current = null;
      handleConfirmParams(pending.confirmMsgId, pending.sessionId, params);
    },
    [handleConfirmParams]
  );

  const onCancelConfirmProp = useCallback(() => {
    const pending = pendingConfirmRef.current;
    if (!pending) return;
    pendingConfirmRef.current = null;
    handleCancelConfirm(pending.confirmMsgId, pending.sessionId);
  }, [handleCancelConfirm]);

  return (
    <main className="flex h-screen w-screen overflow-hidden bg-surface-white">
      <Sidebar
        activeNav={activeNav}
        onNavChange={handleNavChange}
        chatHistory={chatHistory}
        activeSessionId={activeSessionId}
        onSelectChat={handleSelectSession}
      />
      <div className="flex-1 min-w-0 h-full">
        <ChatArea
          view={view}
          messages={messages}
          onSendMessage={handleSendMessage}
          onCreateChat={handleCreateSession}
          onViewList={handleViewList}
          onDownloadExcel={handleDownloadExcel}
          onStopTask={handleStopTask}
          onConfirmParams={onConfirmParamsProp}
          onCancelConfirm={onCancelConfirmProp}
          companyProfile={companyProfile}
          emailSettings={emailSettings}
          onBackToChat={handleBackToChat}
          onStartCollect={handleStartCollect}
          onRecollect={handleRecollect}
          onExportProfile={handleExportProfile}
          onSaveEmailSettings={handleSaveEmailSettings}
          isStreaming={isStreaming}
          isLoading={isLoading}
        />
      </div>

      <LeadsTableModal
        isOpen={showLeadsModal}
        onClose={() => setShowLeadsModal(false)}
      />
    </main>
  );
}
