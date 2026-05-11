// Navigation / Page state
export type PageView = "welcome" | "chat" | "customer-list" | "company-profile" | "email-config";

export type NavItem = "new-chat" | "customer-list" | "company-profile" | "email-config";

// Chat messages
export type MessageRole = "user" | "assistant";

export const CUSTOMER_TYPE_OPTIONS = [
  "manufacturer",
  "supplier",
  "distributor",
  "contractor",
  "installer",
  "brand",
  "competitor",
  "buyer",
] as const;

export type CustomerType = (typeof CUSTOMER_TYPE_OPTIONS)[number];

export interface ConfirmParamsData {
  industry: string;
  country: string;
  keywords: string[];
  num: number;
  reply: string;
  confirmType?: string;
  customerTypes?: CustomerType[];
}

export interface EmailCraftConfirmData {
  confirmType: "email_craft";
  leadCount: number;
  language: string;
  reply: string;
  userRequirements?: string;
}

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  timestamp?: string;
  attachments?: { name: string; size: number; type?: string }[];
  callout?: CalloutData;
  timeline?: TimelineData;
  confirmParams?: ConfirmParamsData;
}

// Callout result card
export interface CalloutData {
  icon: "search" | "building2" | "pen-line" | "send" | "check-circle" | "settings" | "alert-circle" | "message-circle";
  title: string;
  stats: string[];
  actions: CalloutAction[];
  taskId?: number;
  summary?: string;
}

export interface CalloutAction {
  label: string;
  variant: "outlined" | "filled";
  type: "view-list" | "download-excel" | "download-emails" | "view-profile" | "view-emails" | "go-settings" | "go-customer-list";
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
  oneLineIntro?: string;
  fullIntro?: string;
  location?: string;
  industry: string;
  website: string;
  established: string;
  scale?: string;
  employees: string;
  certifications: any[] | string;
  cooperationModels: any[] | string;
  products: any[];
  competencies: any[];
  targetCustomerTypes?: any[];
  caseStudies: any[];
  uniqueSellingPoints?: any[];
  customerMatchingGuide?: any[];
  boundaries?: Record<string, any>;
  metadata?: Record<string, any>;
  profileData?: Record<string, any>;
  profileMarkdown?: string;
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
  configuredAt?: string | null;
}

// Leads table
export interface Lead {
  id: number;
  sourceTaskId?: number | null;
  sourceList?: string;
  userNote?: string;
  companyName: string;
  website: string;
  country: string;
  industry: string;
  companyRole: string;
  contactName: string;
  email: string;
  phone: string;
  matchScore: number | null;
  emailStatus:
    | "unwritten"
    | "draft"
    | "sending"
    | "pending"
    | "sent"
    | "delivered"
    | "failed"
    | "bounced"
    | "complained"
    | string;
  emailSubject?: string;
  emailBody?: string;
  aiSummary?: string;
  businessMatch?: string;
  outreachSuggestion?: string;
}

// Chat session
export interface ChatSession {
  id: string;
  title: string;
  messages: ChatMessage[];
  mode?: "general" | "customer-acquisition" | "company-profile" | "email-craft";
  dbId?: number; // database conversation ID for persistence
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
