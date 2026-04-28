// Navigation / Page state
export type PageView = "welcome" | "chat" | "company-profile" | "email-config";

export type NavItem = "new-chat" | "company-profile" | "email-config";

// Chat messages
export type MessageRole = "user" | "assistant";

export interface ConfirmParamsData {
  industry: string;
  country: string;
  keywords: string[];
  num: number;
  reply: string;
}

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  timestamp?: string;
  callout?: CalloutData;
  timeline?: TimelineData;
  confirmParams?: ConfirmParamsData;
}

// Callout result card
export interface CalloutData {
  icon: "search" | "building2" | "pen-line" | "send" | "check-circle" | "settings";
  title: string;
  stats: string[];
  actions: CalloutAction[];
}

export interface CalloutAction {
  label: string;
  variant: "outlined" | "filled";
  type: "view-list" | "download-excel" | "view-profile" | "view-emails" | "go-settings";
}

// Pipeline timeline
export interface TimelineStep {
  number: number;
  name: string;
  status: "completed" | "running" | "pending" | "cancelled";
  message?: string;
  progress?: number;
  eta?: string;
}

export interface TimelineData {
  taskType: string;
  title: string;
  status: "running" | "completed" | "failed" | "cancelled";
  steps: TimelineStep[];
}

// Company profile
export interface CompanyProfile {
  id: number;
  companyName: string;
  industry: string;
  website: string;
  established: string;
  employees: string;
  certifications: string;
  cooperationModels: string;
  products: string[];
  competencies: string[];
  caseStudies: CaseStudy[];
  collectedAt: string;
}

export interface CaseStudy {
  project: string;
  description: string;
}

// Email settings
export interface EmailSettings {
  senderName: string;
  replyToEmail: string;
  fromEmailPrefix: string;
  mailDomain: string;
  configuredAt?: string;
}

// Leads table
export interface Lead {
  id: number;
  companyName: string;
  website: string;
  country: string;
  industry: string;
  companyRole: string;
  contactName: string;
  email: string;
  phone: string;
  matchScore: number;
  emailStatus: "draft" | "pending" | "sent" | "failed";
  aiSummary?: string;
  businessMatch?: string;
  outreachSuggestion?: string;
}

// Chat session
export interface ChatSession {
  id: string;
  title: string;
  messages: ChatMessage[];
}

// Chat history
export interface ChatHistoryItem {
  id: string;
  title: string;
  timestamp: string;
}

// Feature card
export interface FeatureCardData {
  icon: string;
  title: string;
  description: string;
  prompt: string;
}
