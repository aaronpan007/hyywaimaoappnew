# 前端页面设计提示词

> 给 AI 设计工具（如 v0.dev / bolt.new / Claude Artifacts）使用的提示词。
> 每个页面独立一条 prompt，复制粘贴即可使用。

---

## 全局设计约束（附加到每条 prompt 尾部）

以下设计约束适用于所有页面，生成时请严格遵守：

**设计风格：简约现代 Agent 聊天应用，参考 ChatGPT / Claude / Perplexity 的对话界面风格。**

- **配色**：主色调用蓝色（#2563EB），背景纯白 #FFFFFF（主内容区）、浅灰 #F7F7F8（侧边栏），文字深灰 #1A1A2E（标题正文）、中灰 #6B7280（次要文字）、浅灰 #9CA3AF（时间戳/占位符）
- **字体**：系统字体栈 `-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif`，界面文案中文
- **圆角**：侧边栏菜单 8px，消息卡片 12px，按钮 8px，输入框 12px
- **图标**：使用线性图标风格（Lucide Icons），不使用填充图标
- **侧边栏**：宽度 220px，固定在左侧，浅灰背景，内容垂直排列
- **整体布局**：左侧 220px 固定侧边栏 + 右侧自适应主内容区，无顶部导航栏
- **不要**：不要深色模式，不要渐变背景，不要阴影过重，不要卡通/游戏风格，不要头像

---

## 需要设计的页面清单（共 8 页）

| # | 页面 | 说明 |
|---|---|---|
| 1 | 主布局 · 欢迎屏 | 侧边栏 + 空白聊天区（首次进入的引导屏） |
| 2 | 主布局 · 对话中 | 侧边栏 + 有消息的聊天区（展示消息气泡样式） |
| 3 | 公司资料 · 未采集 | 点击侧边栏"公司资料"后的空状态页 |
| 4 | 公司资料 · 已采集 | 公司画像数据展示页 |
| 5 | 邮箱配置 · 未配置 | 点击侧边栏"邮箱配置"后的空状态页 |
| 6 | 邮箱配置 · 已配置 | 邮箱配置展示 + 编辑页 |
| 7 | 对话 · Pipeline 时间线 | 对话中展示任务进度时间线 |
| 8 | 表格弹窗 · 客户线索 | 弹出式全屏表格（搜索/筛选/排序） |

---

## Page 1: 主布局 · 欢迎屏

```
Design a modern AI chat application layout for a Chinese B2B foreign trade lead generation product called "你的AI外贸业务员" (Your AI Foreign Trade Salesperson).

**Layout**: Fixed left sidebar (220px, background #F7F7F8) + right main content area (white background, centered content).

**Left Sidebar (top to bottom)**:
- Top: A small circular icon (blue #2563EB) + brand text "你的AI外贸业务员" (16px bold, dark gray)
- Divider line
- Navigation menu (vertical list, 16px Lucide icons + 14px text, dark gray #1A1A2E):
  - "新对话" with a Plus icon (selected state: light blue background #EFF6FF, blue text)
  - "公司资料" with a Building2 icon
  - "邮箱配置" with a Mail icon
- Divider line
- Search bar: full-width input with Search icon, placeholder "搜索对话..." (light gray #9CA3AF text), background #EEEEEE, rounded 8px
- Divider line
- Chat history section: small gray header "今天" (12px), below it one item "AI能力概览" with "19m" timestamp in lighter gray
- Bottom: "升级计划" text in blue

**Main Content Area (centered, vertically and horizontally)**:
No chat messages. Instead show a welcome/onboarding screen:

- A centered block (max-width 600px):
- Main greeting: "你好，我是你的外贸获客助手。" (20px, dark gray, bold)
- Subtitle: "告诉我你想找什么样的客户，我来帮你搞定。" (14px, #6B7280)
- 2x2 grid of feature cards (4 cards, each approx 260x120px, white background, 1px #E5E7EB border, 12px rounded corners):
  1. Icon: Building2 (blue). Title: "公司画像". Description: "建立自己的公司档案". Arrow icon on the right.
  2. Icon: Search (blue). Title: "客户搜索". Description: "按行业/国家找潜在客户". Arrow icon.
  3. Icon: PenLine (blue). Title: "开发信撰写". Description: "AI 生成个性化开发信". Arrow icon.
  4. Icon: Send (blue). Title: "批量发送". Description: "批量发送开发信并追踪". Arrow icon.
- Below the grid, a subtle hint: "💡 试试直接输入：帮我找30个美国的LED分销商" (13px, #9CA3AF)
- Bottom of main area: fixed input bar - a rounded (12px) text input spanning full width with placeholder "告诉我你想找什么样的客户..." on the left, and a circular blue send button (40px) with white Send icon on the right. Light #E5E7EB border around the input.

**Design constraints**: Clean, minimal, lots of white space. No dark mode. No gradients. Chinese text. System font stack. Use Lucide-style linear icons only.
```

