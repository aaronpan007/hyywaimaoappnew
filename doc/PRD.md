# PRD：外贸获客 Agent App

> 版本：v0.1 MVP | 日期：2026-04-26

---

## 1. 产品概述

### 产品名称

**你的AI外贸业务员**

### 定位

面向国内外贸企业的 AI 获客助手。用户通过自然语言对话发起任务，系统自动完成从**市场搜索 → 客户筛选 → 个性化开发信撰写 → 批量邮件发送**的全链路获客流程。

### 目标用户

- 国内外贸企业销售/市场人员
- B2B 出口企业老板
- 无技术背景，期望用对话方式驱动 AI 完成复杂获客工作

### 一句话描述

> 对话即获客：告诉 AI 你想找什么客户，剩下的交给我。

---

## 2. 核心交互设计

### 2.1 页面整体布局

页面采用**左侧导航栏 + 右侧聊天区**的经典 Agent 布局，简约现代风格。

```
┌──────────────────────────────────────────────────────────┐
│ ┌──────────┐ ┌──────────────────────────────────────────┐│
│ │          │ │                                          ││
│ │  侧边栏   │ │              聊天主区域                   ││
│ │  ≈220px  │ │                                          ││
│ │          │ │                                          ││
│ │ ──────── │ │                                          ││
│ │ Logo     │ │   ┌──────────────────────────────────┐   ││
│ │          │ │   │         消息流 / 欢迎屏           │   ││
│ │ 导航菜单  │ │   │                                  │   ││
│ │ ▸ 新对话  │ │   │   (欢迎屏 / 消息气泡 /           │   ││
│ │   公司资料 │ │   │    时间线 / Callout 卡片)        │   ││
│ │   邮箱配置 │ │   │                                  │   ││
│ │          │ │   │                                  │   ││
│ │ ──────── │ │   │                                  │   ││
│ │ 搜索     │ │   │                                  │   ││
│ │          │ │   └──────────────────────────────────┘   ││
│ │ ──────── │ │                                          ││
│ │ 历史记录  │ │   ┌──────────────────────────────────┐   ││
│ │ 今天      │ │   │  输入框              [发送]      │   ││
│ │  · 对话1  │ │   └──────────────────────────────────┘   ││
│ │  · 对话2  │ │                                          ││
│ │ 昨天      │ │                                          ││
│ │  · 对话3  │ └──────────────────────────────────────────┘│
│ └──────────┘                                             │
└──────────────────────────────────────────────────────────┘
```

#### 2.1.1 左侧导航栏

左侧导航栏分三个区域：**顶部导航菜单 → 中间搜索 → 底部历史记录**。

**顶部区域：**

| 位置 | 内容 | 说明 |
|---|---|---|
| 最上方 | Logo + 产品名 | "你的AI外贸业务员"（小圆形图标 + 品牌文字） |
| 导航菜单 | **新对话** | + 号图标，点击新建一个对话（即清空当前聊天区回到欢迎屏） |
| 导航菜单 | **公司资料** | 进入公司画像查看/编辑页（替代原来纯对话中的配置卡片） |
| 导航菜单 | **邮箱配置** | 进入发件邮箱设置页（域名验证、发件人信息等） |

- 导航菜单样式：竖向列表，图标 + 文字，hover 时浅灰背景（#f5f5f5），选中项品牌色高亮
- "公司资料"和"邮箱配置"点击后不离开当前页面，在聊天主区域展示对应的设置界面（类似截图中的设置面板风格）

**中间区域：**

- 搜索栏：全宽输入框 + 搜索图标，placeholder "搜索对话..."
- 用于搜索历史对话记录

**底部区域：**

- 对话历史按时间分组：今天 / 昨天 / 更早
- 每条记录显示：对话标题（取第一条用户消息的摘要）+ 时间
- 点击切换到该对话，加载历史消息
- 悬停显示删除按钮（可选，MVP 可不做）

#### 2.1.2 公司资料页面（点击"公司资料"后展示）

聊天主区域切换为**公司资料展示页**，有两种状态：

**状态 A：未采集（首次进入）**

```
┌──────────────────────────────────────────┐
│                                          │
│            🏢 公司资料                    │
│                                          │
│  还没有采集您的企业信息。                  │
│  AI 会通过对话引导您完成信息收集，          │
│  并自动爬取网站生成结构化画像。             │
│                                          │
│         [ 开始采集我的企业信息 ]           │
│                                          │
│                                          │
│  ────────────────────────────────────     │
│  需要准备：                               │
│  · 公司名称和所属行业                      │
│  · 公司官网地址                           │
│  · 主要产品/服务信息                       │
│  · 核心优势和资质认证                      │
│                                          │
└──────────────────────────────────────────┘
```

**状态 B：已采集（数据存在）**

```
┌──────────────────────────────────────────┐
│  ← 返回对话                              │
│                                          │
│  🏢 深圳光明光电科技有限公司               │
│     LED 照明 / 半导体照明                  │
│     https://www.gm-light.com              │
│                                          │
│  ┌─ 基本信息 ────────────────────────┐   │
│  │ 成立年份：2009年                   │   │
│  │ 员工规模：200-500人                │   │
│  │ 认证：ISO 9001, CE, RoHS          │   │
│  └───────────────────────────────────┘   │
│                                          │
│  ┌─ 主要产品 ────────────────────────┐   │
│  │ LED工矿灯 · LED太阳能路灯          │   │
│  │ LED面板灯 · LED防爆灯              │   │
│  └───────────────────────────────────┘   │
│                                          │
│  ┌─ 核心优势 ────────────────────────┐   │
│  │ 15年LED制造经验                    │   │
│  │ 自有模具车间，支持OEM/ODM          │   │
│  └───────────────────────────────────┘   │
│                                          │
│  ┌─ 案例研究（12个）─────────────────┐   │
│  │ [展开查看全部案例 →]               │   │
│  └───────────────────────────────────┘   │
│                                          │
│  采集时间：2026-04-26                     │
│           [ 重新采集 ]  [ 导出画像 ]      │
│                                          │
└──────────────────────────────────────────┘
```

