import type {
  ChatMessage,
  CalloutData,
  TimelineData,
  CompanyProfile,
  EmailSettings,
  Lead,
  ChatHistoryItem,
  FeatureCardData,
} from "@/types";

export const mockChatHistory: ChatHistoryItem[] = [
  { id: "1", title: "AI能力概览", timestamp: "19分钟前" },
  { id: "2", title: "美国太阳能分销商搜索", timestamp: "2小时前" },
  { id: "3", title: "开发信撰写", timestamp: "昨天" },
  { id: "4", title: "公司信息采集", timestamp: "昨天" },
  { id: "5", title: "欧洲LED客户搜索", timestamp: "3天前" },
];

export const mockMessages: ChatMessage[] = [
  {
    id: "m1",
    role: "assistant",
    content: "好的，我来帮您搜索美国的太阳能板分销商。请稍等，我先搜索相关公司...",
    timestamp: "19分钟前",
  },
  {
    id: "m2",
    role: "user",
    content: "帮我找30个美国的太阳能板分销商",
  },
  {
    id: "m3",
    role: "assistant",
    content:
      "已为您筛选出30个高匹配度的美国太阳能板分销商。您可以查看详细列表，也可以直接下载 Excel 文件。需要我帮您给这些客户写开发信吗？",
    timestamp: "18分钟前",
    callout: {
      icon: "search",
      title: "客户搜索完成",
      stats: [
        "找到 30 个高质量美国太阳能分销商",
        "AI 匹配度 ≥ 80%",
      ],
      actions: [
        { label: "查看详细列表", variant: "outlined", type: "view-list" },
        { label: "下载 Excel", variant: "filled", type: "download-excel" },
      ],
    },
  },
  {
    id: "m4",
    role: "user",
    content: "好的，先写英文开发信",
  },
];

// Search response with timeline (mid-pipeline)
export const mockTimelineMessage: ChatMessage[] = [
  {
    id: "t2",
    role: "assistant",
    content: "好的，我来帮您搜索美国的太阳能板分销商，请稍等...",
    timestamp: "3分钟前",
    timeline: {
      taskType: "customer-acquisition",
      title: "客户搜索",
      status: "running",
      steps: [
        {
          number: 1,
          name: "搜索目标公司",
          status: "completed",
          message: "找到 90 个候选",
          progress: 100,
        },
        {
          number: 2,
          name: "爬取网站内容",
          status: "running",
          message: "正在爬取 (12/90)",
          progress: 13,
          eta: "预计 3 分钟",
        },
        {
          number: 3,
          name: "AI 筛选与排名",
          status: "pending",
        },
        {
          number: 4,
          name: "输出结果",
          status: "pending",
        },
      ],
    },
  },
  {
    id: "t3",
    role: "assistant",
    content:
      "已为您筛选出30个高匹配度的美国太阳能板分销商。您可以查看详细列表，也可以直接下载 Excel 文件。需要我帮您给这些客户写开发信吗？",
    timestamp: "刚刚",
    callout: {
      icon: "search",
      title: "客户搜索完成",
      stats: [
        "找到 30 个高质量美国太阳能分销商",
        "AI 匹配度 ≥ 80%",
      ],
      actions: [
        { label: "查看详细列表", variant: "outlined", type: "view-list" },
        { label: "下载 Excel", variant: "filled", type: "download-excel" },
      ],
    },
  },
];

// Search response with completed callout only (no timeline, for non-search prompts)
export const mockCalloutMessage: ChatMessage[] = [
  {
    id: "c1",
    role: "assistant",
    content: "好的，我来帮您搜索美国的太阳能板分销商。请稍等，我先搜索相关公司...",
    timestamp: "19分钟前",
  },
  {
    id: "c3",
    role: "assistant",
    content:
      "已为您筛选出30个高匹配度的美国太阳能板分销商。您可以查看详细列表，也可以直接下载 Excel 文件。需要我帮您给这些客户写开发信吗？",
    timestamp: "18分钟前",
    callout: {
      icon: "search",
      title: "客户搜索完成",
      stats: [
        "找到 30 个高质量美国太阳能分销商",
        "AI 匹配度 ≥ 80%",
      ],
      actions: [
        { label: "查看详细列表", variant: "outlined", type: "view-list" },
        { label: "下载 Excel", variant: "filled", type: "download-excel" },
      ],
    },
  },
];

export const mockCompanyProfile: CompanyProfile = {
  id: 1,
  companyName: "深圳光明光电科技有限公司",
  industry: "LED 照明 / 半导体照明",
  website: "https://www.gm-light.com",
  established: "2009年",
  employees: "200-500人",
  certifications: "ISO 9001, CE, RoHS",
  cooperationModels: "OEM / ODM",
  products: [
    "LED工矿灯",
    "LED太阳能路灯",
    "LED面板灯",
    "LED防爆灯",
    "LED高杆灯",
    "LED隧道灯",
  ],
  competencies: [
    "15年LED制造经验，产品远销80+国家",
    "自有模具车间，支持OEM/ODM定制",
    "通过ISO 9001认证，3年质保",
    "月产能超过50,000套，交期稳定",
  ],
  caseStudies: [
    {
      project: "尼日利亚太阳能路灯项目",
      description: "500套 LED 太阳能路灯",
    },
    {
      project: "沙特阿拉伯厂房照明",
      description: "2000盏 LED 工矿灯",
    },
    {
      project: "印尼工业园区照明",
      description: "800套 LED 高杆灯",
    },
    {
      project: "迪拜酒店照明工程",
      description: "3000套 LED 面板灯",
    },
    {
      project: "巴西仓库照明改造",
      description: "1500盏 LED 工矿灯",
    },
    {
      project: "泰国道路照明项目",
      description: "1200盏 LED 路灯",
    },
    {
      project: "肯尼亚学校照明",
      description: "600套 LED 面板灯",
    },
    {
      project: "菲律宾港口照明",
      description: "400套 LED 防爆灯",
    },
    {
      project: "越南工厂照明",
      description: "1000盏 LED 工矿灯",
    },
    {
      project: "巴基斯坦太阳能项目",
      description: "350套 LED 太阳能路灯",
    },
    {
      project: "南非超市照明",
      description: "800套 LED 面板灯",
    },
    {
      project: "孟加拉纺织厂照明",
      description: "600盏 LED 工矿灯",
    },
  ],
  collectedAt: "2026-04-26",
};