---

## Page 2: 主布局 · 对话中

```
Design a modern AI chat application in conversation state for a Chinese B2B foreign trade product called "你的AI外贸业务员".

**Layout**: Same fixed left sidebar (220px) + right main chat area as the welcome screen design. Sidebar shows "新对话" selected, chat history below. The main area now has chat messages.

**Left Sidebar**: Same as previous - brand logo, nav menu (新对话 selected/highlighted, 公司资料, 邮箱配置), search bar, chat history "今天 > AI能力概览 19m".

**Main Chat Area (scrollable)**:
Show 4 messages alternating between AI and user:

Message 1 (AI, left-aligned):
- No avatar. Text: "好的，我来帮您搜索美国的太阳能板分销商。请稍等，我先搜索相关公司..." (14px, #1A1A2E)
- Below text: timestamp "19分钟前" (12px, #9CA3AF)

Message 2 (User, right-aligned):
- Light gray background (#F0F0F0), 12px rounded corners, max-width 70% right-aligned. Text: "帮我找30个美国的太阳能板分销商" (14px, #1A1A2E)

Message 3 (AI, left-aligned):
- A result callout card (white background, 1px #E5E7EB border, 12px rounded, max-width 500px):
  - Top: Blue search icon + "客户搜索完成" (14px bold)
  - Stats: "找到 30 个高质量美国太阳能分销商" + "AI 匹配度 ≥ 80%" (13px, #6B7280)
  - Two buttons side by side: "查看详细列表" (blue outlined button) and "下载 Excel" (blue filled button, white text), both 8px rounded
- Below card: AI text: "已为您筛选出30个高匹配度的美国太阳能板分销商。您可以查看详细列表，也可以直接下载 Excel 文件。需要我帮您给这些客户写开发信吗？" (14px)

Message 4 (User, right-aligned):
- Gray background. Text: "好的，先写英文开发信" (14px)

**Bottom**: Same fixed input bar as before - rounded text input with placeholder and blue circular send button.

**Design constraints**: Clean message bubbles. AI messages have no background. User messages have #F0F0F0 background. No avatars. Chinese text. Lots of vertical spacing between messages (24px gap).
```

---

## Page 3: 公司资料 · 未采集

```
Design a page for a Chinese B2B AI product. This is the "Company Profile" page shown when no company data has been collected yet.

**Layout**: Same fixed left sidebar (220px, #F7F7F8) on the left. The sidebar nav item "公司资料" is selected/highlighted (light blue background #EFF6FF). Main content area on the right shows the company profile empty state.

**Left Sidebar**: Brand "你的AI外贸业务员", nav menu (新对话, 公司资料 highlighted, 邮箱配置), search bar, chat history.

**Main Content Area** (centered vertically and horizontally):
A centered card/block (max-width 480px):

- Large icon: Building2 (48px, light gray #D1D5DB) centered
- Title: "公司资料" (20px bold, #1A1A2E)
- Description: "还没有采集您的企业信息。" (14px, #6B7280)
- Description line 2: "AI 会通过对话引导您完成信息收集，" (14px, #6B7280)
- Description line 3: "并自动爬取网站生成结构化画像。" (14px, #6B7280)
- Gap (24px)
- A primary button: "开始采集我的企业信息" (blue #2563EB background, white text, 14px, full-width, 12px rounded, 44px height)
- Gap (32px)
- A light divider line
- Below divider: "需要准备：" (13px, #9CA3AF)
- Checklist (with subtle bullet dots):
  - "公司名称和所属行业"
  - "公司官网地址"
  - "主要产品/服务信息"
  - "核心优势和资质认证"

**No input bar at the bottom** for this page (it's a setup page, not a chat).

**Design constraints**: Clean, minimal, centered layout. White background. No gradients. Chinese text. System fonts.
```

---

## Page 4: 公司资料 · 已采集