**交互逻辑：**
- 点击「开始采集我的企业信息」→ 聊天主区域切换为**专用对话窗口**，AI 作为公司画像采集 Agent 开始引导对话：
  - AI："好的，我们先来建立您公司的画像。请问贵公司叫什么名字？主要做哪个行业？"
  - 用户自然语言回答 → AI 追问细节（产品、优势、案例等）
  - AI："了解了，我注意到您提到了公司官网，我可以自动爬取网站来补充信息，这样可以吗？"
  - 用户确认 → 启动 Pipeline（爬取网站 + AI 分析）→ 时间线展示进度
  - 完成后 → Callout 卡片展示画像摘要 → 公司资料页自动更新为"状态 B"
- 「重新采集」同理，进入新一轮对话采集
- 「导出画像」下载 profile.json / profile.md

> **设计理念**：公司资料采集是一个多轮对话的 Agent Pipeline，不是填表。AI 通过追问引导用户逐步提供信息，整个过程自然流畅，符合"你的AI外贸业务员"的定位。

#### 2.1.3 邮箱配置页面（点击"邮箱配置"后展示）

聊天主区域切换为**邮箱配置页面**。配置信息少，直接用表单，不需要 Agent 对话。

**状态 A：未配置（首次进入）**

```
┌──────────────────────────────────────────┐
│                                          │
│             ✉️ 邮箱配置                   │
│                                          │
│  配置后即可通过 AI 批量发送开发信。         │
│                                          │
│  ────────────────────────────────────     │
│                                          │
│  发件人名称                               │
│  ┌──────────────────────────────────┐   │
│  │ 张经理                             │   │
│  └──────────────────────────────────┘   │
│  客户收到邮件时看到的发件人名称             │
│                                          │
│  回复接收邮箱                             │
│  ┌──────────────────────────────────┐   │
│  │ zhang@gmail.com                   │   │
│  └──────────────────────────────────┘   │
│  客户回复邮件时发送到此地址                 │
│                                          │
│              [ 保存配置 ]                │
│                                          │
└──────────────────────────────────────────┘
```

**状态 B：已配置（数据存在）**

```
┌──────────────────────────────────────────┐
│  ← 返回对话                              │
│                                          │
│  ✉️ 邮箱配置                              │
│                                          │
│  发件人名称                               │
│  ┌──────────────────────────────────┐   │
│  │ 张经理                             │   │
│  └──────────────────────────────────┘   │
│                                          │
│  回复接收邮箱                             │
│  ┌──────────────────────────────────┐   │
│  │ zhang@gmail.com                   │   │
│  └──────────────────────────────────┘   │
│                                          │
│  发件邮箱（系统自动生成）                  │
│  ┌──────────────────────────────────┐   │
│  │ zhangmanager @mail.yourdomain.com │   │
│  │                ↑ 可编辑前缀 ↑      │   │
│  └──────────────────────────────────┘   │
│  💡 域名由平台统一管理，您只需设定前缀。    │
│     默认前缀取自您公司名，可自行修改。      │
│                                          │
│              [ 保存修改 ]                │
│                                          │
└──────────────────────────────────────────┘
```

**关键设计：发件邮箱的组成**

发件邮箱由两部分组成，格式为：**前缀@后端域名**

| 部分 | 来源 | 说明 |
|---|---|---|
| 前缀（xxx） | 默认 = 用户公司名（英文/拼音），用户可修改 | 如公司叫"光明光电"则默认为 `gmguangdian` |
| 后端域名（@xxx.com） | 后端统一配置，用户不可见也不可改 | 在后端环境变量中设定（如 `mail.yourdomain.com`），平台运维负责 Resend 域名验证 |

展示规则：
- 未配置时：不显示发件邮箱行（用户还没保存，无法生成前缀）
- 已配置时：显示完整邮箱，前缀部分可编辑，用户修改后即时预览

**前缀生成逻辑：**
1. 如果用户已采集公司资料 → 取 `company_name` 生成英文/拼音前缀（如"光明光电" → `gmguangdian`）
2. 如果没有公司资料 → 取发件人名称拼音（如"张经理" → `zhangmanager`）
3. 去除特殊字符，转小写，拼接简化
4. 用户随时可手动修改，以用户输入为准

> **设计理念**：邮箱配置只需要两个输入（发件人名称 + 回复邮箱），一个自动生成（发件邮箱前缀），信息量浅，直接表单最简单。域名管理是平台运维的事，用户不需要知道。

#### 2.1.4 视觉风格规范

参考截图的简约 Agent 风格：

| 要素 | 规范 |
|---|---|
| **主色调** | 品牌蓝/橙色（待定），用于选中态、按钮、图标高亮 |
| **背景色** | 纯白 #ffffff（聊天区），浅灰 #f7f7f8（侧边栏） |
| **文字色** | 深灰 #1a1a2e（标题/正文），中灰 #6b7280（次要文字），浅灰 #9ca3af（时间戳） |
| **圆角** | 侧边栏菜单 8px，消息卡片 12px，按钮 6px |
| **间距** | 菜单项上下 8px，消息间距 16px，区块间距 24px |
| **字体** | 系统字体栈 `-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif` |
| **字号** | 品牌名 16px bold，消息正文 14px，次要文字 12px |
| **图标** | 线性图标（Lucide Icons），16px 菜单图标 |
| **消息气泡** | AI 消息白底无边框，用户消息浅灰底 #f0f0f0，均无头像 |
| **输入框** | 底部固定，圆角 12px，placeholder "告诉我你想找什么样的客户..."，右侧圆形发送按钮 |

#### 2.1.5 聊天主区域

右侧聊天区是核心交互区域，四种状态：

1. **公司资料展示页**：点击"公司资料"展示（有数据则展示画像，无数据则显示"开始采集"入口 → 点击进入 Agent 对话采集）
2. **邮箱配置页**：点击"邮箱配置"展示简单表单（发件人名称、回复邮箱、自动生成的发件邮箱），直接保存
3. **欢迎屏态**：新对话且无历史消息时展示功能引导
4. **对话态**：正常对话消息流（消息气泡 + 时间线 + Callout 卡片）

#### 2.1.6 空状态欢迎屏（首次进入）

用户首次进入时，聊天区域没有历史消息，显示**欢迎引导屏**（Welcome Screen）替代空白对话区。引导屏包含：

1. **简短问候语**：如"你好，我是你的外贸获客助手。告诉我你想找什么样的客户，我来帮你搞定。"
2. **功能卡片网格**（2×2）：每个卡片对应一个业务能力，点击即发送示例提示词

