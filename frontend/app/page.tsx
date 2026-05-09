"use client";

import React, { useState, useCallback, useEffect, useRef } from "react";
import Sidebar from "@/components/sidebar";
import ChatArea from "@/components/chat-area";
import LeadsTableModal from "@/components/leads-table-modal";
import AuthScreen from "@/components/auth-screen";
import { authClient } from "@/lib/auth-client";
import {
  getSettings,
  updateSettings,
  getProfile,
  exportProfileDocx,
  exportLeadsExcel,
  exportEmailsExcel,
  streamChat,
  startConfirmedPipeline,
  stopTask,
  getConversations,
  getConversationMessages,
} from "@/lib/api";
import type {
  ConversationMessageResponse,
} from "@/lib/api";
import type {
  PageView,
  NavItem,
  ChatMessage,
  ChatSession,
  EmailSettings,
  CalloutData,
  TimelineStep,
  ConfirmParamsData,
} from "@/types";

export default function Home() {
  const {
    data: authSession,
    isPending: isAuthPending,
    refetch: refetchAuthSession,
  } = authClient.useSession();
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [activeNav, setActiveNav] = useState<NavItem>("new-chat");
  const [view, setView] = useState<PageView>("welcome");
  const [companyProfile, setCompanyProfile] = useState<any>(null);
  const [emailSettings, setEmailSettings] = useState<EmailSettings | null>(null);
  const [showLeadsModal, setShowLeadsModal] = useState(false);
  const [leadsModalTaskId, setLeadsModalTaskId] = useState<number | null>(null);
  const [leadsModalMode, setLeadsModalMode] = useState<"leads" | "emails">("leads");
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

  const getActiveSession = useCallback((): ChatSession | undefined => {
    if (!activeSessionId) return undefined;
    return sessions.find((s) => s.id === activeSessionId);
  }, [activeSessionId, sessions]);

  const getInputPlaceholder = useCallback(() => {
    const mode = getActiveSession()?.mode;
    if (mode === "company-profile") {
      return "请输入公司官网、主营产品、优势、案例，或上传产品册/公司介绍...";
    }
    if (mode === "customer-acquisition") {
      return "告诉我你想找什么样的客户...";
    }
    if (mode === "email-craft") {
      return "告诉我你想写什么样的开发信，或上传客户资料...";
    }
    return "告诉我你想完成什么外贸任务...";
  }, [getActiveSession]);

  const chatHistory = sessions.map((s) => {
    // Use last message timestamp for display
    const lastMsg = s.messages[s.messages.length - 1];
    return {
      id: s.id,
      title: s.title,
      timestamp: lastMsg?.timestamp || "刚刚",
    };
  });

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

  const updateSessionDbId = useCallback(
    (sessionId: string, dbId: number) => {
      setSessions((prev) =>
        prev.map((s) =>
          s.id === sessionId && !s.dbId ? { ...s, dbId } : s
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
    if (!authSession) {
      setIsLoading(false);
      return;
    }

    async function loadInitialData() {
      setIsLoading(true);
      // Load each data source independently so one failure doesn't block others
      try { const s = await getSettings(); setEmailSettings(s); } catch (e) { console.warn("Failed to load settings:", e); }
      try { const p = await getProfile(); setCompanyProfile(p); } catch (e) { console.warn("Failed to load profile:", e); }
      try {
        const conversations = await getConversations();
        const loaded: ChatSession[] = conversations.map((c) => ({
          id: String(c.id),
          title: c.title,
          mode: c.mode as ChatSession["mode"],
          messages: [],
          dbId: c.id,
        }));
        setSessions(loaded);
      } catch (e) {
        console.warn("Failed to load conversations:", e);
      }
      setIsLoading(false);
    }
    loadInitialData();
  }, [authSession?.user?.id]);

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
        case "customer-list":
          setView("customer-list");
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
      const isProfile = title === "公司画像" || Boolean(title?.includes("画像"));
      const isSupplement = title === "补充资料";
      const isCustomerSearch = title === "客户搜索" || Boolean(title?.includes("客户"));
      const isEmailCraft = title === "开发信撰写" || Boolean(title?.includes("开发信"));
      let initialMessages: ChatMessage[] = [];
      if (isProfile) {
        initialMessages = [
          {
            id: `profile-guide-${Date.now()}`,
            role: "assistant",
            content:
              "我来帮您建立公司画像。请先提供这些信息中的任意几项：\n\n1. 公司全称或品牌名\n2. 官网 URL\n3. 主营产品/服务\n4. 核心优势、资质认证、合作模式\n5. 典型案例、产品册、公司介绍文件\n\n您可以直接粘贴官网，也可以点击输入框左侧的附件按钮上传资料。",
            timestamp: "刚刚",
          },
        ];
      } else if (isSupplement) {
        initialMessages = [
          {
            id: `supplement-guide-${Date.now()}`,
            role: "assistant",
            content:
              "好的，您想对公司画像进行补充或修改。请告诉我您想补充的内容，例如：\n\n1. 补充新的产品或服务线\n2. 更新核心优势或资质认证\n3. 添加更多成功案例\n4. 修正已有信息中的错误\n5. 补充目标客户类型或合作模式\n\n您可以直接输入文字描述，也可以上传相关文件。",
            timestamp: "刚刚",
          },
        ];
      } else if (isEmailCraft) {
        initialMessages = [
          {
            id: `emailcraft-guide-${Date.now()}`,
            role: "assistant",
            content:
              "我来帮您撰写开发信。系统将根据您的公司画像和客户线索，为每位客户生成个性化的开发信。\n\n您可以直接说\"帮我写开发信\"，也可以上传客户资料（Excel/CSV）来补充线索。",
            timestamp: "刚刚",
          },
        ];
      }
      const newSession: ChatSession = {
        id,
        title: title ?? "新聊天",
        mode: isProfile || isSupplement ? "company-profile" : isEmailCraft ? "email-craft" : isCustomerSearch ? "customer-acquisition" : "general",
        messages: initialMessages,
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
      // Load messages from DB if not yet loaded
      if (session?.dbId && session.messages.length === 0) {
        getConversationMessages(session.dbId).then((msgs) => {
          const chatMessages: ChatMessage[] = msgs.map((m: ConversationMessageResponse) => {
            const msg: ChatMessage = {
              id: `db-${m.id}`,
              role: m.role as "user" | "assistant",
              content: m.content,
              timestamp: new Date(m.createdAt).toLocaleString("zh-CN"),
            };
            if (m.extraData) {
              if (m.messageType === "callout") {
                msg.callout = m.extraData as unknown as CalloutData;
              } else if (m.messageType === "timeline") {
                msg.timeline = m.extraData as any;
              } else if (m.messageType === "confirm_params") {
                msg.confirmParams = m.extraData as unknown as ConfirmParamsData;
              } else if (m.messageType === "confirm_email_craft") {
                msg.confirmParams = m.extraData as unknown as ConfirmParamsData;
              }
            }
            return msg;
          });
          setSessions((prev) =>
            prev.map((s) =>
              s.id === sessionId ? { ...s, messages: chatMessages } : s
            )
          );
        }).catch(() => undefined);
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

  const completeTimeline = useCallback(
    (sessionId: string, timelineMsgId: string) => {
      updateSessionMessages(sessionId, (prev) =>
        prev.map((m) => {
          if (m.id !== timelineMsgId || !m.timeline) return m;
          return {
            ...m,
            timeline: {
              ...m.timeline,
              status: "completed",
              steps: m.timeline.steps.map((step) =>
                step.status === "running"
                  ? { ...step, status: "completed", progress: 100 }
                  : step
              ),
            },
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
      const existingDbId = sessions.find((s) => s.id === sessionId)?.dbId;

      await startConfirmedPipeline(
        { ...params, conversationId: existingDbId },
        {
          ...pipelineHandlers,
          onResult: (data) => {
            if (data.callout) {
              calloutDataRef.current = data.callout;
            }
          },
          onDone: (doneData) => {
            const tlId = timelineMsgIdRef.current;
            if (tlId) {
              completeTimeline(sessionId, tlId);
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
            if (doneData.conversationId) {
              updateSessionDbId(sessionId, doneData.conversationId);
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
    [updateMessage, getPipelineHandlers, completeTimeline, sessions]
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
    async (message: string, files?: File[], _skipGuard?: boolean) => {
      if (isStreamingRef.current) return;
      if (
        !_skipGuard &&
        view === "company-profile" &&
        (!files || files.length === 0) &&
        (message.includes("公司画像") || message.includes("敾鍍"))
      ) {
        handleCreateSession("公司画像");
        return;
      }
      const attachments = (files || []).map((file) => ({
        name: file.name,
        size: file.size,
        type: file.type,
      }));

      // Read image files as base64 for the backend to process with vision model
      // Resize to max 1200px on longest side to reduce upload size
      let imageBase64List: string[] = [];
      let backendFiles: { filename: string; data: string }[] | undefined;
      let backendMessage = message;
      if (files && files.length > 0) {
        const imageFiles = files.filter((f) => f.type.startsWith("image/"));
        const nonImageFiles = files.filter((f) => !f.type.startsWith("image/"));
        if (imageFiles.length > 0) {
          imageBase64List = await Promise.all(
            imageFiles.map(
              (file) =>
                new Promise<string>((resolve) => {
                  const img = new Image();
                  img.onload = () => {
                    const MAX_DIM = 1200;
                    let w = img.width;
                    let h = img.height;
                    if (w > MAX_DIM || h > MAX_DIM) {
                      const scale = MAX_DIM / Math.max(w, h);
                      w = Math.round(w * scale);
                      h = Math.round(h * scale);
                    }
                    const canvas = document.createElement("canvas");
                    canvas.width = w;
                    canvas.height = h;
                    const ctx = canvas.getContext("2d");
                    ctx?.drawImage(img, 0, 0, w, h);
                    const dataUrl = canvas.toDataURL("image/jpeg", 0.8);
                    resolve(dataUrl.split(",")[1] || "");
                  };
                  img.src = URL.createObjectURL(file);
                })
            )
          );
        }
        if (nonImageFiles.length > 0) {
          // Read non-image files as base64 for the backend
          backendFiles = await Promise.all(
            nonImageFiles.map(
              (file) =>
                new Promise<{ filename: string; data: string }>((resolve) => {
                  const reader = new FileReader();
                  reader.onload = () => {
                    const base64 = (reader.result as string).split(",")[1] || "";
                    resolve({ filename: file.name, data: base64 });
                  };
                  reader.readAsDataURL(file);
                })
            )
          );
          backendMessage = message || "帮我写开发信";
        } else {
          backendMessage = message;
        }
      } else {
        backendMessage = message;
      }

      // Ensure we have an active session
      let sid = activeSessionId;
      if (!sid) {
        // Auto-create session
        const id = `session-${Date.now()}`;
        const newSession: ChatSession = {
          id,
          title: "新聊天",
          mode: "general",
          messages: [],
        };
        setSessions((prev) => [newSession, ...prev]);
        setActiveSessionId(id);
        sid = id;
      }

      const sessionId = sid; // capture for closures

      // Get existing DB conversation ID for this session
      const existingDbId = sessions.find((s) => s.id === sid)?.dbId;

      // Add user message
      const userMsg: ChatMessage = {
        id: `user-${Date.now()}`,
        role: "user",
        content: message,
        attachments,
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
      let pipelineType: string | null = null;

      await streamChat(
        backendMessage,
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
            pipelineType = data.type;
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

          onDone: (doneData) => {
            if (timelineMsgId) {
              completeTimeline(sessionId, timelineMsgId);
            }

            if (pipelineType === "company-profile") {
              getProfile().then(setCompanyProfile).catch(() => undefined);
              getSettings().then(setEmailSettings).catch(() => undefined);
            }

            // Save conversation DB id when received
            if (doneData.conversationId) {
              updateSessionDbId(sessionId, doneData.conversationId);
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
        controller.signal,
        imageBase64List.length > 0 ? imageBase64List : undefined,
        backendFiles,
        existingDbId
      );
    },
    [activeSessionId, handleCreateSession, updateMessage, updateTimelineStep, updateSessionMessages, completeTimeline, view]
  );

  // ─── Other handlers ──────────────────────────────────────────────
  const handleViewList = useCallback((taskId?: number) => {
    setLeadsModalTaskId(taskId ?? null);
    setLeadsModalMode("leads");
    setShowLeadsModal(true);
  }, []);

  const handleDownloadExcel = useCallback(async (taskId?: number) => {
    try {
      await exportLeadsExcel({ taskId });
    } catch {
      alert("Excel 导出失败，请重试");
    }
  }, []);

  const handleDownloadEmails = useCallback(async (taskId?: number) => {
    try {
      await exportEmailsExcel(taskId);
    } catch {
      alert("邮件 Excel 导出失败，请重试");
    }
  }, []);

  const handleViewProfile = useCallback(async () => {
    const profile = await getProfile();
    setCompanyProfile(profile);
    setView("company-profile");
    setActiveNav("company-profile");
  }, []);

  const handleViewEmails = useCallback((taskId?: number) => {
    setLeadsModalTaskId(taskId ?? null);
    setLeadsModalMode("emails");
    setShowLeadsModal(true);
  }, []);

  const handleStartCollect = useCallback(() => {
    handleCreateSession("公司画像");
  }, [handleCreateSession]);

  const handleSupplement = useCallback(() => {
    handleCreateSession("补充资料");
  }, [handleCreateSession]);

  const handleRecollect = useCallback(() => {
    const website = companyProfile?.website || companyProfile?.profileData?.website;
    if (website) {
      handleSendMessage(`请基于官网 ${website} 重新采集并覆盖公司画像`, undefined, true);
      return;
    }
    handleCreateSession("重新采集公司画像");
  }, [companyProfile, handleCreateSession, handleSendMessage]);

  const handleExportProfile = useCallback(async () => {
    try {
      await exportProfileDocx();
    } catch {
      alert("画像导出失败，请确认已经生成公司画像后重试");
    }
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
    (params: { industry: string; country: string; keywords: string[]; num: number; confirmType?: string; leadCount?: number; language?: string }) => {
      const pending = pendingConfirmRef.current;
      if (!pending) return;

      // Dispatch by confirm type
      if (params.confirmType === "email_craft") {
        pendingConfirmRef.current = null;
        handleConfirmEmailCraft(pending.confirmMsgId, pending.sessionId, params);
        return;
      }

      pendingConfirmRef.current = null;
      handleConfirmParams(pending.confirmMsgId, pending.sessionId, params);
    },
    [handleConfirmParams]
  );

  // ─── Email-craft confirm handler ──────────────────────────────────
  const handleConfirmEmailCraft = useCallback(
    async (
      confirmMsgId: string,
      sessionId: string,
      params: { leadCount?: number; language?: string },
      files?: { filename: string; data: string }[]
    ) => {
      updateMessage(sessionId, confirmMsgId, {
        content: "正在启动开发信生成...",
        confirmParams: undefined,
      });

      isStreamingRef.current = true;
      streamingSessionRef.current = sessionId;

      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      const timelineMsgIdRef = { current: null as string | null };
      const pipelineHandlers = getPipelineHandlers(sessionId, timelineMsgIdRef);
      const existingDbId = sessions.find((s) => s.id === sessionId)?.dbId;

      await startConfirmedPipeline(
        {
          confirmType: "email_craft",
          language: params.language || "en",
          num: params.leadCount || 0,
          files,
          conversationId: existingDbId,
        },
        {
          ...pipelineHandlers,
          onResult: (data) => {
            if (data.callout) {
              calloutDataRef.current = data.callout;
            }
          },
          onDone: (doneData) => {
            const tlId = timelineMsgIdRef.current;
            if (tlId) {
              completeTimeline(sessionId, tlId);
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
            if (doneData.conversationId) {
              updateSessionDbId(sessionId, doneData.conversationId);
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
    [updateMessage, getPipelineHandlers, completeTimeline, sessions]
  );

  // ─── Email-craft confirm from card (with optional uploaded files) ──
  const onConfirmEmailCraftProp = useCallback(
    (files?: { filename: string; data: string }[]) => {
      const pending = pendingConfirmRef.current;
      if (!pending) return;
      // Get the confirm data from the message
      const session = sessions.find((s) => s.id === pending.sessionId);
      const msg = session?.messages.find((m) => m.id === pending.confirmMsgId);
      const confirmData = msg?.confirmParams as any;
      pendingConfirmRef.current = null;
      handleConfirmEmailCraft(
        pending.confirmMsgId,
        pending.sessionId,
        {
          leadCount: confirmData?.leadCount || confirmData?.num || 0,
          language: confirmData?.language || "en",
        },
        files
      );
    },
    [sessions, handleConfirmEmailCraft]
  );

  const onCancelConfirmProp = useCallback(() => {
    const pending = pendingConfirmRef.current;
    if (!pending) return;
    pendingConfirmRef.current = null;
    handleCancelConfirm(pending.confirmMsgId, pending.sessionId);
  }, [handleCancelConfirm]);

  // ─── Generate emails from customer list ───────────────────────────
  const handleGenerateEmailsFromList = useCallback(
    async (leadIds: number[], language: string = "en") => {
      if (leadIds.length === 0 || isStreamingRef.current) return;

      const sessionId = `session-${Date.now()}`;
      const newSession: ChatSession = {
        id: sessionId,
        title: `开发信撰写 - ${leadIds.length} 个客户`,
        mode: "email-craft",
        messages: [
          {
            id: `guide-${Date.now()}`,
            role: "assistant",
            content: `正在为选中的 ${leadIds.length} 个客户生成开发信...`,
            timestamp: "刚刚",
          },
        ],
      };
      setSessions((prev) => [newSession, ...prev]);
      setActiveSessionId(sessionId);
      setView("chat");
      setActiveNav("new-chat");

      isStreamingRef.current = true;
      streamingSessionRef.current = sessionId;
      calloutDataRef.current = null;
      currentTaskIdRef.current = null;

      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      const timelineMsgIdRef = { current: null as string | null };
      const pipelineHandlers = getPipelineHandlers(sessionId, timelineMsgIdRef);

      await startConfirmedPipeline(
        {
          confirmType: "email_craft",
          leadIds,
          num: leadIds.length,
          language,
        },
        {
          ...pipelineHandlers,
          onResult: (data) => {
            if (data.callout) {
              calloutDataRef.current = data.callout;
            }
          },
          onDone: (doneData) => {
            const tlId = timelineMsgIdRef.current;
            if (tlId) {
              completeTimeline(sessionId, tlId);
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
            if (doneData.conversationId) {
              updateSessionDbId(sessionId, doneData.conversationId);
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
    [getPipelineHandlers, updateSessionMessages, completeTimeline]
  );

  const handleSendEmailsFromList = useCallback(
    async (
      leadIds: number[],
      settings: {
        delayMin: number;
        delayMax: number;
        dailyLimit: number;
        dryRun: boolean;
        sendMode: "immediate" | "auto";
      }
    ) => {
      if (leadIds.length === 0 || isStreamingRef.current) return;

      const sessionId = `session-${Date.now()}`;
      const newSession: ChatSession = {
        id: sessionId,
        title: `批量发送 - ${leadIds.length} 个客户`,
        mode: "email-craft",
        messages: [
          {
            id: `guide-${Date.now()}`,
            role: "assistant",
            content: `正在为选中的 ${leadIds.length} 个客户发送开发信...`,
            timestamp: "刚刚",
          },
        ],
      };
      setSessions((prev) => [newSession, ...prev]);
      setActiveSessionId(sessionId);
      setView("chat");
      setActiveNav("new-chat");

      isStreamingRef.current = true;
      streamingSessionRef.current = sessionId;
      calloutDataRef.current = null;
      currentTaskIdRef.current = null;

      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      const timelineMsgIdRef = { current: null as string | null };
      const pipelineHandlers = getPipelineHandlers(sessionId, timelineMsgIdRef);

      await startConfirmedPipeline(
        {
          confirmType: "email_blast",
          leadIds,
          num: leadIds.length,
          delayMin: settings.delayMin,
          delayMax: settings.delayMax,
          dailyLimit: settings.dailyLimit,
          dryRun: false,
          sendMode: settings.sendMode,
        },
        {
          ...pipelineHandlers,
          onResult: (data) => {
            if (data.callout) {
              calloutDataRef.current = data.callout;
            }
          },
          onDone: (doneData) => {
            const tlId = timelineMsgIdRef.current;
            if (tlId) {
              completeTimeline(sessionId, tlId);
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
            if (doneData.conversationId) {
              updateSessionDbId(sessionId, doneData.conversationId);
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
    [getPipelineHandlers, updateSessionMessages, completeTimeline]
  );

  const handleSignOut = useCallback(async () => {
    abortRef.current?.abort();
    abortRef.current = null;
    streamingSessionRef.current = null;
    isStreamingRef.current = false;
    currentTaskIdRef.current = null;
    pendingConfirmRef.current = null;
    calloutDataRef.current = null;

    await authClient.signOut();
    setSessions([]);
    setActiveSessionId(null);
    setActiveNav("new-chat");
    setView("welcome");
    setCompanyProfile(null);
    setEmailSettings(null);
    setShowLeadsModal(false);
    setLeadsModalTaskId(null);
    setIsLoading(false);
    await refetchAuthSession();
  }, [refetchAuthSession]);

  if (isAuthPending) {
    return (
      <main className="flex h-screen w-screen items-center justify-center bg-[#f4f5f2] text-[14px] text-text-secondary">
        正在加载...
      </main>
    );
  }

  if (!authSession) {
    return <AuthScreen onAuthenticated={refetchAuthSession} />;
  }

  return (
    <main className="flex h-screen w-screen overflow-hidden bg-surface-white">
      <Sidebar
        activeNav={activeNav}
        onNavChange={handleNavChange}
        chatHistory={chatHistory}
        activeSessionId={activeSessionId}
        onSelectChat={handleSelectSession}
        userEmail={authSession.user.email}
        onSignOut={handleSignOut}
      />
      <div className="flex-1 min-w-0 h-full">
        <ChatArea
          view={view}
          messages={messages}
          onSendMessage={handleSendMessage}
          onCreateChat={handleCreateSession}
          onViewList={handleViewList}
          onDownloadExcel={handleDownloadExcel}
          onDownloadEmails={handleDownloadEmails}
          onViewProfile={handleViewProfile}
          onViewEmails={handleViewEmails}
          onStopTask={handleStopTask}
          onConfirmParams={onConfirmParamsProp}
          onConfirmEmailCraft={onConfirmEmailCraftProp}
          onCancelConfirm={onCancelConfirmProp}
          onGoToCustomerList={() => handleNavChange("customer-list")}
          companyProfile={companyProfile}
          emailSettings={emailSettings}
          onBackToChat={handleBackToChat}
          onStartCollect={handleStartCollect}
          onSupplement={handleSupplement}
          onRecollect={handleRecollect}
          onExportProfile={handleExportProfile}
          onSaveEmailSettings={handleSaveEmailSettings}
          onGenerateEmails={handleGenerateEmailsFromList}
          onGoToEmailConfig={() => handleNavChange("email-config")}
          onSendEmails={handleSendEmailsFromList}
          isStreaming={isStreaming}
          isLoading={isLoading}
          inputPlaceholder={getInputPlaceholder()}
          allowFileUpload={getActiveSession()?.mode === "company-profile" || getActiveSession()?.mode === "email-craft"}
        />
      </div>

      <LeadsTableModal
        isOpen={showLeadsModal}
        onClose={() => setShowLeadsModal(false)}
        taskId={leadsModalTaskId}
        mode={leadsModalMode}
      />
    </main>
  );
}