```
Design a page for a Chinese B2B AI product. This is the "Company Profile" page showing collected company data.

**Layout**: Same fixed left sidebar (220px, #F7F7F8). Sidebar nav "公司资料" is highlighted. Main content area shows company profile data.

**Left Sidebar**: Same as before. Brand "你的AI外贸业务员", nav menu (新对话, 公司资料 highlighted, 邮箱配置), search, history.

**Main Content Area** (centered, max-width 640px, with a "← 返回对话" link at top-left in blue #2563EB, 14px):

Company header section:
- Large Building2 icon (32px, blue) inline with text
- Company name: "深圳光明光电科技有限公司" (20px bold, #1A1A2E)
- Subtitle line: "LED 照明 / 半导体照明" (14px, #6B7280)
- URL: "https://www.gm-light.com" (14px, blue #2563EB, underline)
- Gap

Card 1: "基本信息" (white bg, 1px #E5E7EB border, 12px rounded, padding 16px):
- Card header: "基本信息" (13px bold, #374151)
- Content: Key-value pairs in 2 columns:
  - "成立年份" → "2009年"
  - "员工规模" → "200-500人"
  - "认证资质" → "ISO 9001, CE, RoHS"
  - "合作模式" → "OEM / ODM"

Card 2: "主要产品" (same card style):
- Tags/chips layout: "LED工矿灯" "LED太阳能路灯" "LED面板灯" "LED防爆灯" (each as a small rounded chip, light blue #EFF6FF bg, blue #2563EB text, 6px rounded)

Card 3: "核心优势" (same card style):
- Bullet list:
  - "15年LED制造经验，产品远销80+国家"
  - "自有模具车间，支持OEM/ODM定制"
  - "通过ISO 9001认证，3年质保"

Card 4: "案例研究" (same card style):
- Header: "案例研究（12个）"
- Show 2 example cases in a compact list:
  - "尼日利亚太阳能路灯项目 — 500套 LED 太阳能路灯"
  - "沙特阿拉伯厂房照明 — 2000盏 LED 工矿灯"
- Link: "展开查看全部案例 →" (blue, 13px)

Footer area:
- "采集时间：2026-04-26" (12px, #9CA3AF)
- Two buttons: "重新采集" (outlined, gray border) and "导出画像" (filled blue), side by side

**No input bar at bottom.**

**Design constraints**: Clean data display. Cards with subtle borders. Chinese text. System fonts. Blue accent color.
```

---

## Page 5: 邮箱配置 · 未配置

```
Design a page for a Chinese B2B AI product. This is the "Email Settings" page shown when no email has been configured.

**Layout**: Same fixed left sidebar (220px, #F7F7F8). Sidebar nav "邮箱配置" is highlighted. Main content shows email setup form.

**Left Sidebar**: Brand "你的AI外贸业务员", nav (新对话, 公司资料, 邮箱配置 highlighted), search, history.

**Main Content Area** (centered, max-width 480px):

- Large Mail icon (48px, light gray #D1D5DB) centered
- Title: "邮箱配置" (20px bold, #1A1A2E)
- Description: "配置后即可通过 AI 批量发送开发信。" (14px, #6B7280)
- Gap (24px)

Form (two fields):

Field 1: "发件人名称" label (13px, #374151) above the input
- Subtitle hint: "客户收到邮件时看到的发件人名称" (12px, #9CA3AF)
- Input: full-width, 44px height, #EEEEEE background, 12px rounded, placeholder "如：张经理、Lisa from GMLight"

Field 2: "回复接收邮箱" label
- Subtitle hint: "客户回复邮件时发送到此地址" (12px, #9CA3AF)
- Input: same style, placeholder "如：zhang@gmail.com"

Gap (16px)
Primary button: "保存配置" (blue #2563EB, white text, full-width, 12px rounded, 44px height)

**No input bar at bottom.**

**Design constraints**: Simple, clean form. Minimal fields. Chinese text. System fonts. No dark mode.
```

---

## Page 6: 邮箱配置 · 已配置

```
Design a page for a Chinese B2B AI product. This is the "Email Settings" page showing saved email configuration.

**Layout**: Same fixed left sidebar (220px). Sidebar "邮箱配置" highlighted. Main content shows current email config.

**Left Sidebar**: Brand "你的AI外贸业务员", nav (新对话, 公司资料, 邮箱配置 highlighted), search, history.

**Main Content Area** (centered, max-width 480px):

Top-left: "← 返回对话" link (blue #2563EB, 14px)

Title: "✉️ 邮箱配置" (20px bold)

Card: "配置信息" (white bg, 1px #E5E7EB border, 12px rounded, padding 20px):
- Field: "发件人名称" (label 13px #374151)
- Value: "张经理" (14px #1A1A2E) — in a light gray read-only box or just plain text
- Gap

- Field: "回复接收邮箱" (label)
- Value: "zhang@gmail.com" — in read-only box
- Gap

- Field: "发件邮箱（系统自动生成）" (label)
- Value display: A special box showing "zhangmanager @mail.yourdomain.com"
  - The prefix part "zhangmanager" is editable (shown in an inline input with a subtle blue border)
  - The " @mail.yourdomain.com" part is plain gray text (not editable)
  - Below this: hint text "💡 域名由平台统一管理，您只需设定前缀。默认前缀取自您公司名，可自行修改。" (12px, #9CA3AF)

Gap (16px)
Button: "保存修改" (blue filled, full-width, 12px rounded, 44px height)

Bottom: "配置时间：2026-04-26" (12px, #9CA3AF, centered)

**No input bar at bottom.**

**Design constraints**: Clean config display. Editable prefix shown clearly. Chinese text. System fonts.
```