```
┌─────────────────────────────────────────────────────┐
│                                                     │
│  你好，我是你的外贸获客助手。                         │
│  告诉我你想找什么样的客户，我来帮你搞定。              │
│                                                     │
│  ┌──────────────┐  ┌──────────────┐                 │
│  │ 🏢 公司画像   │  │ 🔍 客户搜索   │                 │
│  │              │  │              │                    │
│  │ 建立自己的    │  │ 按行业/国家   │                    │
│  │ 公司档案      │  │ 找潜在客户    │                    │
│  │              │  │              │                    │
│  │ [开始建立 →]  │  │ [去搜索 →]   │                    │
│  └──────────────┘  └──────────────┘                 │
│  ┌──────────────┐  ┌──────────────┐                 │
│  │ ✉️ 开发信撰写  │  │ 📮 批量发送   │                 │
│  │              │  │              │                    │
│  │ AI 生成个性   │  │ 批量发送开发  │                    │
│  │ 化开发信      │  │ 信并追踪状态  │                    │
│  │              │  │              │                    │
│  │ [开始写 →]   │  │ [去发送 →]   │                    │
│  └──────────────┘  └──────────────┘                 │
│                                                     │
│  💡 试试直接输入：                                    │
│  "帮我找30个美国的LED分销商"                          │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**功能卡片对应示例提示词：**

| 功能 | 点击发送的提示词 |
|---|---|
| 公司画像 | "帮我建立一个公司画像" |
| 客户搜索 | "帮我找一批目标客户" |
| 开发信撰写 | "帮我给客户写开发信" |
| 批量发送 | "把写好的邮件发出去" |

**交互规则：**
- 欢迎屏仅在对话历史为空时显示，用户发送第一条消息后自动消失
- 点击功能卡片 = 在输入框填入示例提示词并自动发送
- 功能卡片可检测前置条件状态：如"开发信撰写"和"批量发送"卡片在无线索时可置灰，显示"请先搜索客户"
- 底部提示词示例可随机轮换

#### 2.1.7 正常对话

欢迎屏消失后，进入正常对话模式。用户在输入框中用自然语言描述需求，例如：

- "帮我找 30 个美国的太阳能板分销商"
- "给这批客户写英文开发信"
- "把写好的邮件发出去"
- "帮我建一个公司画像，我们公司是做 LED 照明的"

### 2.2 意图识别 → Pipeline 匹配

系统后端通过 LLM 理解用户意图，自动匹配对应的业务 Pipeline：

| 用户意图关键词 | 匹配 Pipeline | 触发参数 |
|---|---|---|
| 公司画像 / 我们公司 / profile | company-profile | 行业、产品等 |
| 找客户 / 搜索 / distributor | customer-acquisition | 行业、国家、数量、角色 |
| 写开发信 / 邮件 / email | email-craft | 目标线索、语言 |
| 发邮件 / 发送 / blast | email-blast | 发送范围、批次参数 |

当意图不明确时，AI 通过追问补充必要参数（行业、目标国家等），再启动 Pipeline。

### 2.3 实时步骤时间线（SSE 推送）

Pipeline 启动后，AI 消息区显示一个**步骤时间线**组件，实时更新任务进度：

```
┌─────────────────────────────────────┐
│ ✓ 正在搜索目标公司...              │
│   找到 90 个候选，开始逐个分析      │
│ ● 正在爬取网站内容 (12/90)         │
│   ████████░░░░░░░░ 13%  预计 3 分钟 │
│ ○ AI 筛选与排名                    │
│ ○ 输出结果                         │
└─────────────────────────────────────┘
```

实现方式：后端 Pipeline 每完成一个步骤，通过 SSE（Server-Sent Events）推送状态事件到前端，前端实时渲染时间线。

### 2.4 结果 Callout 卡片

Pipeline 完成后，AI 消息中嵌入一个**Callout 卡片**，展示摘要统计和操作按钮：

```
┌─────────────────────────────────────┐
│ 🔍 客户搜索完成                     │
│                                     │
│ 找到 30 个高质量美国太阳能分销商      │
│ AI 匹配度 ≥ 80%                     │
│                                     │
│ [查看详细列表]  [下载 Excel]          │
└─────────────────────────────────────┘
```

卡片内容根据 Pipeline 类型不同而变化：

- **公司画像**：显示公司名、行业、产品数量、案例数量 + [查看画像] [下载]
- **客户获取**：显示找到数量、平均匹配度、国家分布 + [查看列表] [下载 Excel]
- **开发信撰写**：显示已生成数量、待生成数量 + [查看邮件] [全部生成]
- **批量发送**：显示已发送/总数、成功/失败统计 + [查看状态]

### 2.5 配置缺失时的处理

用户在业务对话中触发需要配置的功能时，根据配置类型采取不同策略。

#### 公司资料缺失（建议型，不阻断）

| 功能 | 说明 |
|---|---|
| 客户获取 (customer-acquisition) | 建议先建公司画像，AI 匹配更精准 |
| 开发信撰写 (email-craft) | 建议先建公司画像，邮件更个性化 |

处理方式：在对话中插入轻量提示条，用户可选择跳过。

```
┌──────────────────────────────────────────┐
│ 💡 建议先完善公司资料                      │
│                                          │
│ 拥有公司画像后，AI 能生成更精准的匹配和     │
│ 个性化的开发信。[去设置 →] 或 [跳过，继续] │
└──────────────────────────────────────────┘
```

- 点击「去设置」→ 跳转到公司资料页
- 点击「跳过，继续」→ Pipeline 正常启动

#### 邮箱配置缺失（阻断型，AI 对话内收集）

当用户触发**批量发送 (email-blast)** 但邮箱未配置时，Pipeline 不启动，AI 在对话中**直接收集所需信息**（不跳转到侧边栏）。

```
┌─ AI 消息 ──────────────────────────────┐

发送邮件需要先配置发件信息，我帮您快速设置一下。

请问您的发件人名称是什么？
（客户收到邮件时看到的名称，如：张经理、Lisa from GMLight）

└────────────────────────────────────────┘

┌─ 用户输入 ────────────────────────────┐
张经理
└────────────────────────────────────────┘

┌─ AI 消息 ──────────────────────────────┐

好的。客户回复的邮件您希望收到哪个邮箱？

└────────────────────────────────────────┘

┌─ 用户输入 ────────────────────────────┐
zhang@gmail.com
└────────────────────────────────────────┘

┌─ AI 消息 ──────────────────────────────┐

配置完成！