export const mockEmailSettings: EmailSettings = {
  senderName: "张经理",
  replyToEmail: "zhang@gmail.com",
  fromEmailPrefix: "zhangmanager",
  mailDomain: "clientconnet.com",
  configuredAt: "2026-04-26",
};

export const mockLeads: Lead[] = [
  {
    id: 1,
    companyName: "ABC Solar Corp",
    website: "abcsolar.com",
    country: "美国",
    industry: "太阳能",
    companyRole: "分销商",
    contactName: "John Smith",
    email: "john@abcsolar.com",
    phone: "+1-555-0100",
    matchScore: 92.5,
    emailStatus: "draft",
  },
  {
    id: 2,
    companyName: "SunPower Distributors",
    website: "sunpower-dist.com",
    country: "美国",
    industry: "太阳能",
    companyRole: "分销商",
    contactName: "Mike Johnson",
    email: "mike@sunpower-dist.com",
    phone: "+1-555-0200",
    matchScore: 88.3,
    emailStatus: "draft",
  },
  {
    id: 3,
    companyName: "Green Energy USA",
    website: "greenenergyusa.com",
    country: "美国",
    industry: "太阳能",
    companyRole: "系统集成商",
    contactName: "Sarah Lee",
    email: "sarah@greenenergyusa.com",
    phone: "+1-555-0300",
    matchScore: 85.1,
    emailStatus: "draft",
  },
  {
    id: 4,
    companyName: "Pacific Solar Solutions",
    website: "pacificsolar.com",
    country: "美国",
    industry: "太阳能",
    companyRole: "批发商",
    contactName: "David Chen",
    email: "david@pacificsolar.com",
    phone: "+1-555-0400",
    matchScore: 82.7,
    emailStatus: "draft",
  },
  {
    id: 5,
    companyName: "National Energy Trading",
    website: "natenergy.com",
    country: "美国",
    industry: "太阳能",
    companyRole: "贸易商",
    contactName: "Emily White",
    email: "emily@natenergy.com",
    phone: "+1-555-0500",
    matchScore: 80.4,
    emailStatus: "draft",
  },
  {
    id: 6,
    companyName: "SolarTech Midwest",
    website: "solartech-mw.com",
    country: "美国",
    industry: "太阳能",
    companyRole: "安装服务商",
    contactName: "Robert Brown",
    email: "robert@solartech-mw.com",
    phone: "+1-555-0600",
    matchScore: 78.9,
    emailStatus: "draft",
  },
  {
    id: 7,
    companyName: "Bright Future Solar",
    website: "brightfuture-solar.com",
    country: "美国",
    industry: "太阳能",
    companyRole: "经销商",
    contactName: "Lisa Anderson",
    email: "lisa@brightfuture-solar.com",
    phone: "+1-555-0700",
    matchScore: 76.2,
    emailStatus: "draft",
  },
  {
    id: 8,
    companyName: "Eco Power Systems",
    website: "ecopower.com",
    country: "美国",
    industry: "太阳能",
    companyRole: "工程服务商",
    contactName: "James Wilson",
    email: "james@ecopower.com",
    phone: "+1-555-0800",
    matchScore: 73.5,
    emailStatus: "draft",
  },
  {
    id: 9,
    companyName: "West Coast Solar",
    website: "wcsolar.com",
    country: "美国",
    industry: "太阳能",
    companyRole: "分销商",
    contactName: "Karen Davis",
    email: "karen@wcsolar.com",
    phone: "+1-555-0900",
    matchScore: 71.0,
    emailStatus: "draft",
  },
  {
    id: 10,
    companyName: "Renewable Energy Inc",
    website: "renewenergy.com",
    country: "美国",
    industry: "太阳能",
    companyRole: "品牌商",
    contactName: "Tom Martinez",
    email: "tom@renewenergy.com",
    phone: "+1-555-1000",
    matchScore: 68.8,
    emailStatus: "draft",
  },
];

export const featureCards: FeatureCardData[] = [
  {
    icon: "building2",
    title: "公司画像",
    description: "建立自己的公司档案",
    prompt: "帮我建立一个公司画像",
  },
  {
    icon: "search",
    title: "客户搜索",
    description: "按行业/国家找潜在客户",
    prompt: "帮我找一批目标客户",
  },
  {
    icon: "pen-line",
    title: "开发信撰写",
    description: "AI 生成个性化开发信",
    prompt: "帮我给客户写开发信",
  },
  {
    icon: "send",
    title: "批量发送",
    description: "批量发送开发信并追踪",
    prompt: "把写好的邮件发出去",
  },
];