---

## Page 7: 对话 · Pipeline 时间线

```
Design a modern AI chat application showing a Pipeline progress timeline within a conversation. This is for a Chinese B2B foreign trade product "你的AI外贸业务员".

**Layout**: Same left sidebar (220px) + right chat area. The chat shows a running pipeline task.

**Left Sidebar**: Standard sidebar (brand, nav, search, history).

**Main Chat Area** (scrollable):
Show these messages:

1. User message (right, gray bg): "帮我找30个美国的太阳能板分销商"
2. AI message (left): "好的，我来帮您搜索美国的太阳能板分销商，请稍等..." + timestamp "3分钟前"

3. A Pipeline Timeline component (left-aligned, max-width 560px, white bg, 1px #E5E7EB border, 12px rounded, padding 16px):
   - Title: "客户搜索" with a spinning/loader icon (blue), 14px bold
   - 4 steps vertically listed:

   Step 1 (completed): ✅ green check icon. "搜索目标公司" — "找到 90 个候选" (13px gray)
   Step 2 (in progress): 🔵 blue spinning icon. "爬取网站内容" — "正在爬取 (12/90)" + a thin progress bar below showing ~13% fill in blue #2563EB on light blue #EFF6FF track. Small text "预计 3 分钟" (12px #9CA3AF)
   Step 3 (pending): ⚪ gray circle icon. "AI 筛选与排名" (gray text)
   Step 4 (pending): ⚪ gray circle icon. "输出结果" (gray text)

   Each step has: icon (20px) + step name (14px) on the left, status text (13px gray) on the right, connected by a thin vertical gray line between steps.

4. (No more messages — conversation is "live" with the pipeline running)

**Bottom**: Input bar (same as always).

**Design constraints**: The timeline should feel alive and modern. Use subtle animations implied by the spinning icon and progress bar. Blue accent for active step. Green for completed. Gray for pending. Chinese text. Clean minimal style.
```

---

## Page 8: 表格弹窗 · 客户线索

```
Design a full-screen modal/overlay showing a data table of customer leads. This is for a Chinese B2B foreign trade product. The modal appears on top of the chat interface.

**Background**: Slightly dimmed (rgba overlay) with the chat interface barely visible behind.

**Modal** (full-screen height minus some padding, white background, 16px rounded corners, with a top header bar):

Header bar (horizontal, padding 16px 24px, border-bottom 1px #E5E7EB):
- Left: Title "客户线索" (18px bold) + count badge "共 30 条" (13px, #6B7280, in a light gray pill)
- Right: Close button (X icon, 20px, gray) and "下载 Excel" button (blue outlined, with Download icon)

Toolbar row (below header, padding 12px 24px):
- Left: A search input (300px wide, #EEEEEE bg, 8px rounded, Search icon, placeholder "搜索公司名、国家、行业...")
- Right: Filter dropdowns side by side:
  - "国家" dropdown button (showing "全部", with ChevronDown icon, 8px rounded)
  - "行业" dropdown button (showing "全部")
  - "匹配度" dropdown button (showing "全部")
  - Sort toggle: "匹配度 ↓" (blue text, indicating sorted descending)

Table area (scrollable, fixed header):
- Table header (sticky top, white bg, 13px bold #374151, light gray bottom border):
  Columns: ☐ (checkbox) | 公司名称 | 网站 | 国家 | 行业 | 匹配度 | 联系人 | 邮箱 | 操作
- Table body (14px, alternating white/#FAFAFA row backgrounds):
  Row 1: ☐ | "ABC Solar Corp" (blue link) | "abcsolar.com" (gray) | 🇺🇸 美国 | 太阳能 | "92.5" (green badge) | "John Smith" | "john@abcsolar.com" | "查看" link
  Row 2: ☐ | "SunPower Distributors" | "sunpower-dist.com" | 🇺🇸 美国 | 太阳能 | "88.3" (green badge) | "Mike Johnson" | "mike@sun..." | "查看"
  Row 3: ☐ | "Green Energy USA" | "greenenergyusa.com" | 🇺🇸 美国 | 太阳能 | "85.1" (green badge) | "Sarah Lee" | "sarah@gre..." | "查看"
  (show 8-10 rows total with realistic data)

Match score column: numbers ≥ 80 shown as green text, ≥ 60 yellow, < 60 red.

Pagination bar (bottom of table, padding 12px 24px):
- Left: "显示 1-20 条，共 30 条" (13px gray)
- Right: Page buttons: "上一页" (gray), "1" (blue filled circle), "2" (gray outlined circle), "下一页" (gray)

**Design constraints**: Professional data table look. Fixed header with scrollable body. Clean borders. Chinese labels, English company data. System fonts. Blue accent for actions and active states. Compact but readable row heights (44-48px).
```