· 发件人：张经理
· 回复邮箱：zhang@gmail.com
· 发件邮箱：zhangmanager@mail.yourdomain.com

现在可以继续发送邮件了，需要我现在发吗？

└────────────────────────────────────────┘
```

**交互规则：**
- AI 在对话中直接追问两个信息：发件人名称 + 回复邮箱
- 收集完毕后，后端自动保存到 `user_settings`，自动生成发件邮箱前缀
- AI 用 Callout 卡片展示配置结果供确认
- 确认后自动继续执行之前被中断的发邮件 Pipeline
- 同一对话中只收集一次，不重复追问
- 用户也可随时在侧边栏「邮箱配置」页面修改已保存的配置

### 2.6 表格弹窗预览

点击 Callout 卡片的"查看"按钮，弹出全屏/半屏表格弹窗，支持以下功能：

| 功能 | 说明 |
|---|---|
| **搜索** | 全文搜索（公司名、国家、行业等） |
| **列筛选** | 下拉选择筛选条件（国家、行业、匹配度范围） |
| **排序** | 点击列头切换升序/降序 |
| **固定表头** | 滚动时表头固定，适配大数据量 |
| **分页** | 每页 20/50/100 条，可切换 |
| **下载 Excel** | 一键导出当前筛选结果为 .xlsx |

表格列定义参见第 5 节数据模型。

---

## 3. 四大业务模块

### 3.1 公司画像 (company-profile)

> 为用户自己的公司建立结构化画像，供后续 AI 生成开发信时引用。

**Pipeline 步骤：**

1. **信息收集**：AI 通过对话引导用户输入公司信息（行业、产品、优势等）
2. **网站爬取**：用 Playwright 爬取用户公司官网，提取产品页、关于页等内容
3. **AI 深度分析**：调用 LLM，结合用户提供的信息 + 网站内容，生成结构化画像
4. **输出画像**：存储为 JSON + 生成 Markdown 可读版本

**输出字段（profile.json）：**

```json
{
  "company_name": "",
  "location": "",
  "established": "",
  "industry": "",
  "products": [
    {
      "name": "",
      "description": "",
      "target_customers": "",
      "key_features": []
    }
  ],
  "core_competencies": [],
  "certifications": [],
  "cooperation_models": [],
  "case_studies": [
    {
      "project_name": "",
      "client_type": "",
      "industry": "",
      "country": "",
      "products_used": [],
      "problem_solved": "",
      "result": "",
      "key_highlight": "",
      "usable": true
    }
  ],
  "boundaries": {
    "can_claim": [],
    "cannot_claim": []
  }
}
```

**关键设计：**
- `boundaries` 字段防止 AI 在后续开发信中编造不实信息
- 至少 10 个案例研究，确保开发信有真实素材引用
- 可多次迭代更新，每次对话都可以补充/修改

### 3.2 客户获取 (customer-acquisition)

> 根据用户需求搜索目标市场的潜在客户。

**Pipeline 步骤：**

1. **参数解析**：从用户对话中提取目标行业、国家、公司角色、数量
2. **Serper 搜索**：调用 Serper API 搜索目标公司（搜索量 3× 目标数量）
3. **网站爬取**：逐个爬取候选公司网站（每站 20-30 秒）
4. **AI 筛选排名**：调用 LLM 分析每家公司，按匹配度打分排序
5. **输出结果**：取 Top N 存入数据库

**AI 评分维度：**

| 维度 | 权重 | 说明 |
|---|---|---|
| 业务匹配度 | 高 | 产品/服务是否与用户匹配 |
| 国家匹配 | 高 | 是否在目标国家 |
| 联系信息完整度 | 中 | 是否有邮箱/电话 |
| 信息可信度 | 中 | 非目录站/黄页站（-50 分惩罚） |

**输出字段（leads 表）：**

| 列名 | 类型 | 说明 |
|---|---|---|
| company_name | string | 公司名称 |
| website | string | 公司网站 |
| country | string | 国家/地区 |
| industry | string | 行业 |
| company_role | string | 公司角色（制造商/分销商等） |
| contact_name | string | 联系人 |
| email | string | 邮箱 |
| phone | string | 电话 |
| ai_summary | text | AI 分析摘要 |
| business_match | text | 业务匹配点 |
| outreach_suggestion | text | 开发建议 |
| match_score | float | AI 匹配度评分 |

### 3.3 开发信撰写 (email-craft)

> 为已获取的线索批量生成个性化开发信。

**Pipeline 步骤：**

1. **加载线索**：从数据库读取已有线索（优先选择无开发信的记录）
2. **加载公司画像**：读取用户的 company-profile 作为邮件素材
3. **AI 生成**：为每条线索调用 LLM 生成个性化开发信
4. **存储结果**：将主题行 + 邮件正文写回数据库

**AI 生成规则（7 条）：**

1. **自然开头**：提及具体信息，不做泛泛问候
2. **匹配分析**：客户需求 × 我方能力的交叉点
3. **案例引用**：引用 1-2 个相关案例研究
4. **专业语气**：自然、专业、无模板感
5. **轻量 CTA**：以兴趣探询结尾，不强行推销
6. **杜绝编造**：仅使用已有数据，不虚构信息
7. **长度控制**：英文 150-300 词，中文 200-400 字

**参数：**
- `--language`：en（默认）或 cn
- `--all`：为所有无草稿的线索生成
- `--select`：指定线索 ID
- `--regenerate`：重新生成已有草稿

### 3.4 批量发送 (email-blast)

> 通过 Resend API 批量发送开发信，实时跟踪发送状态。

**Pipeline 步骤：**

1. **预检查**：验证 Resend API Key、发件人域名配置
2. **读取待发送**：从数据库筛选有邮箱 + 有开发信草稿的记录
3. **发送预览**：展示待发送列表，用户确认
4. **执行发送**：按批次发送（支持速率限制）
5. **状态回写**：实时更新每封邮件的发送状态

**发送控制参数：**

| 参数 | 默认值 | 范围 | 说明 |
|---|---|---|---|
| batch_size | 10 | 5-20 | 每批发送数量 |
| delay_min | 60 | 30-600 | 批次间最小间隔（秒） |
| delay_max | 120 | 30-600 | 批次间最大间隔（秒） |
| daily_limit | 50 | 20-100 | 每日发送上限 |
| send_mode | auto | auto/immediate/schedule | 发送模式 |
| dry_run | false | - | 预览模式，不实际发送 |

**状态追踪：**

每封邮件的发送状态实时更新：`pending` → `sending` → `sent` / `failed`

---

## 4. 技术架构

### 4.1 整体架构图

```
┌──────────────┐     SSE      ┌──────────────┐
│              │ ◄─────────── │              │
│   Next.js    │   HTTP API   │   FastAPI    │
│   (前端)     │ ───────────► │   (后端)     │
│   Vercel     │              │   腾讯云      │
└──────────────┘              └──────┬───────┘
                                     │
                              异步任务队列
                                     │
                              ┌──────▼───────┐
                              │   Pipeline   │
                              │   Worker     │
                              │   (Python)   │
                              └──────┬───────┘
                                     │
                    ┌────────┬───────┼───────┬────────┐
                    ▼        ▼       ▼       ▼        ▼
                 Serper  Playwright  LLM   PostgreSQL Resend
                 (搜索)   (爬虫)  (Replicate)  (DB)   (邮件)
```

### 4.2 技术栈总览

| 层 | 技术 | 说明 |
|---|---|---|
| **前端框架** | Next.js 14 (App Router) | TypeScript, Tailwind CSS |
| **前端 AI** | Vercel AI SDK | `useChat` Hook 管理对话状态 |
| **前端 UI** | Lucide Icons | 线性图标，strokWidth 1.8 |
| **前端表格** | 原生实现 | 搜索/筛选/排序/分页 |
| **前端 Excel** | SheetJS (xlsx) | 一键导出 |
| **后端框架** | Python FastAPI | 异步支持 |
| **后端 ORM** | SQLAlchemy 2.0 | 异步模式 (AsyncSession) |
| **后端迁移** | Alembic | 数据库版本管理 |
| **数据库** | PostgreSQL 16+ | 本机部署（腾讯云服务器） |
| **认证** | Better Auth | 邮箱注册/登录 + JWT 鉴权 |
| **搜索** | Serper API | Google 搜索 |
| **爬虫** | Playwright | 网站内容爬取 |
| **LLM** | Replicate API | 调用 OpenAI 模型 |
| **邮件** | Resend API | 开发信发送 |
| **部署前端** | Vercel | 自动部署 |
| **部署后端** | 腾讯云轻量服务器 | Nginx + PM2 |
| **部署数据库** | PostgreSQL 本机 | 同服务器 |

### 4.3 前端：Next.js + Vercel AI SDK

- **框架**：Next.js 14 (App Router)
- **AI SDK**：Vercel AI SDK（`useChat` Hook 管理对话状态）
- **流式**：SSE（Server-Sent Events）推送 Pipeline 步骤状态
- **图标**：Lucide React（线性风格，strokWidth 1.8）
- **Excel 导出**：SheetJS (xlsx)

### 4.4 后端：Python FastAPI

- **框架**：FastAPI（异步支持）
- **ORM**：SQLAlchemy 2.0（异步模式）
- **迁移**：Alembic（数据库版本管理）
- **API 格式**：RESTful JSON + SSE 流式端点
- **异步任务**：后台 Pipeline 执行，通过 SSE 推送进度
- **认证**：Better Auth（JWT 鉴权中间件）

### 4.5 Worker：Python Pipeline

- 沿用现有 `waimao_toolkit_new/skills/` 中的 Pipeline 逻辑
- 改造为可独立调用的 Python 模块
- 输出从 CSV/飞书改为写入 PostgreSQL
- 通过回调/事件机制推送步骤状态到 FastAPI

### 4.6 数据库：PostgreSQL

- **部署**：PostgreSQL 装在腾讯云服务器本地（避免海外延迟）
- **版本**：PostgreSQL 16+
- **ORM**：SQLAlchemy 2.0（异步模式）
- **迁移**：Alembic 管理表结构变更
- **认证**：Better Auth（邮箱注册/登录 + JWT 鉴权）

### 4.7 外部服务

| 服务 | 用途 | SDK/协议 |
|---|---|---|
| Serper | Google 搜索 | REST API |
| Playwright | 网站爬取 | Python SDK |
| Replicate | LLM 调用（OpenAI 模型） | REST API |
| Resend | 邮件发送 | REST API |

---

## 5. 数据模型

### ER 关系图

```
users 1──N tasks 1──N task_logs
                  1──N leads N──1 company_profiles (my_profile)
leads 1──N outreach_emails
```

### 表结构

#### users（用户账户）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | 自增 ID |
| username | TEXT | 用户名 |
| created_at | TIMESTAMP | 创建时间 |

> MVP 阶段固定单用户，后续扩展登录注册。

#### user_settings（用户配置）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | 自增 ID |
| user_id | INTEGER FK | 关联用户（MVP 固定为 1） |
| sender_name | TEXT | 发件人名称（邮件发送功能） |
| from_email_prefix | TEXT | 发件邮箱前缀（如 `zhangmanager`），用户可编辑 |
| reply_to_email | TEXT | 回复接收邮箱 |
| profile_id | INTEGER FK | 当前使用的公司画像 ID（关联 company_profiles） |
| updated_at | TIMESTAMP | 最后更新时间 |

> **注意**：`from_email_prefix` + 后端配置的域名 = 完整发件邮箱（如 `zhangmanager@mail.yourdomain.com`）。域名是平台级配置，不在用户表中。

#### tasks（任务记录）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | 自增 ID |
| user_id | INTEGER FK | 关联用户 |
| type | TEXT | Pipeline 类型：company-profile / customer-acquisition / email-craft / email-blast |
| status | TEXT | pending / running / completed / failed |
| params | TEXT (JSON) | 任务参数（行业、国家、数量等） |
| result_summary | TEXT (JSON) | 结果摘要（数量、统计等） |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

#### task_logs（步骤日志 → 前端时间线）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | 自增 ID |
| task_id | INTEGER FK | 关联任务 |
| step_number | INTEGER | 步骤序号 |
| step_name | TEXT | 步骤名称 |
| status | TEXT | pending / running / completed / failed |
| message | TEXT | 步骤描述/进度信息 |
| progress | INTEGER | 进度百分比 0-100 |
| created_at | TIMESTAMP | 创建时间 |

#### leads（客户线索）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | 自增 ID |
| task_id | INTEGER FK | 来源任务 |
| company_name | TEXT | 公司名称 |
| website | TEXT | 公司网站 |
| country | TEXT | 国家/地区 |
| industry | TEXT | 行业 |
| company_role | TEXT | 公司角色 |
| contact_name | TEXT | 联系人 |
| email | TEXT | 邮箱 |
| phone | TEXT | 电话 |
| ai_summary | TEXT | AI 分析摘要 |
| business_match | TEXT | 业务匹配点 |
| outreach_suggestion | TEXT | 开发建议 |
| match_score | REAL | 匹配度评分 0-100 |
| created_at | TIMESTAMP | 创建时间 |

#### company_profiles（公司画像）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | 自增 ID |
| user_id | INTEGER FK | 关联用户 |
| task_id | INTEGER FK | 生成任务 |
| company_name | TEXT | 公司名称 |
| profile_data | TEXT (JSON) | 完整画像数据（profile.json 结构） |
| profile_markdown | TEXT | Markdown 可读版本 |
| is_current | BOOLEAN | 是否为当前使用的画像 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

#### outreach_emails（开发信 + 发送状态）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | 自增 ID |
| lead_id | INTEGER FK | 关联线索 |
| task_id | INTEGER FK | 生成任务 |
| email_subject | TEXT | 邮件主题 |
| email_body | TEXT | 邮件正文（HTML） |
| send_status | TEXT | draft / pending / sending / sent / failed |
| sent_at | TIMESTAMP | 发送时间 |
| error_message | TEXT | 失败原因 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

---

## 6. API 设计

### 6.1 对话接口

**POST /api/chat**

主入口。接收用户消息，返回 SSE 流式响应。

请求：
```json
{
  "message": "帮我找30个美国的太阳能板分销商",
  "conversation_id": "uuid"
}
```

响应（SSE 流）：
```
event: thinking
data: {"content": "好的，我来帮您搜索..."}

event: config_required
data: {"type": "email_settings", "message": "发送邮件需要先配置发件信息", "blocker": true}
# 后端不启动 Pipeline，AI 在对话中直接追问收集 sender_name 和 reply_to_email

event: suggestion
data: {"type": "profile_suggested", "message": "建议先完善公司资料，AI 能生成更精准的匹配", "blocker": false}

event: pipeline_started
data: {"task_id": 123, "type": "customer-acquisition", "params": {...}}

event: step_update
data: {"task_id": 123, "step": 1, "name": "搜索目标公司", "status": "running", "progress": 30, "message": "已找到27个候选..."}

event: step_update
data: {"task_id": 123, "step": 2, "name": "爬取网站内容", "status": "running", "progress": 15, "message": "正在爬取 (12/90)"}

event: result
data: {"task_id": 123, "type": "callout", "summary": {"total": 30, "avg_score": 85.3}, "actions": ["view_list", "download_excel"]}

event: done
data: {"task_id": 123}
```

### 6.2 配置接口

**GET /api/settings**

获取当前用户配置（用于判断是否需要收集缺失信息）。

响应：
```json
{
  "sender_name": "张经理",
  "from_email_prefix": "zhangmanager",
  "from_email": "zhangmanager@mail.yourdomain.com",
  "reply_to_email": "zhang@gmail.com",
  "profile_id": 1
}
```

> `from_email` 由后端拼接 `from_email_prefix` + `MAIL_DOMAIN` 生成，前端只传 prefix。

**PUT /api/settings**

更新用户配置（侧边栏「邮箱配置」页面的"保存配置"按钮调用）。

请求：
```json
{
  "sender_name": "张经理",
  "from_email_prefix": "zhangmanager",
  "reply_to_email": "zhang@gmail.com"
}
```

响应：
```json
{
  "sender_name": "张经理",
  "from_email_prefix": "zhangmanager",
  "from_email": "zhangmanager@mail.yourdomain.com",
  "reply_to_email": "zhang@gmail.com"
}
```

**POST /api/settings/generate-prefix**

根据公司名或发件人名称自动生成发件邮箱前缀，供用户确认或修改。

请求：
```json
{
  "company_name": "光明光电"
}
```

响应：
```json
{
  "suggested_prefix": "gmguangdian"
}
```

### 6.3 任务接口

**GET /api/tasks**

获取任务列表。

参数：`?type=customer-acquisition&status=completed&page=1&limit=20`

响应：
```json
{
  "items": [
    {
      "id": 123,
      "type": "customer-acquisition",
      "status": "completed",
      "result_summary": {"total": 30, "avg_score": 85.3},
      "created_at": "2026-04-26T10:00:00Z"
    }
  ],
  "total": 42,
  "page": 1,
  "limit": 20
}
```

**GET /api/tasks/:id**

获取任务详情 + 步骤日志。

响应：
```json
{
  "id": 123,
  "type": "customer-acquisition",
  "status": "completed",
  "params": {"industry": "solar", "country": "US", "num": 30},
  "result_summary": {"total": 30, "avg_score": 85.3},
  "logs": [
    {"step_number": 1, "name": "搜索目标公司", "status": "completed", "message": "找到90个候选", "progress": 100},
    {"step_number": 2, "name": "爬取网站内容", "status": "completed", "message": "完成90个网站爬取", "progress": 100},
    {"step_number": 3, "name": "AI筛选与排名", "status": "completed", "message": "筛选出30个高质量线索", "progress": 100}
  ],
  "created_at": "2026-04-26T10:00:00Z",
  "updated_at": "2026-04-26T10:15:00Z"
}
```

### 6.4 线索接口

**GET /api/leads**

获取线索列表（支持分页/搜索/排序）。

参数：
- `task_id`：筛选来源任务
- `search`：全文搜索
- `country`：国家筛选
- `industry`：行业筛选
- `min_score`：最低匹配度
- `sort_by`：排序字段（match_score / company_name / created_at）
- `sort_order`：asc / desc
- `page` / `limit`：分页

响应：
```json
{
  "items": [
    {
      "id": 1,
      "company_name": "ABC Solar Corp",
      "website": "https://abcsolar.com",
      "country": "United States",
      "industry": "Solar Energy",
      "company_role": "Distributor",
      "contact_name": "John Smith",
      "email": "john@abcsolar.com",
      "phone": "+1-555-0100",
      "ai_summary": "Major US solar distributor...",
      "business_match": "Product lineup matches...",
      "match_score": 92.5,
      "email_status": "draft"
    }
  ],
  "total": 30,
  "page": 1,
  "limit": 20,
  "filters": {
    "countries": ["United States"],
    "industries": ["Solar Energy"],
    "score_range": [60, 95]
  }
}
```

**GET /api/leads/:id/export**

下载线索为 Excel 文件。

参数：`?format=xlsx`

响应：`Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`

### 6.5 公司画像接口

**GET /api/profile**

获取当前公司画像。

**POST /api/profile**

创建/更新公司画像（由 Pipeline 自动调用，也可手动编辑）。

**PUT /api/profile/:id**

更新画像字段。

### 6.6 邮件接口

**GET /api/emails**

获取开发信列表（支持分页/搜索/筛选）。

参数：`?lead_id=&status=draft&task_id=`

**POST /api/emails/generate**

触发开发信生成 Pipeline。

请求：
```json
{
  "lead_ids": [1, 2, 3],
  "language": "en",
  "regenerate": false
}
```

**POST /api/emails/send**

触发批量发送 Pipeline。

请求：
```json
{
  "task_id": 123,
  "batch_size": 10,
  "dry_run": false
}
```

---

## 7. MVP 范围

### 7.1 MVP 做什么（v0.1）

| 功能 | 优先级 | 说明 |
|---|---|---|
| 后端骨架 | P0 | FastAPI + PostgreSQL + 7 张数据表 + API 路由定义 |
| 公司画像 Pipeline | P0 | 对话引导 + 网站爬取 + AI 分析 |
| 客户获取 Pipeline | P0 | Serper 搜索 + 爬取 + AI 筛选 |
| 开发信撰写 Pipeline | P0 | 批量生成个性化邮件 |
| 批量发送 Pipeline | P0 | Resend 发送 + 状态追踪 |
| 实时步骤时间线 | P0 | SSE 推送 Pipeline 进度 |
| 结果 Callout 卡片 | P0 | 摘要统计 + 操作按钮 |
| 聊天对话界面 | P0 | 自然语言输入，AI 响应（前端已完成） |
| 配置收集 Callout 卡片 | P0 | 首次使用某功能时收集必要配置（如发件邮箱） |
| 表格弹窗预览 | P1 | 搜索/筛选/排序/固定表头（前端已完成） |
| Excel 导出 | P1 | 一键下载 .xlsx |
| 历史任务列表 | P1 | 查看过去的任务和结果 |
| 登录注册 | P2 | Better Auth 邮箱注册/登录 + JWT 鉴权（核心功能跑通后加入） |

### 7.2 MVP 不做什么

| 功能 | 原因 |
|---|---|
| 飞书集成 | 数据全部在网页内管理 |
| 付费系统 | 先免费收集反馈 |
| 多语言界面 | 目标用户为国内企业，界面固定中文 |
| 手机端适配 | 优先桌面端完整体验 |
| 独立 Agent 框架 | 伪 Agent 体验即可，Pipeline 后端足够 |
| 自定义 Pipeline | 固定 4 个业务模块 |

### 7.3 开发阶段顺序

> 先跑通核心业务链路（后端 + Pipeline），再补登录注册。

```
阶段一：后端骨架
  ├── FastAPI 项目结构搭建
  ├── PostgreSQL 连接 + SQLAlchemy ORM 配置
  ├── Alembic 数据库迁移
  ├── 7 张数据表创建
  └── 核心 API 路由定义（/api/chat, /api/leads, /api/profile, /api/settings）

阶段二：Pipeline 改造 + 前后端联调
  ├── 改造 customer-acquisition skill → PostgreSQL + SSE 事件推送
  ├── 改造 company-profile skill → PostgreSQL + SSE 事件推送
  ├── 改造 email-craft skill → PostgreSQL + SSE 事件推送
  ├── 改造 email-blast skill → PostgreSQL + SSE 事件推送
  ├── 前端 useChat 接入 /api/chat SSE 流
  ├── 前端替换所有 mock 数据为真实 API 调用
  └── 时间线 / Callout / 表格弹窗接入真实数据

阶段三：登录注册
  ├── Better Auth 集成（邮箱注册/登录）
  ├── JWT 鉴权中间件
  ├── 前端登录/注册页面
  └── 数据按用户隔离

阶段四：部署上线
  ├── 前端推 Vercel
  ├── 后端部署腾讯云（PostgreSQL + Nginx + PM2）
  ├── 域名 + HTTPS 配置
  └── CORS + 环境变量配置
```

### 7.4 后续迭代方向（v0.2+）

- 登录注册优化（手机号、OAuth）
- 多租户数据隔离增强
- 邮件打开/回复追踪
- 线索 CRM 管理（跟进状态、备注）
- 定时任务（定时搜索、定时发送）
- 更多获客渠道（LinkedIn、海关数据等）

---

## 8. 部署方案

### 8.1 前端部署

- **平台**：Vercel（免费额度充足）
- **域名**：待定
- **构建**：`next build` 自动部署，Git push 触发

### 8.2 后端部署

- **平台**：腾讯云 / 阿里云轻量应用服务器（2C4G 起步）
- **进程管理**：systemd 或 PM2
- **反向代理**：Nginx（HTTPS + API 路由）
- **Python 环境**：Python 3.11 + virtualenv

### 8.3 数据库

- **类型**：PostgreSQL 16+
- **部署**：本机部署（与后端同一台腾讯云服务器）
- **管理**：Alembic 迁移
- **备份**：pg_dump 定时备份（可选）

### 8.4 环境变量

```env
# 数据库
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/waimao

# AI / LLM
REPLICATE_API_TOKEN=r8_xxx
# 测试阶段默认使用 Replicate openai/gpt-4.1-nano，降低调试成本；
# 生产质量生成时可一键改回 openai/gpt-5.2。
REPLICATE_MODEL=openai/gpt-4.1-nano

# 搜索
SERPER_API_KEY=xxx

# 邮件发送
RESEND_API_KEY=re_xxx
MAIL_DOMAIN=mail.yourdomain.com
# 完整发件地址 = {用户设置的前缀}@{MAIL_DOMAIN}
# MAIL_DOMAIN 由平台运维配置，Resend 域名验证在部署时一次性完成

# 后端
API_SECRET=xxx
CORS_ORIGIN=https://your-app.vercel.app
```

---

## 附录 A：与现有 Skill 代码的映射关系

| 现有 Skill 目录 | 对应 Pipeline | 改造要点 |
|---|---|---|
| `skills/company-profile/scripts/` | CompanyProfilePipeline | 输出从 profile.json → PostgreSQL company_profiles 表 |
| `skills/customer-acquisition/scripts/` | CustomerAcquisitionPipeline | 输出从 CSV → PostgreSQL leads 表；移除飞书逻辑 |
| `skills/email-craft/scripts/` | EmailCraftPipeline | 输出从 CSV → PostgreSQL outreach_emails 表；移除飞书逻辑 |
| `skills/email-blast/scripts/` | EmailBlastPipeline | 状态从 CSV → PostgreSQL outreach_emails 表；移除飞书逻辑 |
| `skills/_shared/setup_env.py` | 共享配置模块 | 保留，从环境变量读取 API Key |
| `skills/_shared/csv_utils.py` | Excel 导出工具 | 保留，用于 Excel 下载功能 |

## 附录 B：数据流全景

```
用户对话 → LLM 意图识别 → Pipeline 调度

[公司画像]                    [客户获取]
  输入：对话 + 网站              输入：行业/国家/数量
  处理：爬取 → AI分析            处理：Serper → 爬取 → AI筛选
  输出：company_profiles         输出：leads
         ↓                            ↓
  [引用画像] ──────────────────→ [加载画像]

                                      ↓
                               [开发信撰写]
                                 输入：leads + profile
                                 处理：AI 生成个性化邮件
                                 输出：outreach_emails (draft)
                                      ↓
                               [批量发送]
                                 输入：outreach_emails (draft)
                                 处理：Resend API 分批发送
                                 输出：outreach_emails (sent/failed)
```
 
 
---

## 附录 C：客户名单与开发信撰写范围设计补充（2026-04-30）

### C.1 设计目标

开发信撰写不应只服务于系统搜索出来的客户。真实业务中，用户可能已有自己的客户数据，也可能只想给少量客户手动写几封开发信。因此新增“客户名单工作台”作为统一入口，但必须保护已经稳定的 customer-acquisition pipeline。

核心原则：

- customer-acquisition pipeline 只作为上游数据生产器，继续负责搜索、爬取、AI 分析、排序、保存 leads，不在该 pipeline 内加入客户名单/CRM 复杂逻辑。
- 客户名单只读取和组织现有 leads / tasks / outreach_emails，不反向影响客户开发 pipeline。
- 开发信撰写 pipeline 从“默认读取全部 leads”调整为“按用户选择范围读取 leads”。
- 上传客户、手动输入客户走独立导入/手动来源，不复用客户开发 pipeline。

### C.2 客户名单页面

导航栏新增：客户名单。

默认表格列：

| 列 | 说明 |
|---|---|
| 公司名称 | lead.company_name |
| 网站 | lead.website |
| 国家/地区 | lead.country |
| 行业 | lead.industry |
| 公司角色 | lead.company_role |
| 联系人 | lead.contact_name |
| 邮箱 | lead.email |
| 来源 List | 短期使用 lead.task_id 关联 Task 作为来源批次 |
| 匹配度 | lead.match_score |
| 开发信状态 | 未写 / 已写 / 已发送 |
| 操作 | 查看详情、生成/重新生成开发信、导出等 |

详情/展开内容：

- AI 分析摘要：lead.ai_summary
- 业务匹配点：lead.business_match
- 开发建议：lead.outreach_suggestion
- 邮件主题：outreach_emails.email_subject
- 开发信正文：outreach_emails.email_body

开发信状态映射：

- 未写：没有关联 outreach_emails 记录。
- 已写：存在 outreach_emails，且 send_status = draft。
- 已发送：存在 outreach_emails，且 send_status = sent。

MVP 暂不把发送失败放入主状态枚举；失败原因可后续在详情中展示。

### C.3 List / 来源批次策略

MVP 不新增复杂 CRM 表。短期使用现有 Task 作为 List：

- 每次客户搜索 task = 一个来源 List。
- 每次上传客户资料生成开发信，可创建一个 import/email-craft task，作为上传来源 List。
- 每次手动输入客户，可创建一个 manual task，作为手动来源 List。

List 命名先自动生成，例如：

- USA ceiling systems - 2026-04-30
- 上传客户名单 - 2026-04-30
- 手动输入客户 - 2026-04-30

后续如果需要用户自定义命名、一个客户属于多个 List，再增加 lead_lists / lead_list_items 多对多表；MVP 阶段不做。

### C.4 开发信撰写入口

点击“开发信撰写”后，用户应先选择生成范围，而不是默认全量生成：

1. 选择已有客户 List。
2. 上传新的客户资料。
3. 手动输入少量客户信息。

生成参数建议支持：

```json
{
  "source_task_id": 123,
  "lead_ids": [1, 2, 3],
  "files": [],
  "manual_leads": [],
  "language": "en",
  "only_without_email_draft": true
}
```

默认只为“未写”客户生成开发信，避免重复消耗模型额度。用户明确点击“重新生成”时，才覆盖或新增新的开发信草稿。

### C.5 手动输入客户

当用户只有几个目标客户时，可以在聊天框直接输入客户信息，例如：

> 帮我给 ABC Lighting 写一封英文开发信，他们是美国酒店照明工程商，网站是 abc.com，联系人 John，邮箱 john@abc.com。

MVP 流程：

1. LLM 从自然语言中抽取客户字段。
2. 保存为 leads 记录，来源 List 为“手动输入客户”。
3. 复用 email-craft prompt 和 pipeline 生成开发信。
4. 开发信保存到 outreach_emails，后续可在客户名单中查看、导出、发送。

这样少量客户和批量客户最终都进入统一客户池，避免后续 email-blast 状态追踪断裂。

### C.6 实施顺序

1. 新增客户名单导航页，读取现有 leads + outreach_emails，展示默认列和三态开发信状态。
2. 新增客户详情弹窗/展开区，展示 AI 分析摘要、业务匹配点、开发建议、邮件主题、开发信正文。
3. email-craft 支持按 source_task_id / lead_ids 选择范围生成，不再默认全量读取 leads。
4. 上传客户资料保存为独立来源 List 后再生成开发信。
5. 手动输入客户保存为 lead 后复用 email-craft 生成。

### C.7 风险控制

- 不修改 customer-acquisition pipeline 的搜索、爬取、AI 分析、排序、保存主流程。
- 新增能力优先放在 lead workspace、lead_service、email_craft_pipeline_service 外围逻辑中。
- 现有 leads.task_id 含义保持为“来源任务”。
- 客户名单页面只做读取和聚合展示，不改变上游 pipeline 输出。
