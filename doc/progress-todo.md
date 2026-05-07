# AI 外贸业务员 — Progress & TODO

## 当前状态总览（2026-05-07）

### 已完成

- 4 条主 pipeline 已接通：`customer-acquisition`、`company-profile`、`email-craft`、`email-blast`。
- 客户名单页已成为开发信撰写和批量发送的主操作台：支持搜索、筛选、分页、排序、批量选择、批量生成开发信、单条重写、复制、手动编辑、删除客户、导出。
- `email-craft` 已闭环：支持 DB 客户、上传客户文件、聊天手动输入客户、按选中客户范围生成，结果写入 `outreach_emails`，并支持查看/导出/编辑。
- `email-blast` 已完全闭环：客户名单选择客户 → 发送确认弹窗 → `confirmType=”email_blast”` → SSE/timeline → Resend 真实批量发送 → `sending/sent/failed` 状态回写 → Resend webhook 回写 `delivered/bounced/failed/complained`。
- `email-blast` 已移除 dry-run 模式：所有发送均为真实 Resend 发送，前后端所有 dry_run 相关代码已剔除（schema 默认值改为 False，pipeline 中 dry_run 分支已移除，前端发送确认弹窗去掉 dry-run 复选框和提示文字）。
- `email-blast` 发送完成卡片已简化：只保留一个”前往客户名单”按钮（action type: `go-customer-list`），去掉”查看状态”按钮；按钮点击后正确跳转到客户名单页面（`onGoToCustomerList` prop 已补全到 ChatArea）。
- `email-blast` 预检查步骤消息已简化：Resend 域名校验等技术细节不再暴露给用户，只显示”配置检查通过”。
- Pipeline 时间轴步骤排版已修复：步骤名称和消息从同行排列改为上下两行，消息加 `break-words` 自动换行，不再溢出卡片。
- 邮箱配置页已精简：去掉所有冗余描述备注（”客户收到邮件时看到的发件人名称”等），保留纯标签+输入框；新增发件人实时预览（名称和邮箱前缀随输入实时更新）；回复接收邮箱去掉”（可选）”标签和”可留空”placeholder，改为”客户的回复会回传到填写的邮箱地址”。
- LLM 意图识别已强化 email_craft/email_blast 区分：prompt 中明确”发邮件”→ email_blast、”写开发信”→ email_craft 的区分规则；regex fallback 中 `_looks_like_email_blast` 优先于 `_looks_like_email_craft` 检查。
- `email-blast` 已对齐 `waimao_toolkit_new/skills/email-blast/` 的关键策略：默认 `send_mode=”auto”`，按客户国家/地区推算当地工作时间，非工作日或非 09:00-17:00 跳过，不改写该邮件状态。
- `email-blast` 发送前预检已补齐：检查 `RESEND_API_KEY`、发件人名称、发件邮箱前缀、邮箱配置确认状态、`MAIL_DOMAIN`，并尝试通过 Resend API 校验 key 和发件域名；回复接收邮箱为可选项。
- Resend webhook 已接入：`POST /api/emails/resend/webhook`，使用 Svix 签名校验，按 `resend_message_id` 回写 `delivered/bounced/failed/complained`。
- 客户名单状态已细化但筛选保持简洁：后端 `/api/leads` 不再把 `delivered/bounced/complained` 合并成 sent/failed；前端行内 badge 保留真实状态，顶部筛选只保留”全部/未写/已写/已发送/失败”。
- 聊天入口已支持 email-blast 意图：如”发邮件”、”把写好的开发信发出去”会识别为批量发送；没有明确发送范围时，引导用户前往客户名单选择。
- 邮箱配置缺失时已支持对话式收集：依次询问发件人名称、发件邮箱前缀，保存到 `user_settings`，完成后不会继续拦截下一句话；回复接收邮箱可在配置页留空或后续修改。
- 公司画像完成后会自动生成一套基础邮箱配置推荐：发件人名称从公司名提取（如 PRANCE），发件邮箱默认 `sales@clientconnet.com`，回复接收邮箱默认留空；当前画像变化时会刷新推荐，用户首次发送前必须进入邮箱配置页确认/保存。
- 邮箱配置已区分”系统推荐态”和”用户确认态”：`user_settings.confirmed_at` 为空表示尚未确认；邮箱配置页保存或对话式配置完成后写入确认时间。客户名单首次点击发送会引导到邮箱配置页确认，确认弹窗会展示发件人、发件邮箱、回复邮箱并提供修改入口。
- 2026-05-06 端到端联调通过（详见下方记录）。
- 2026-05-06 Resend 真实发送验证通过：通过 email-blast pipeline 真实调用 Resend API 发送邮件到 panlingy3@gmail.com。
- 2026-05-06 Resend webhook 验证通过：delivered/bounced 事件正确更新 outreach_emails 状态。
- 2026-05-06 DMARC DNS 记录已配置：`_dmarc.clientconnet.com` → `v=DMARC1; p=none; rua=mailto:dmarc@clientconnet.com`，SPF/DKIM/DMARC 三套齐全。
- 2026-05-06 国家/时区映射扩展：用 `zoneinfo` + `tzdata` 替换固定 UTC 偏移表，覆盖 70+ 个国家/地区，自动处理夏令时。
- 2026-05-06 `prefix_generator` pypinyin 中文支持：中文公司名自动转拼音生成邮箱前缀。
- 2026-05-06 失败邮件快速筛选+批量重发：切到"失败"筛选自动全选，红色警示文字提示重发。
- 2026-05-07 部署前 Resend webhook 配置已更新：Resend 控制台 endpoint 使用 `https://api.clientconnet.com/api/emails/resend/webhook`，根 `.env` 已换为真实 webhook signing secret（不要写入文档或提交）。
- 2026-05-07 Better Auth 注册/登录闭环已完成：Next.js 暴露 `/api/auth/[...all]`，前端登录/注册/退出可用，FastAPI 读取 Better Auth session cookie 并映射到本项目 `users.id`，`CurrentUser=1` stub 已移除。
- 2026-05-07 部署准备已完成：`scraper.py` Chromium 路径改为跨平台（Windows/Linux），PM2 `ecosystem.config.cjs` 已创建，完整部署指南 `doc/deploy.md` 已输出（含腾讯云环境搭建、后端部署、Nginx 反代+SSL、DNS、Vercel 前端、Resend webhook、验证清单）。

### 后续 TODO

1. **按 `doc/deploy.md` 分步执行部署**：腾讯云服务器搭建 → 后端部署 → Nginx+SSL → DNS → Vercel → Resend webhook。
2. 部署后回归验证：Resend webhook endpoint、Better Auth 登录态跨域 cookie、后端 `CORS_ORIGINS`（加入前端 Vercel/正式域名）、批量发送小样本。
3. 数据库索引优化与 seed 脚本多用户适配。

---

更新时间：2026-05-07（部署准备完成）

---

## 已完成 Pipeline（代码已稳定，后续开发其他功能时不要修改这些 pipeline 的代码）

### 1. 客户搜索 (customer-acquisition) Pipeline ✓

**功能**：用户通过自然语言描述目标客户（行业、国家、关键词），系统自动搜索、爬取、AI 分析、筛选排序，结果存入数据库。

**后端关键文件**：
- `backend/app/services/pipeline_service.py` — 核心编排
- `backend/app/services/intent_router.py` — LLM 意图识别（Replicate GPT），正则 fallback
- `backend/app/services/chat_service.py` — SSE 流式推送
- `backend/app/services/task_manager.py` — 任务生命周期管理

**前端关键文件**：
- `frontend/app/page.tsx` — 主页面状态管理、SSE 处理
- `frontend/components/chat-area.tsx` — 聊天区域
- `frontend/components/chat-input.tsx` — 输入框（含文件上传）
- `frontend/components/message-bubble.tsx` — 消息气泡
- `frontend/components/callout-card.tsx` — 结果卡片（通用：支持 view-list / download-excel / download-emails / view-emails / view-profile / go-settings 6 种 action）
- `frontend/components/leads-table-modal.tsx` — 线索列表弹窗（支持 leads / emails 两种模式）
- `frontend/lib/api.ts` — API client + SSE 解析 + 重连

**完成内容**：
- [x] Serper API 搜索 → Playwright 爬取 → Replicate AI 分析 → 筛选排序 → 存 DB
- [x] SSE 流式推送任务进度（thinking → pipeline_started → step_update × N → result → done）
- [x] 任务生命周期管理（heartbeat / cancel / stale cleanup）
- [x] 前端 SSE 自动重连（刷新页面后恢复运行中任务）
- [x] 线索列表弹窗 + Excel 导出
- [x] 参数确认卡片（用户确认搜索参数后启动）
- [x] 配置缺失检测（缺 API key 时提示前往设置）

### 2. 公司画像 (company-profile) Pipeline ✓

**功能**：用户提供官网 URL 或文字资料，系统爬取官网、AI 整理结构化画像（产品、优势、案例、资质、合作模式等），存入数据库。

**后端关键文件**：
- `backend/app/services/profile_pipeline_service.py` — 画像采集编排
- `backend/app/services/profile_service.py` — 画像 CRUD
- `waimao_toolkit_new/skills/company-profile/scripts/scrape_website.py` — Playwright 爬虫

**前端关键文件**：
- `frontend/components/company-profile.tsx` — 公司画像展示页
- `frontend/components/welcome-screen.tsx` — 欢迎页（含功能卡片入口）

**完成内容**：
- [x] Playwright 多页面爬取（自动提取 email/phone/LinkedIn）
- [x] 多语言重复页面过滤 + 文本压缩
- [x] Replicate AI 结构化画像生成（prompt 经过多次调优）
- [x] AI 超时兜底（超时保存基础草稿，不丢数据）
- [x] 增量更新模式（补充资料时基于已有画像 merge，而非覆盖）
- [x] 前端画像展示页（产品/竞争力/案例/资质/合作模式/卖点/信息边界）
- [x] 画像展示页列表截断区域添加"展开全部/收起"按钮
- [x] "补充资料"按钮 → 新建 company-profile 会话 + 引导提示
- [x] "重新采集"按钮 → 明确告知 AI 是 replace 模式
- [x] 前端图片上传（base64 resize → 后端 vision 模型解析）
- [x] 画像导出 Word 文档
- [x] 保存阶段按 profile_mode 分流（create/update/replace）

### 3. 开发信撰写 (email-craft) Pipeline ✓

**功能**：加载公司画像 + 客户线索（DB 已有 + 用户上传文件）→ 批量调用 LLM → 为每条线索生成个性化开发信 → 保存到 DB → 查看邮件列表 / 导出 Excel。高度遵循 `waimao_toolkit_new/skills/email-craft/` 的 prompt 模板和逻辑。

**后端关键文件**：
- `backend/app/services/email_craft_pipeline_service.py` — 核心编排：4 步流水线 + prompt 模板 + AI 调用（3 次重试 + 1s 间隔）+ heartbeat 保活
- `backend/app/utils/file_parser.py` — Excel/CSV/Word 解析 → 标准化 lead dict + LLM 智能列名匹配
- `backend/app/services/email_service.py` — `export_emails_xlsx()` 通过 outreach_emails 表反向查 leads（14 列导出）
- `backend/app/services/lead_service.py` — `get_leads_with_emails()` 查询带邮件内容的线索
- `backend/app/schemas/lead.py` — `LeadEmailResponse` schema（含 email_subject / email_body）
- `backend/app/routers/leads.py` — `GET /api/leads/{task_id}/emails` 端点
- `backend/app/routers/emails.py` — `GET /api/emails/{task_id}/export` 导出端点 + `PATCH /api/emails/leads/{lead_id}` 手动编辑开发信端点

**前端关键文件**：
- `frontend/components/email-craft-confirm-card.tsx` — 确认卡片（N 条线索 + 语言选择 + 上传/直接开始）
- `frontend/components/callout-card.tsx` — 新增 `view-emails` action，传递 taskId
- `frontend/components/leads-table-modal.tsx` — 新增 emails 模式（显示邮件主题+正文列，下载按钮调用 emails 导出接口）
- `frontend/components/customer-list.tsx` — 客户名单主页面 + 详情抽屉（批量生成/重写/复制/删除/联系人邮箱备注编辑/邮件主题正文编辑）
- `frontend/components/message-bubble.tsx` — confirmParams 渲染分支 + onViewEmails 传递
- `frontend/components/chat-area.tsx` / `message-list.tsx` — onViewEmails prop 链路
- `frontend/lib/api.ts` — `exportEmailsExcel()` + `getLeadsWithEmails()` + `updateLeadEmail()` + `LeadWithEmail` 类型

**用户交互流程与 Callout 卡片引导**：

```
Flow A: 有画像 + 有 DB 线索（常规路径）
  用户: "帮我写开发信"
  → AI 检查: 公司画像 ✓, 线索 16 条
  → 返回 confirm 卡片:
    "您有 16 条客户线索，可以直接生成开发信。也可以上传客户资料补充线索。"
    语言选择: ○ 英文  ● 中文
    [上传客户资料并开始] (outlined)    [直接开始生成] (filled)
  → 用户点 [直接开始生成]
  → Pipeline 4 步执行（timeline 实时更新进度）
  → Callout 卡片:
    📝 开发信生成完成
    成功生成 16 封开发信
    [查看邮件] (outlined)    [导出 Excel] (filled)
  → 点 [查看邮件]: 弹出 LeadsTableModal（emails 模式），显示公司名/国家/行业/联系人/匹配度/邮件主题/邮件正文
  → 点 [导出 Excel]: 下载 14 列 Excel（12 线索列 + Email Subject + Email Body）

Flow B: 有画像 + 有线索 + 上传文件
  用户在 confirm 卡片点 [上传客户资料并开始]
  → 弹出文件选择器（支持 .xlsx/.csv/.docx）
  → Pipeline: 解析文件（智能列名匹配）→ 合并线索（DB+上传，按公司名去重）→ 逐条生成
  → Callout: "成功生成 20 封开发信，含 4 条上传线索"

Flow C: 无公司画像
  用户: "帮我写开发信"
  → AI: "请先通过公司画像功能建立公司资料"（callout 卡片 + [前往公司画像] 按钮）

Flow D: 无线索
  用户: "帮我写开发信"（有画像但无线索）
  → AI: "请先搜索客户或上传客户资料"（callout 卡片）
```

**Pipeline 四步**：
```
Step 1: 加载公司画像 — 从 DB 读取 profile_data (JSON)
Step 2: 加载线索数据 — DB leads + 解析上传文件 + 按公司名去重合并
Step 3: 生成开发信   — 逐条调用 Replicate, 进度 [i+1]/N, 带 heartbeat
Step 4: 保存结果     — outreach_emails 表 + result_summary 统计
```

**导出 Excel 14 列**：
Company Name / Website / Country / Industry / Company Role / Contact Name / Email / Phone / Match Score / AI Summary / Business Match / Outreach Suggestion / Email Subject / Email Body

**Prompt 模板**（从 toolkit 原样移植）：
- `_BASE_SYSTEM_PROMPT`: 7 条严格规则（自然开头、匹配理由、相关案例、专业语气、轻量 CTA、禁止编造、长度控制）
- `build_system_prompt(language)`: 语言要求（cn/en）
- `build_user_prompt(customer, profile, cases)`: 客户信息 + 我司信息
- `select_relevant_cases()`: 智能案例选择（国家+100, 行业+50, 客户类型+30）
- `build_profile_section()`: 结构化我司信息（产品/竞争力/案例/卖点/资质/合作模式/客户匹配指南）
- 输出格式: `{"email_subject": "...", "email_body": "..."}` (纯文本)

**文件解析**（`file_parser.py`）：
- Excel (.xlsx/.xls): openpyxl
- CSV: csv 模块（多编码尝试：utf-8-sig / utf-8 / gbk / gb2312 / latin-1）
- Word (.docx): python-docx
- 静态列名映射（中文名/英文名 → Lead 字段，覆盖常见变体）
- LLM 智能列名匹配：静态匹配率 < 50% 时，调 Replicate 自动识别非标准列名（仅补充不覆盖）

**导出查询逻辑**：
- `export_emails_xlsx` 通过 `outreach_emails` 表反向查 `leads`（不是按 `Lead.task_id`），确保 DB 原始线索（属于 customer-acquisition 任务）和上传线索都能被找到

**测试通过**：
- [x] 常规生成（直接开始）：DB 16 条线索 → 16 封开发信 → Excel 14 列验证
- [x] 上传文件生成：Excel 列名解析 → 去重合并 → 生成 + 导出
- [x] 查看邮件弹窗：emails 模式显示公司信息 + 邮件主题/正文，弹窗内下载按钮导出正确 Excel
- [x] Callout 导出 Excel：直接从卡片导出 14 列 Excel
- [x] 客户名单范围生成：支持选中 leadIds、按语言生成，不再默认全量读取 leads
- [x] 上传客户资料：上传后创建独立 import task/list，解析保存 leads 后进入 email-craft
- [x] 手动输入客户：自然语言抽取客户字段，保存为 manual task 下的 lead，再生成开发信
- [x] 详情抽屉重写开发信：单个客户可重新生成，未发送草稿覆盖，已发送邮件保留历史并新建 draft
- [x] 详情抽屉手动编辑：支持修改联系人、邮箱、来源备注、邮件主题、开发信正文
- [x] 复制邮件：详情抽屉内复制邮件主题 + 正文
- [x] 客户删除：删除 lead 时同步删除对应 outreach_emails
- [x] email-craft 全流程完成：常规生成、上传生成、手动输入生成、范围选择、查看/导出、复制、重写、手动编辑均已闭环
- [x] 前端 TypeScript 编译无错误
- [x] 后端 Python 语法检查通过

---

## TODO：剩余 Pipeline

### 4. 批量发送 (email-blast) Pipeline — 已接通，继续完善

**目标**：通过 Resend API 批量发送开发信，实时跟踪发送状态。

**参考**：
- PRD §3.4
- `waimao_toolkit_new/skills/email-blast/` — 已有 toolkit 实现（Resend API）

**TODO**：
- [x] 后端 `email_blast_pipeline_service.py`：从 DB 筛选待发送记录
- [x] 意图路由：识别"发邮件"意图，提取发送范围和发送参数
- [x] 邮箱未配置时 AI 直接收集信息（不启动 pipeline）
- [x] Resend API 集成：批量发送 + 状态回写 + webhook 回调
- [x] 状态回写：发送成功/失败/送达/退回/投诉收录到 DB
- [x] 前端：发送进度展示（已发送/总数、成功/失败统计）
- [x] 前端：发送结果 callout 卡片（[查看状态]）
- [x] 前端：发送设置（发送策略、每日上限、每封间隔、dry-run）

### email-blast 开发计划（2026-05-03）

**开发边界**：
- 不修改 `backend/app/services/pipeline_service.py`，避免影响已稳定的 customer-acquisition pipeline。
- 继续复用 `tasks` 作为来源 List，不新增 `lead_lists`。
- 继续复用 `outreach_emails` 作为开发信与发送状态主表；发送状态先落在最新一封开发信记录上。
- MVP 发送入口优先从「客户名单」选中客户发起，聊天意图入口作为补充。
- 发送逻辑参考 `waimao_toolkit_new/skills/email-blast/scripts/`，但从飞书/CSV 状态回写改为 PostgreSQL `outreach_emails` 状态回写。

**状态模型建议**：
- 当前已有字段：`send_status`、`sent_at`、`error_message`。
- MVP 状态枚举：`draft` / `pending` / `sending` / `sent` / `failed`。
- Webhook 增强后扩展：`delivered` / `bounced` / `complained`。
- 已补充字段：
  - `resend_message_id`：Resend 返回的邮件 ID，用于 webhook 反查。
  - `last_send_attempt_at`：最近一次发送尝试时间。
  - `last_event`：最近一次 webhook 事件类型。

**Phase 1：后端 MVP 闭环**：
- [x] 新建 `backend/app/services/email_blast_pipeline_service.py`。
- [x] Step 1 预检查：检查 `RESEND_API_KEY`、`user_settings.sender_name`、`from_email_prefix`、`MAIL_DOMAIN`；`reply_to_email` 可选。
- [x] Step 2 读取待发送：仅读取当前用户可访问的 leads 下最新 `outreach_emails`，筛选有邮箱、有主题、有正文、未发送或失败可重发的记录。
- [x] Step 3 发送预览/统计：统计待发送、已发送跳过、缺邮箱、缺主题/正文、失败可重试数量。
- [x] Step 4 执行发送：逐封调用 Resend API，支持 `delay_min`、`delay_max`、`daily_limit`、`dry_run`、`send_mode`。
- [x] Step 5 状态回写：每封发送前写 `sending`，成功写 `sent + sent_at + resend_message_id`，失败写 `failed + error_message`。
- [x] `backend/app/services/email_service.py`：把 `send_emails_stub()` 改为正式任务入口，或删除 stub 并迁移调用方。
- [x] `backend/app/routers/emails.py`：`POST /api/emails/send` 接入真实发送任务。
- [x] `backend/app/services/chat_service.py`：新增 `start_email_blast_pipeline()`，复用 Task + SSE 编排。
- [x] `backend/app/routers/tasks.py`：支持 `confirm_type="email_blast"`。
- [x] `backend/app/schemas/chat.py` / `backend/app/schemas/email.py`：补充 email-blast 参数 schema。

**Phase 2：Resend 发送细节**：
- [x] 用 `httpx` 调 `POST https://api.resend.com/emails`，依赖后端 `pyproject.toml` 已有 `httpx`。
- [x] 发件人拼装：`{sender_name} <{from_email_prefix}@{MAIL_DOMAIN}>`。
- [x] `reply_to` 使用用户设置的 `reply_to_email`；为空时可不传。
- [x] 正文优先按纯文本发送，必要时复用 toolkit 的 `strip_markdown()`。
- [x] 使用幂等键避免重复发送，建议 `outreach-email-{email_id}-{task_id}`。
- [x] 网络错误重试 1 次；API 限流、域名未验证、参数错误写入分类后的错误信息。
- [x] `dry_run=true` 时不调用 Resend，但完整跑 timeline 和结果统计。

**Phase 3：状态回调 / webhook 增强**：
- [x] 新增环境变量 `RESEND_WEBHOOK_SECRET`。
- [x] 新增 `POST /api/emails/resend/webhook`。
- [x] 使用 Svix 签名校验 webhook 请求。
- [x] 用 webhook payload 中的 Resend email id 匹配 `outreach_emails.resend_message_id`。
- [x] 处理事件：`email.sent`、`email.delivered`、`email.bounced`、`email.failed`、`email.complained`。
- [x] webhook 更新必须幂等，重复事件不会创建新记录，只覆盖同一封邮件的最新状态。
- [x] 本地已新增 Alembic 迁移 `7f2c3d4e5a6b_add_resend_tracking_to_outreach_emails.py` 并执行 `python -m alembic upgrade head`。

**Phase 4：意图路由与聊天入口**：
- [x] `intent_router.py` LLM prompt 中补充 email_blast 参数：`lead_ids`、`source_task_id`、`delay_min`、`delay_max`、`daily_limit`、`dry_run`、`send_mode`。
- [x] Regex fallback 增加触发词：`发邮件`、`发送开发信`、`批量发送`、`群发`、`email blast`、`send emails`、`batch send`。
- [x] 当用户没有明确范围时，不直接全量发送；返回 callout 卡片，引导去「客户名单」选择。
- [x] 邮箱未配置时，AI 在对话中收集「发件人名称 + 发件邮箱前缀」，保存到 `user_settings` 后继续之前的发送请求；回复邮箱可跳过。
- [x] 同一会话中邮箱配置只追问一次，不重复打断。

**Phase 5：前端 MVP 交互**：
- [x] `frontend/components/customer-list.tsx` 增加「发送邮件」按钮。
- [x] 只有选中客户里存在 `emailStatus in ("draft", "failed")` 且有邮箱时，发送按钮可用。
- [x] 选中栏增加发送前摘要：`选中 N 个 / 可发送 M 个 / 已发送跳过 X 个 / 缺邮箱 Y 个`。
- [x] 增加发送设置确认弹窗：发送策略、每日上限、每封间隔、dry-run。
- [x] 点击确认后创建 email-blast 会话，跳转聊天页，启动 `startConfirmedPipeline({ confirmType: "email_blast", leadIds, ...sendSettings })`。
- [x] timeline 显示「邮件发送」，步骤为：预检查 / 读取待发送 / 发送邮件 / 状态回写。
- [x] 完成 callout：展示成功、失败、跳过统计，按钮为 `[查看状态]`、`[返回客户名单]`。
- [x] 客户名单刷新后显示发送状态，顶部筛选保持：全部 / 未写 / 已写 / 已发送 / 失败；发送中/已送达/退信/投诉只作为行内真实状态展示。

**前端交互待讨论稿**：

**交互结论（当前建议）**：
- MVP 主入口放在「客户名单」页，用户必须显式勾选要发送的客户，不做默认全量发送。
- 点击「发送邮件」后使用居中确认弹窗，而不是右侧抽屉；这是一个短决策动作，确认范围和发送策略即可。
- 确认弹窗里展示本次真实会发送的数量，并清楚列出跳过原因，避免误发。
- 自然语言聊天入口只负责理解“我要发邮件”的意图；若没有明确发送范围，AI 引导用户前往客户名单选择，不直接启动发送。
- 单个客户详情抽屉保留「发送这封」入口，用于测试、小批量手动发送和补发。

入口 A：客户名单页（推荐 MVP 主入口）
```
用户进入「客户名单」
  → 勾选要发送的客户
  → 顶部批量操作区显示：
    已选 N 个｜可发送 M 个｜已发送 X 个将跳过｜缺邮箱 Y 个｜缺开发信 Z 个
  → 点击「发送邮件」
  → 打开发送确认弹窗：
    - 收件范围：M 个可发送客户
    - 发件人：sender_name <prefix@domain>
    - 回复邮箱：reply_to_email（可选）
    - 发送策略：按客户当地工作时间 / 立即发送
    - 发送限制：每日上限 / 每封间隔 / dry-run
    - 风险提示：已发送客户不会重复发送
  → 点击「确认发送」
  → 跳转聊天页 + email-blast timeline 实时跑
  → 完成后 callout：
    批量发送完成：成功 S 封，失败 F 封，跳过 K 封
    [查看状态] [返回客户名单]
```

入口 B：聊天自然语言入口
```
用户说：「把写好的开发信发出去」
  → 若没有明确范围：
    AI 回复：请先到客户名单选择要发送的客户
    callout: [前往客户名单]
  → 若用户说「发送刚才选中的/这 10 个」但没有上下文：
    不猜测范围，仍引导选择
  → 若后续已有上下文记忆支持 lead_ids：
    显示发送确认卡片，不直接启动发送
```

入口 C：单个客户详情抽屉
```
客户名单 → 打开某个客户详情
  → 若该客户已有开发信 draft 且有邮箱：
    显示「发送这封」按钮
  → 点击后走同一个发送确认弹窗，但范围为 1 个客户
```

**发送确认弹窗内容**：
- 标题：`确认发送开发信`
- 摘要：`本次将发送 M 封开发信`
- 统计区：
  - `可发送 M`
  - `已发送跳过 X`
  - `缺邮箱 Y`
  - `缺开发信 Z`
  - `失败可重发 R`
- 发件信息：
  - 发件人名称
  - 发件邮箱
  - 回复邮箱（可选）
- 发送设置：
  - 发送策略：默认按客户当地工作时间，可切换立即发送
  - 每日上限：默认 50
  - 每封间隔：默认 60-120 秒
  - dry-run：默认关闭，开发/测试阶段可开启
- 操作按钮：
  - `取消`
  - `确认发送`

**客户名单页按钮状态**：
- 未选择客户：`发送邮件` 禁用。
- 选中客户中没有任何可发送项：按钮禁用，并提示「选中的客户暂无可发送开发信」。
- 选中客户中至少有 1 个 `draft` 或 `failed` 且有邮箱：按钮可用。
- 有不可发送项时不阻断整个发送任务，但在确认弹窗中列出跳过数量。

**发送完成后的前端行为**：
- timeline 自动完成，显示发送结果 callout。
- callout 主按钮：`查看状态`，返回客户名单并刷新列表。
- callout 次按钮：`返回客户名单`。
- 客户名单刷新后，状态列展示最新 `sent/failed/sending` 等状态。
- 如果存在失败邮件，顶部可显示「失败 F 封，可选择后重发」。

**选择名单规则**：
- 默认只能发送用户显式选中的客户，不允许默认全量发送。
- `emailStatus="draft"`：可发送。
- `emailStatus="failed"`：可重发，但确认弹层中单独统计。
- `emailStatus="sent"` / `delivered` / `bounced`：默认跳过；如需重发，后续单独增加「包含已发送」高级开关。
- `emailStatus="unwritten"`：不可发送，引导先生成开发信。
- `lead.email` 为空：不可发送，引导补充邮箱。
- 最新一封开发信如果已 `sent`，重新生成/编辑会新建 draft；发送时只发送最新 draft。

**验收标准**：
- [x] dry-run 不调用 Resend，但 timeline、统计、callout 完整可用。（2026-05-06 验证通过）
- [x] 实发 1-2 封测试邮件后，DB 状态从 `draft → sending → sent`。（2026-05-06 验证通过，Resend ID: `3c86d98b-...`）
- [x] 失败时写入 `failed + error_message`，下次可重新发送。
- [x] 客户名单刷新后能看到发送状态变化。
- [x] 前端 TypeScript 编译通过。
- [x] 后端 Python 语法检查通过。

**建议实现顺序**：
1. 后端读取待发送 + dry-run pipeline。
2. 客户名单「发送邮件」按钮 + 确认弹层 + timeline。
3. 接入 Resend 实发 + 状态回写。
4. 失败重试、每日上限、间隔策略完善。
5. 邮箱未配置时的对话式收集配置：发件人名称、发件邮箱前缀，保存到 `user_settings` 后继续发送请求；回复邮箱可在邮箱配置页留空或后续补充。

---

## TODO：LLM 意图识别升级

当前 `intent_router.py` 已接入 LLM (Replicate GPT-5.2) 做意图识别，正则作为 fallback。

**TODO**：
- [x] 意图路由后处理完善（email_blast 参数提取等）
- [x] 对话历史持久化（新增 `conversations` + `conversation_messages` 表）
- [x] 上下文记忆：后续消息能引用之前对话

---

## TODO：数据库 & 迁移

当前使用 Alembic + async SQLAlchemy，但模型和迁移可能需要补全。

**TODO**：
- [x] 检查 Alembic 迁移是否与当前模型完全同步（2026-05-06 验证通过）
- [x] `conversations` + `conversation_messages` 表（对话历史持久化，2026-04-30 完成）
- [ ] 数据库索引优化（leads 按公司名/邮箱查询等高频场景）

---

## TODO：登录注册

使用 Better Auth 实现邮箱注册/登录 + session cookie。Next.js 负责注册/登录与 session cookie，FastAPI 通过同一套数据库里的 Better Auth session 表校验 cookie，再映射到本项目整数 `users.id`。

**参考**：PRD §2.6

**TODO**：
- [x] Better Auth Next.js 集成（`/api/auth/[...all]` 注册/登录/Session 管理）
- [x] `get_current_user`/`CurrentUser` 从 `user_id=1` stub 改为真实 Better Auth session cookie 验证
- [x] 前端登录/注册页面
- [x] 前端 Auth 状态管理（未登录显示登录/注册，登录后进入工作台，退出后清空状态）
- [x] 多用户数据隔离（业务 API 继续使用 `CurrentUser`，现在映射到真实登录用户 `users.id`）
- [ ] Seed 脚本适配多用户

---

## TODO：部署上线

**完整部署指南**：`doc/deploy.md`（分步可复制粘贴执行）

**已完成的部署准备**：
- [x] `backend/app/utils/scraper.py` Chromium 路径跨平台支持（Windows `AppData/Local` + Linux `.cache`）
- [x] `backend/ecosystem.config.cjs` PM2 进程管理配置
- [x] `doc/deploy.md` 完整部署教程（腾讯云环境 + 后端 + Nginx + SSL + DNS + Vercel + Webhook + 验证清单 + 运维命令）

**前端（Vercel）**：
- [ ] Vercel 项目配置（连接 GitHub 仓库，Root Directory: `frontend`）
- [ ] 环境变量配置：`NEXT_PUBLIC_API_URL=https://api.clientconnet.com`、`BETTER_AUTH_URL=https://clientconnet.com`、`BETTER_AUTH_SECRET`、`BETTER_AUTH_COOKIE_DOMAIN=.clientconnet.com`、`BETTER_AUTH_DATABASE_URL`
- [ ] 域名绑定 `clientconnet.com` + `www.clientconnet.com`

**后端（腾讯云 Nginx + PM2）**：
- [ ] 腾讯云服务器环境搭建（详见 deploy.md Phase 1-7）
- [ ] PostgreSQL 17 安装 + 远程访问配置（pg_hba.conf 允许 Vercel IP）
- [ ] Python 3.13 + Node.js 20 + Playwright Chromium
- [ ] Nginx 反向代理 + SSL 证书（SSE `proxy_buffering off` + 300s 超时）
- [ ] PM2 启动后端 + 开机自启
- [ ] 生产 `.env` 配置：真实 API keys + `BETTER_AUTH_SECRET`（与前端一致）+ `CORS_ORIGINS=https://clientconnet.com,https://www.clientconnet.com`
- [ ] DNS A/CNAME 记录 + Resend SPF/DKIM/DMARC
- [ ] 数据库迁移 `alembic upgrade head`
- [ ] Resend webhook URL 确认为 `https://api.clientconnet.com/api/emails/resend/webhook`

---

## 运行状态

- 前端：`http://localhost:3000`
- 后端：默认 `http://localhost:8002`；当前本机 `8002` 有旧 uvicorn 残留时，Better Auth 联调用干净端口 `http://localhost:8011`
- 前端 API 配置：`frontend/.env.local` 当前指向 `http://localhost:8011`；清掉 `8002` 残留后可改回 `http://localhost:8002`
- 数据库：PostgreSQL 17 本机，`waimao` 数据库

---

## 2026-04-30 测试阶段模型配置更新

- 后端 Replicate 模型调用已统一收敛到 `REPLICATE_MODEL` / `settings.replicate_model`。
- 当前测试默认模型：`openai/gpt-4.1-nano`，用于降低 email-craft 等 pipeline 调试成本。
- 原生产质量模型保留为可回切选项：把 `.env` 中 `REPLICATE_MODEL` 改为 `openai/gpt-5.2` 即可一键恢复。
- 覆盖范围：意图识别、客户搜索 AI 分析、公司画像 AI 分析/图片解析、开发信撰写 pipeline。

---

## 2026-04-30 开发信撰写范围与客户名单规划

### 背景

开发信撰写不能只面向 customer-acquisition pipeline 搜索出来的客户。真实业务里，用户也可能已有自己的客户 Excel/CSV/Word 数据，或者只想手动输入少量客户信息并立即生成几封开发信。

同时必须保护已经稳定的客户开发 pipeline：搜索、爬取、AI 分析、排序、保存 leads 的主流程不改。新增客户名单和开发信范围选择，只作为外围读取、组织和调用 email-craft 的能力。

### 产品方案

新增导航入口：客户名单。

客户名单默认表格列：

| 列 | 说明 |
|---|---|
| 公司名称 | leads.company_name |
| 网站 | leads.website |
| 国家/地区 | leads.country |
| 行业 | leads.industry |
| 公司角色 | leads.company_role |
| 联系人 | leads.contact_name |
| 邮箱 | leads.email |
| 来源 List | MVP 先用 leads.task_id -> tasks 作为来源批次 |
| 匹配度 | leads.match_score |
| 开发信状态 | 未写 / 已写 / 已发送 |
| 操作 | 查看详情、生成/重新生成开发信、导出 |

详情/展开列：

- AI 分析摘要：leads.ai_summary
- 业务匹配点：leads.business_match
- 开发建议：leads.outreach_suggestion
- 邮件主题：outreach_emails.email_subject
- 开发信正文：outreach_emails.email_body

开发信状态映射：

- 未写：没有关联 outreach_emails。
- 已写：存在 outreach_emails，且 send_status = draft。
- 已发送：存在 outreach_emails，且 send_status = sent。

### List / 来源批次策略

MVP 不新增 lead_lists 表，先复用现有 tasks 作为 List：

- customer-acquisition task = 搜索来源 List。
- 上传客户资料 = 独立 import/email-craft task。
- 手动输入客户 = 独立 manual task。

List 命名先自动生成，例如：

- USA ceiling systems - 2026-04-30
- 上传客户名单 - 2026-04-30
- 手动输入客户 - 2026-04-30

后续如需用户重命名、多 List 归属，再新增 lead_lists / lead_list_items。

### 开发信撰写入口调整

点击“开发信撰写”后，不再默认对所有 leads 直接生成。改为先选择范围：

1. 选择已有客户 List。
2. 上传新的客户资料。
3. 手动输入少量客户信息。

email-craft pipeline 后续应支持参数：

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

默认只为“未写”的客户生成开发信。用户明确点“重新生成”时，才覆盖或新增新草稿，避免重复消耗模型额度。

### 手动输入少量客户

支持用户在聊天框直接描述客户，例如：

> 帮我给 ABC Lighting 写一封英文开发信，他们是美国酒店照明工程商，网站是 abc.com，联系人 John，邮箱 john@abc.com。

MVP 流程：

1. LLM 抽取客户字段。
2. 保存为 leads 记录，来源为“手动输入客户”。
3. 复用 email-craft prompt / pipeline 生成开发信。
4. 写入 outreach_emails，后续可在客户名单查看、导出、发送。

### 实施任务拆分

- [x] 客户名单导航页：新增入口，展示 leads + 最新 outreach_email 聚合数据。
- [x] 客户名单表格：实现默认列、搜索/筛选、三态开发信状态。
- [x] 客户详情弹窗/展开：展示 AI 分析摘要、业务匹配点、开发建议、邮件主题、开发信正文。
- [x] 来源 List 展示：MVP 先用 tasks 作为来源批次，自动生成名称。
- [x] email-craft 范围选择：支持按 source_task_id / lead_ids 生成，不再默认全量读取 leads。
- [x] 上传客户资料：上传后保存为独立来源 task/list，再进入 email-craft。
- [x] 手动输入客户：从自然语言抽取字段，保存 lead，再生成开发信。
- [x] 导出适配：客户名单导出和开发信导出都以 outreach_emails 反查 leads，避免遗漏历史搜索任务中的 leads。
- [x] 回归测试：customer-acquisition pipeline 不改主流程，重点验证原搜索、爬取、分析、保存、SSE 不受影响。

### 风险控制

- 不修改 `backend/app/services/pipeline_service.py` 的 customer-acquisition 主流程。
- 新增能力优先放在 `lead_service.py`、客户名单页面、email-craft 范围读取逻辑。
- `leads.task_id` 继续表示来源任务，不引入多对多 List 复杂度。
- 客户名单页面只读聚合数据，不反向影响上游 pipeline。

### 2026-04-30 当前实现交接说明

已完成：

- 后端 `/api/leads` 返回新增 `sourceTaskId`、`sourceList`、`emailSubject`、`emailBody`。
- 后端三态开发信状态已修正：无 `outreach_emails` = `unwritten`，`send_status=sent` = `sent`，其他已有邮件草稿 = `draft`。
- 前端新增 `frontend/components/customer-list.tsx`，作为客户名单主页面。
- 侧边栏新增“客户名单”入口，并接入主 `ChatArea` / `PageView`。
- 客户名单表格已实现默认列、搜索、状态筛选、分页、来源 List、三态状态 badge。
- 客户详情抽屉已实现，点击表格“查看”展示：AI 分析摘要、业务匹配点、开发建议、邮件主题、开发信正文。
- 客户名单表格已新增行选择能力：支持单选、当前页全选/取消全选、显示已选客户数量、清空选择。
- 已预留”生成开发信”批量按钮位置；当前按钮禁用，等待下一步接入 email-craft 范围生成。
- **客户名单”生成开发信”按钮已接通**：选中客户后点击按钮 → 创建 email-craft 会话 → 跳转聊天页 → startConfirmedPipeline({ confirmType: “email_craft”, leadIds, language: “en” }) → SSE/timeline 实时进度 → 完成后 callout 卡片。用户返回客户名单时自动 refetch，开发信状态更新。
- **客户名单操作入口已调整**：表格已去掉”操作”列，点击整行任意位置进入详情抽屉（复选框和网站外链除外，各自有独立行为）；单条重写入口移动到详情抽屉的”开发信正文”区域。
- **email-craft 范围校验已加强**：后端 `/api/tasks/start` 对 email_craft 请求增加校验，无 `lead_ids`、`source_task_id`、`files` 时返回 HTTP 400 提示”请前往客户名单选择客户”。前端确认卡片”直接开始生成”按钮已替换为”前往客户名单选择”（关闭卡片 + 跳转客户名单页）。上传客户资料流程不受影响。
- **客户详情抽屉增加”复制邮件”按钮**：有开发信正文时，在详情抽屉底部显示”复制邮件”按钮，点击将邮件主题+正文复制到剪贴板，按钮短暂变为绿色”已复制”反馈。
- **客户名单”生成开发信”增加语言选择**：选择栏新增 EN/中文 切换，选中语言随按钮一起传递给 email-craft pipeline，替代原硬编码英文。
- **来源 List 展示优化**：后端 `_format_source_list()` 对 email-craft 任务细分显示——有文件时显示”上传客户名单”，有 lead_count 时显示”开发信撰写 (N条)”，其他显示”开发信名单”。
- **上传客户资料保存为独立 import task**：后端 `/api/tasks/start` 在 email_craft 有上传文件时，先创建 `type=import` 的 Task（status=completed），解析文件并按公司名去重，保存 leads 到 import task，再将 source_task_id 指向 import task。Pipeline 不再处理文件解析（已移至 router）。来源 List 正确显示为”上传客户名单 - 日期”。
- **手动输入客户**：用户在聊天中描述客户信息时，LLM 意图识别自动提取客户字段（company_name/website/country/industry/contact_name/email 等），保存为 `type=manual` 的 Task 下的 Lead，然后自动启动 email-craft pipeline 生成开发信。来源 List 显示为”手动输入客户 - 日期”。
- **文件解析逻辑提取为共享函数**：`lead_service.create_leads_from_files()` 同时被 `/api/chat` 和 `/api/tasks/start` 复用，避免代码重复。
- 后端已为 email-craft 增加范围参数透传：`StartPipelineRequest` / `/api/tasks/start` 支持 `lead_ids`、`source_task_id`。
- `email_craft_pipeline_service.py` 已支持按 `lead_ids` 或 `source_task_id` 读取当前用户可访问的 leads；未传范围时暂时保留旧的全量读取行为，避免影响现有聊天确认入口。
- 前端 `startConfirmedPipeline` 类型已预留 `leadIds`、`sourceTaskId` 参数，后续客户名单按钮可直接复用。
- **详情抽屉新增”重写开发信”按钮**：点击后复用现有 email-craft 流程，只为当前客户重新生成开发信。
- **重写覆盖策略已调整**：email-craft 生成成功后，如果客户已有未发送草稿，则覆盖该草稿的主题和正文；如果最新邮件已发送，则保留发送历史并新建 draft。
- **客户删除能力已新增**：客户名单选中客户后可点击”删除客户”；后端 DELETE `/api/leads` 会校验当前用户归属，并删除对应 `leads` 与 `outreach_emails` 记录。

完成状态：

- ~~客户名单页尚未把选中的客户传给 email-craft，批量”生成开发信”按钮仍未启用。~~ **已完成 (2026-04-30)**
- ~~客户名单”操作”目前只有只读查看；单条”生成/重新生成开发信”按钮还未接 pipeline。~~ **已完成后改为详情内”重写开发信”入口 (2026-04-30)**
- ~~email-craft 未传范围时仍保留旧的全量读取行为；等客户名单入口接通并验证后，再改成必须显式选择范围。~~ **已完成 (2026-04-30)**
- ~~详情抽屉是只读展示，暂未支持复制邮件、编辑邮件或重新生成。~~ **已完成：复制邮件、重写开发信、邮件主题/正文手动编辑均已完成 (2026-05-01)**
- ~~来源 List 目前是基于 `tasks` 自动命名，尚未支持用户自定义命名。~~ 已实现自动命名优化。
- ~~客户名单”生成开发信”按钮当前默认英文语言，未提供语言选择 UI。~~ **已完成 (2026-04-30)**
- ~~上传客户资料保存为独立 List、手动输入客户保存为 lead 尚未做。~~ 上传资料已改为独立 import task。手动输入客户已实现。
- 手动输入客户保存为 lead 已实现。
- 客户删除已实现为物理删除；后续如果需要恢复能力，可再改为软删除字段。
- **email-craft Pipeline 已全部完成 (2026-05-01)**：常规生成、上传生成、手动输入生成、范围选择、语言选择、查看/导出、复制、重写、手动编辑、删除联动均已接通。

建议下一步实现：

1. email-blast 批量发送 Pipeline（Resend API 集成）。
2. 客户名单发送状态展示与筛选：接入 email-blast 后展示发送成功/失败/退回等状态。
3. 保持 `pipeline_service.py` 不动，避免影响已稳定的客户开发 pipeline。

---

## 2026-05-01 UI 优化记录

### 已完成的 UI 优化

1. **邮件列表弹窗行展开**（`leads-table-modal.tsx` emails 模式）：点击任意行展开查看完整邮件主题和正文，展开区域还显示邮箱和电话。再次点击收起。

2. **客户名单表格列内联编辑**（`customer-list.tsx`）：
   - "来源 List" 改名为 **"来源/备注"**
   - 表格中"联系人"、"邮箱"、"来源/备注"三列支持点击内联编辑
   - 每个格子 hover 显示淡铅笔图标（`Pencil`），点击进入编辑
   - 编辑状态：失焦/Enter 保存，Esc 取消，留空不保存，无任何弹窗提示
   - 编辑中整行禁用抽屉展开，编辑结束后 200ms 内继续禁止（避免点击失焦导致误触抽屉）
   - 通用 `EditableCell` 组件 + `EditableDetailField` 抽屉版本

3. **后端 Lead 字段更新接口**：
   - `leads` 表新增 `user_note` 字段（Text，存用户备注），已跑 Alembic 迁移
   - 新增 `PATCH /api/leads/{lead_id}` 通用更新接口，支持更新 `contact_name`、`email`、`user_note` 三个字段
   - Schema: `UpdateLeadRequest(BaseModel)` 使用 snake_case（非 CamelModel，避免 alias 兼容问题）
   - Service: `lead_service.update_lead()` 校验 lead 归属当前用户后更新指定字段

### 已解决 / 历史卡点

4. **抽屉内联系人/邮箱内联编辑不生效（已修复）**：
   - **现象**：在客户名单表格（主列表）中，联系人/邮箱/来源备注的内联编辑完全正常；但在点击行打开的详情抽屉（Drawer）中，联系人/邮箱点击后只会闪烁，无法进入编辑模式。
   - **已尝试但不生效的方案**：
     - 在 `<aside>` 上添加 `onMouseDown` + `onClick` 的 `stopPropagation`（阻止事件穿透到 overlay）
     - 将 overlay 从 `<button absolute inset-0>` 改为在外层 `<div>` 上监听 `onClick` 关闭（标准 modal 模式）
     - 在 overlay 的 `onClick` 中检查 `editingCell` 状态，编辑中不关闭抽屉
     - 在 `EditableCell` 的 div 上添加 `onMouseDown preventDefault` 阻止浏览器默认焦点切换
     - 在外层 div 的 onClick 中加 `editingCell || justFinishedRef.current` 守卫
   - **可能的原因分析**：抽屉的 DOM 结构（fixed 定位 + overlay 背景层 + aside 内容层）与 React 事件冒泡/合成事件系统之间存在交互问题。表格内的 EditableCell 代码完全相同但正常工作，说明问题出在抽屉特有的 DOM 层级或事件传播路径上。
   - **最终修复**：给编辑状态增加 `scope: "table" | "drawer"`，避免抽屉进入编辑态时背后的表格同字段也同时 autoFocus 并触发 blur 清空编辑状态。
   - **此前建议下一步**：考虑换一种实现方式，比如：
     - 将抽屉改为 Portal 渲染（`createPortal`），脱离当前 DOM 树避免事件冲突
     - 或在抽屉中不用 EditableCell 内联编辑，改为点击后弹出一个小型 popover/浮层来编辑
     - 或用 `pointer-events: none` 在编辑状态下禁用 overlay 的交互

### 2026-05-01 抽屉内联编辑修复记录

- 已修复 `frontend/components/customer-list.tsx` 客户详情抽屉中“联系人 / 邮箱”无法进入编辑态的问题。
- 根因：抽屉和表格共用同一个 `editingCell` 状态。抽屉点击联系人/邮箱时，背后的表格同一字段也同时渲染为 `autoFocus` input，随后触发 blur 保存逻辑，把编辑态立即清空，所以表现为“闪一下”。
- 修复方式：给 `editingCell` 增加 `scope: "table" | "drawer"`，表格与抽屉编辑态隔离；抽屉字段使用抽屉专用编辑 UI，支持 Enter 保存、Esc 取消、确认/取消图标按钮，不再依赖 blur 自动保存。
- 同步修复：保存成功后同时更新 `leads` 列表和当前 `selectedLead`，避免抽屉里保存成功后仍显示旧值。
- 已验证：
  - `cd frontend && cmd /c npx tsc --noEmit`
  - `cd frontend && cmd /c npm run build`
  - Playwright 打开 `http://localhost:3001`，验证客户名单抽屉联系人/邮箱可进入编辑态，Esc 可取消，邮箱 Enter 保存返回 `PATCH /api/leads/{id}` 200。

### 2026-05-01 邮件主题/正文手动编辑

- 已支持在客户详情抽屉中直接修改“邮件主题”和“开发信正文”，用户可以基于 AI 原文微调。
- 前端：`frontend/components/customer-list.tsx` 新增邮件内容编辑态，主题用单行输入，正文用多行 textarea；支持保存/取消，正文支持 Esc 取消，保存后同步当前抽屉和客户名单列表状态。
- API client：`frontend/lib/api.ts` 新增 `updateLeadEmail()`，兼容后端 snake_case 返回值。
- 后端：新增 `PATCH /api/emails/leads/{lead_id}`，更新当前用户名下该客户最新一封开发信；如果最新邮件已发送，则保留发送历史并新建一封 draft。
- 交互修复：保存失败时不再静默无响应，会在编辑框下方显示错误；关闭抽屉会清空邮件编辑态，重新打开不会继续卡在输入框。
- 已验证：
  - `cd backend && PYTHONUTF8=1 python -m compileall -f app`
  - `cd frontend && cmd /c npx tsc --noEmit`
  - `cd frontend && cmd /c npm run build`
  - 本地导入 `app.main` 确认路由包含 `/api/emails/leads/{lead_id}`。
  - Playwright 验证：主题进入编辑态后关闭抽屉，再重新打开不会保留编辑态。
  - Playwright 验证：前端指向 `http://localhost:8010` 时，主题保存返回 `PATCH /api/emails/leads/{id}` 200，保存后退出编辑态。
- 本地运行备注：`localhost:8002` 当前存在旧 uvicorn/端口残留，OpenAPI 未加载新路由；已临时将 `frontend/.env.local` 改为 `NEXT_PUBLIC_API_URL=http://localhost:8010`，并在 8010 启动干净后端用于联调。后续清理 8002 后可切回原端口。

### 2026-05-01 公司画像进度与完整度修复

- 已修复公司画像生成结果中“完整度 9500%”的问题。原因是 AI/画像 metadata 有时返回 95 这种 0-100 数值，但后端用百分比格式化再次乘以 100。
- 后端 `profile_pipeline_service.py` 新增完整度归一化：兼容 `95` 和 `0.95`，统一按 `0.95` 存储和展示，并限制在 `0-1`。
- 后端 `chat_service.py` 的公司画像完成卡片也增加兼容处理，历史任务里如果已经存了 `95`，也会显示为 `95%`。
- 已修复保存画像完成后 timeline 仍显示“保存画像”执行中的前端兜底：`frontend/app/page.tsx` 在收到 done 时，会把仍处于 running 的步骤同步标记为 completed、progress=100。
- 已验证：
  - `cd backend && PYTHONUTF8=1 python -m compileall -f app`
  - `cd frontend && cmd /c npx tsc --noEmit`
  - `cd frontend && cmd /c npm run build`
  - 脚本验证：`completeness=95` 的公司画像完成卡片显示 `完整度 95%`。

### 2026-05-03 email-blast skill 对齐更新

本轮继续开发已完成：

- 后端 email-blast 默认发送模式改为 `auto`，与 `waimao_toolkit_new/skills/email-blast/` 的策略保持一致：实发时优先按客户国家/地区推算当地时间，非工作日或非 09:00-17:00 时跳过该客户，不改写邮件状态，并在 timeline 中记录跳过原因。
- 后端发送前预检补齐 Resend 侧检查：非 dry-run 时会检查 `RESEND_API_KEY`、发件人名称、发件邮箱前缀、`MAIL_DOMAIN`，并尝试通过 Resend API 校验 key 与发件域名状态。回复邮箱可选；预检失败时直接终止 task，避免半路批量失败。
- 前端客户名单的“确认发送开发信”弹窗增加发送模式选择：默认“按客户当地工作时间”，可切换“立即发送”。参数通过 `sendMode` 传给 `/api/tasks/start`。
- 聊天入口触发 email-blast 但邮箱配置缺失时，会按顺序追问发件人名称、发件邮箱前缀，并保存到 `user_settings`。回复邮箱可选；配置完成后会标记 pending 状态为 completed，避免后续聊天继续被当成配置答案。
- email-blast intent fallback 已能识别“把写好的开发信发出去”等表达，避免误分到 email-craft。

本轮验证：

- `cd backend && python -m compileall -f app` 通过。
- `cd frontend && cmd /c npm run build` 通过。
- `cd frontend && cmd /c npx tsc --noEmit` 通过（先 build 生成 `.next/types` 后执行）。

下一步建议：

1. 跑一次真实前后端联调：从聊天说“把写好的开发信发出去”→ 缺配置时追问 → 客户名单选择 → dry-run → 实发小批量。
2. 补 Resend webhook 的 HTTP 集成测试：构造 Svix 签名请求，验证 `/api/emails/resend/webhook` 对真实 HTTP 请求返回 200 并正确回写状态。
3. 如要完全贴近 skill，可继续扩展国家/时区映射或引入更准确的 timezone 数据源，当前实现是 MVP 级国家偏移表。

### 2026-05-06 email-blast 状态 badge 细化

本轮继续开发已完成：

- 后端 `backend/app/services/lead_service.py` 的客户名单查询改为返回最新 `outreach_emails.send_status` 细分值：`sent`、`delivered`、`failed`、`sending`、`pending`、`bounced`、`complained`。不再把 `delivered` 合并为 `sent`，也不再把 `bounced/complained` 合并为 `failed`。
- 前端 `frontend/components/customer-list.tsx` 行内状态 badge 支持 `已送达`、`退信`、`投诉` 等真实投递状态。
- 顶部状态筛选按业务视角保持简洁，只保留 `全部/未写/已写/已发送/失败`；`delivered` 归入“已发送”筛选，`bounced/complained` 归入“失败”筛选，`sending` 仅在行内展示、不单独提供筛选。
- 发送确认弹窗和选中统计同步修正：`delivered` 计入已发送跳过，`bounced/complained` 计入需处理，不再被误算成“失败可重发”。
- 发送确认弹窗去掉“批次大小”：当前 email-blast 不再暴露也不再传递 `batch_size`；发送策略改为紧凑下拉，和每日上限、最小间隔、最大间隔放在同一组设置里。默认“按客户当地工作时间”，可切换“立即发送”。
- `frontend/types/index.ts` 补充 emailStatus union，方便后续继续扩展发送状态。

本轮验证：

- `cd backend && python -m compileall -f app` 通过。
- `cd frontend && cmd /c npx tsc --noEmit` 通过。
- `cd frontend && cmd /c npm run build` 通过。

下一步建议：

1. 扩展国家/时区映射：当前 `send_mode="auto"` 使用 MVP 级国家 UTC 偏移表，后续可引入更准确 timezone 数据源。
2. 前端交互细化：发送完成后从 callout 一键回客户名单并强制刷新；失败邮件可快速筛选并重发。
3. 部署上线前继续核对生产环境变量：`RESEND_WEBHOOK_SECRET` 已在本地换为真实值，生产环境也必须设置同名真实值；不要把 secret 写入文档或提交。

### 2026-05-06 端到端联调 + Resend 真实发送 + Webhook 测试

本轮验证已完成：

**1. Resend restricted API key 预检 bug 修复**：
- 发现：Resend Sending access 类型的 API key 对 GET 请求（`/domains`、`/audiences`）返回 HTTP 401 + `"This API key is restricted to only send emails"`。pipeline 的 `_check_resend_environment()` 把 401 统一当作 "API Key 无效" 直接终止。
- 修复：`backend/app/services/email_blast_pipeline_service.py` 第 185-194 行，在 401 处理逻辑中增加 `"restricted" in message.lower()` 判断，识别 restricted key 后标记为有效并跳过域名查询（返回"请手动确认域名已验证"提示）。

**2. Alembic 迁移同步检查**：
- 所有 5 张业务表（users, tasks, leads, user_settings, outreach_emails）+ 2 张对话表（conversations, conversation_messages）与 SQLAlchemy 模型完全同步。
- Alembic head version = `8a1b2c3d4e5f`，DB current version = `8a1b2c3d4e5f`，一致。
- `outreach_emails` 的 3 个 Resend tracking 字段（`resend_message_id`、`last_send_attempt_at`、`last_event`）已通过迁移 `7f2c3d4e5a6b` 落地。

**3. Dry-run 发送测试**：
- 通过 `run_email_blast_pipeline()` 直接调用，2 个客户（lead 140, 145），dry-run=True，send_mode=immediate。
- 4 个步骤全部 completed：预检查 → 读取待发送（2/2）→ 发送邮件（模拟成功 2 封）→ 状态回写。
- from_email 正确拼装为 `PRANCE <sales@clientconnet.com>`。

**4. Resend 真实发送测试**：
- 临时将 lead 140 邮箱改为 panlingy3@gmail.com，dry_run=False，send_mode=immediate。
- Resend API 返回成功，`resend_message_id = 3c86d98b-6d3b-4795-ba89-dca1b0ad6852`。
- DB 状态正确变化：`draft → sending → sent`，`sent_at`、`last_send_attempt_at`、`last_event=email.sent` 均写入。
- 测试后已恢复 lead 140 原始邮箱。

**5. Resend webhook 集成测试**：
- 当时使用本地测试 webhook signing secret 验证 Svix 签名流程；2026-05-07 已改为 Resend 控制台真实 webhook signing secret（值只保存在环境变量中，不写入文档）。
- 通过 ASGI transport 直接测试 `POST /api/emails/resend/webhook`：
  - Svix 签名校验通过 → 200。
  - `email.delivered` 事件：`send_status` 从 `sent` 更新为 `delivered`，`error_message` 清空。
  - `email.bounced` 事件：`send_status` 更新为 `bounced`，`error_message` 写入退信原因。
  - 幂等性：多次更新同一封邮件，状态正确覆盖。
  - 签名错误：返回 401 `"Invalid webhook signature"`。
- 注意：Windows 上 Python httpx 对 localhost POST 请求偶现 503（Starlette/uvicorn HTTP 解析兼容问题），不影响实际生产环境（Nginx 反代 + Linux）。

**6. 配置确认**：
- `user_settings.confirmed_at` 已为 user_id=1 设置为当前时间，解除真实发送阻断。
- `.env` 中 `RESEND_WEBHOOK_SECRET` 已配置；2026-05-07 已替换为 Resend 控制台真实 webhook signing secret。
- 发件人地址：`PRANCE <sales@clientconnet.com>` — 域名 clientconnet.com 已在 Resend 验证。

**验证命令**：
- `cd backend && python -m compileall -f app` 通过。
- `cd frontend && cmd /c npx tsc --noEmit` 通过。
- `cd frontend && npm run build` 通过。
4. 前端交互细化：发送完成后从 callout 一键回客户名单并强制刷新；失败邮件可快速筛选并重发。

### 2026-05-06 邮箱推荐配置与首次发送确认

本轮继续开发已完成：

- 默认发件域名改为 `clientconnet.com`，不再使用 `@yourdomain.com`；前端邮箱配置页会清理域名和前缀里的多余 `@`，展示为 `sales@clientconnet.com`，避免出现 `@@`。
- 公司画像保存/更新后会调用 `ensure_recommended_email_settings()` 自动生成推荐配置：发件人名称从公司名提取（当前 PRANCE 画像会得到 `PRANCE`），发件邮箱前缀默认 `sales`，回复接收邮箱默认空。
- 推荐配置现在会跟随“当前公司画像”刷新：如果 `user_settings.profile_id` 仍绑定旧画像，新读取设置时会刷新到当前画像，并清空 `reply_to_email`。同一个画像下用户已经保存过的配置不会被反复覆盖。
- 新增 `user_settings.confirmed_at` 字段和迁移 `backend/alembic/versions/8a1b2c3d4e5f_add_confirmed_at_to_user_settings.py`。`configuredAt=null` 表示这是系统推荐但用户尚未确认；邮箱配置页保存或对话式配置完成后写入确认时间。
- 客户名单点击“发送邮件”时，不仅检查发件人名称和发件邮箱前缀，也会检查 `configuredAt`；如果是首次推荐态，会弹窗提示并跳转邮箱配置页，让用户确认/修改后保存。
- 发送确认弹窗新增“发件信息”区块，显示发件人、发件邮箱、回复邮箱，并提供“修改”按钮返回邮箱配置页。
- 聊天里的邮箱配置追问流程仍只要求发件人名称和发件邮箱前缀，回复邮箱可跳过；对话式配置完成后会写入 `confirmed_at`。
- 非 dry-run 的 email-blast 预检新增“邮箱配置确认”检查，避免未经确认的推荐配置直接实发。
- 本地数据库当前已验证：`GET settings_service.get_settings(db, 1)` 会把旧 `Zhang/zhangmanager` 刷新为 `sender_name=PRANCE`、`from_email_prefix=sales`、`reply_to_email=""`、`mail_domain=clientconnet.com`、`configured_at=None`。

本轮验证：

- `cd backend && python -m alembic upgrade head` 通过，已添加 `user_settings.confirmed_at`。
- `cd backend && python -m compileall -f app` 通过。
- `cd frontend && cmd /c npx tsc --noEmit` 通过。
- `cd frontend && cmd /c npm run build` 通过。

刚刚被打断的部分：

- 我已经跑完 migration、后端 compile、前端 tsc、前端 build。
- 被打断时正准备重启前端/后端 dev server，并做最后的接口与浏览器验证。
- 后续已于 2026-05-07 完成：已重启前后端并确认前端没有 `_next/static` 404、`/api/settings` 可返回推荐态 `configuredAt=null`、客户名单首次点击发送会跳到邮箱配置页。
- 重要提醒：刚跑过 `npm run build`，如果旧的 Next dev server 还在跑，前端可能再次出现静态资源 404；重启 dev server 后强制刷新即可。

### 2026-05-06 UI 清理与 dry-run 移除 + 意图识别优化

本轮继续开发已完成：

- **dry-run 模式已完全移除**：前后端所有 `dry_run` 相关代码已剔除。后端 `email_blast_pipeline_service.py` 中所有 dry_run 分支已移除，始终调用 Resend API 真实发送，始终写回邮件状态；`chat_service.py`、`intent_router.py` 中 dry_run 参数默认值改为 `False`；`schemas/chat.py`、`schemas/email.py` 中 `dry_run` 默认值改为 `False`。前端 `customer-list.tsx` 中 dry-run 复选框和提示文字已删除。
- **发送完成卡片简化**：后端 `_task_completed_callout` 中 email-blast 完成卡片从两个按钮（"查看状态"+"返回客户名单"）改为一个"前往客户名单"按钮，action type 从 `view-list` 改为 `go-customer-list`。前端 `page.tsx` 中 `onGoToCustomerList` prop 已补全传递到 `ChatArea` 组件，之前遗漏导致按钮点击无响应。
- **预检查步骤消息简化**：后端预检查完成后不再拼接 Resend API 校验的技术详情（如"API Key 无权查询域名状态，请手动确认 clientconnet.com 已在 Resend 中验证"），统一只显示"配置检查通过"。
- **Pipeline 时间轴排版修复**：`pipeline-timeline.tsx` 中步骤名称和消息从同行 `flex` 排列改为上下两行（`<span>` + `<p>`），消息加 `break-words` 允许长文本自动换行，解决溢出卡片边界的问题。
- **邮箱配置页精简**：去掉所有冗余描述备注（"客户收到邮件时看到的发件人名称"、"（可选）"、"可留空"、"系统自动生成"、"域名由平台统一管理"等）；回复接收邮箱的"（可选）"和"可留空"去掉，placeholder 改为"客户的回复会回传到填写的邮箱地址"。
- **邮箱配置页实时预览**：新增发件人预览区，显示 `senderName <prefix@clientconnet.com>`，随用户输入实时更新；未填写时显示提示文字。
- **LLM 意图识别 email_blast/email_craft 区分强化**：`intent_router.py` LLM prompt 中新增明确的区分规则（"发邮件"→ email_blast，"写开发信"→ email_craft），并给出具体示例。验证结果：`"发邮件"` → email_blast，`"发送开发信"` → email_blast，`"写开发信"` → email_craft，`"帮我写邮件"` → email_craft。

### 2026-05-07 本地 dev server 重启验证 + 部署前配置核对

本轮验证已完成：

- 已重启本地后端 dev server：`http://127.0.0.1:8002`，日志输出到 `.codex-run-logs/backend-8002.*.log`。
- 已重启本地前端 dev server：`http://localhost:3000`，日志输出到 `.codex-run-logs/frontend-3000.*.log`。
- Playwright 验证首页加载通过：没有 `_next/static` 404，没有 4xx/5xx 网络响应，没有 console error/warning。
- `/api/settings` 正常返回当前已确认配置；为验证推荐态，临时将本地 `user_settings.confirmed_at` 置空，确认接口返回 `configuredAt=null`，验证后已恢复原确认时间。
- 客户名单首次发送确认路径验证通过：在推荐态下选择可发送客户，点击"发送邮件"会先弹出"首次发送前请先确认邮箱配置"提示，确认后跳转到邮箱配置页。
- 本地当前 `user_settings` 已恢复到确认态，避免影响后续真实发送测试。

部署前配置核对结果：

- 后端实际读取的是项目根目录 `.env`（`backend/app/config.py` 的 `_PROJECT_ROOT` 指向项目根目录），不是 `backend/.env`。`backend/.env` 当前仍是旧占位值，容易误导，部署时应以平台环境变量或根 `.env` 为准。
- `RESEND_API_KEY`：根 `.env` 已配置；通过 Resend `/domains` 探测返回 `restricted_api_key`，说明当前 key 是 Sending-only 类型，符合当前发送链路预期，但不能用来查询域名状态。
- `RESEND_WEBHOOK_SECRET`：根 `.env` 已替换为 Resend 控制台 webhook 的真实 signing secret；部署生产环境时也必须同步设置同名环境变量。
- `MAIL_DOMAIN`：根 `.env` 为 `clientconnet.com`，与当前发件域名一致。
- 前端 `frontend/.env.local` 当前为 `NEXT_PUBLIC_API_URL=http://localhost:8011`，这是因为本机 `8002` 端口残留了旧 uvicorn 响应，Better Auth 联调用干净后端端口 `8011` 完成；部署到 Vercel 前必须改为后端公网 HTTPS API 地址 `https://api.clientconnet.com`。
- 后端公网 webhook URL 已按后端 API 子域名方案在 Resend 控制台配置为 `https://api.clientconnet.com/api/emails/resend/webhook`。后续部署时需要让后端公网 API 使用 `api.clientconnet.com`，否则要回 Resend 控制台同步改 webhook endpoint。
- `CORS_ORIGINS` 当前仍是本地 localhost 列表；部署后需要加入 Vercel 前端正式域名，并保持后端允许携带 cookie。

下一步建议：

1. 部署后确认 `https://api.clientconnet.com/api/emails/resend/webhook` 能访问到后端 `/api/emails/resend/webhook` 路由。
2. 部署后设置 `NEXT_PUBLIC_API_URL` 为 `https://api.clientconnet.com`，并同步更新后端 `CORS_ORIGINS`。
3. 部署后验证 Better Auth 登录态 cookie 能从前端域名带到 `api.clientconnet.com`。

### 2026-05-07 Better Auth 注册登录闭环

本轮继续开发已完成：

- 前端安装 `better-auth`、`pg`、`@types/pg`，新增 `frontend/lib/auth.ts`、`frontend/lib/auth-client.ts`、`frontend/app/api/auth/[...all]/route.ts`。
- Better Auth 使用现有 PostgreSQL，并通过 schema 映射复用 `users` 表的整数主键：`name -> username`、`email_verified`、`created_at`、`updated_at`；session/account/verification 分别落到 `auth_sessions`、`auth_accounts`、`auth_verifications`。
- 新增迁移 `backend/alembic/versions/9b2c3d4e5f6a_add_better_auth_tables.py`：补 `users.email/email_verified/image`，创建 Better Auth 相关表，并修正历史 `users_id_seq`，避免已有 `users.id=1` 时注册新用户撞主键。
- 后端 `backend/app/dependencies.py` 已从 `CurrentUser=1` stub 改为真实校验 Better Auth signed session cookie：读取 cookie、校验 HMAC-SHA256 签名、查 `auth_sessions.token`、检查过期时间，最后返回整数 `user_id`。
- 前端新增登录/注册界面 `frontend/components/auth-screen.tsx`；`frontend/app/page.tsx` 会根据 `authClient.useSession()` 切换登录页/工作台，并在退出登录后清空本地业务状态。
- `frontend/lib/api.ts` 所有业务 fetch/SSE/导出请求已加 `credentials: "include"`，确保 Better Auth cookie 能传给 FastAPI。
- `frontend/components/sidebar.tsx` 新增当前用户邮箱展示和退出登录按钮。
- `.env.example`、`backend/.env.example`、`frontend/.env.example` 已补 Better Auth 相关占位变量；根 `.env` 和 `frontend/.env.local` 已配置本地联调用 secret（不要提交真实 secret）。

本地验证结果：

- `cd backend && python -m alembic upgrade head` 通过。
- `cd backend && python -m compileall -f app` 通过。
- `cd frontend && cmd /c npx tsc --noEmit` 通过。
- `cd frontend && cmd /c npm run build` 通过。
- 使用干净后端 `http://localhost:8011` + 前端 `http://localhost:3000` 完成浏览器注册、登录、退出验证：登录后 `/api/settings` 返回 200，退出后 `/api/settings` 返回 401。
- 注册验证生成的 `codex.auth.*@example.com` 临时用户已清理。

本地端口备注：

- `8002` 端口当前仍有旧 uvicorn 残留响应，但 Windows 进程表查不到可终止进程；为了避免旧代码干扰，Better Auth 联调使用 `8011`。后续如果清掉 `8002`，可把 `frontend/.env.local` 改回 `http://localhost:8002`；生产环境不要用本地端口。

生产部署注意：

- `BETTER_AUTH_SECRET` 必须同时设置在 Next.js 前端服务和 FastAPI 后端环境里，且两边完全一致。
- `BETTER_AUTH_URL` 应设置为生产前端地址；`BETTER_AUTH_DATABASE_URL` 指向生产 PostgreSQL。
- 如果前端在 `clientconnet.com`/`app.clientconnet.com`，后端在 `api.clientconnet.com`，建议设置 `BETTER_AUTH_COOKIE_DOMAIN=.clientconnet.com`，让登录 cookie 能跨子域发送。
- `NEXT_PUBLIC_API_URL` 生产值固定为 `https://api.clientconnet.com`；后端 `CORS_ORIGINS` 必须加入前端 Vercel/正式域名。
- Resend webhook URL 继续使用 `https://api.clientconnet.com/api/emails/resend/webhook`，后端生产环境也必须设置同一个真实 `RESEND_WEBHOOK_SECRET`。

剩余事项：

1. Seed 脚本适配多用户。
2. 部署上线并做生产烟测：登录/注册、`/api/settings`、客户名单、Resend webhook、小批量真实发送。

### 给其他 AI 编程工具的接手提示词

如果换其他 AI 编程工具继续开发，可以直接复制下面这段作为上下文：

```text
请先阅读 doc/progress-todo.md 的 email-blast 章节和 2026-05-06 更新记录。当前项目是 AI 外贸员智能体，已接通 customer-acquisition、company-profile、email-craft、email-blast 四个 pipeline。

email-blast 当前状态：
- dry-run 模式已完全移除，所有发送均为 Resend 真实发送。
- 客户名单选择客户 → 发送确认弹窗 → /api/tasks/start(confirmType=”email_blast”) → SSE/timeline → Resend 实发 → outreach_emails 状态回写 → Resend webhook 回写 delivered/bounced/failed/complained。
- 默认 send_mode=”auto”，遵循 waimao_toolkit_new/skills/email-blast/：按客户国家/地区推算当地工作时间，非工作日或非 09:00-17:00 跳过，不改写该邮件状态；前端弹窗可切换”按客户当地工作时间/立即发送”。
- 发送前检查 RESEND_API_KEY、发件人名称、发件邮箱前缀、邮箱配置确认状态、MAIL_DOMAIN，并尝试通过 Resend API 校验 key 和发件域名状态；reply_to_email 可空。
- 发送完成卡片只显示”前往客户名单”按钮（go-customer-list action），点击跳转客户名单页。
- LLM 意图识别已强化 email_craft/email_blast 区分：”发邮件”→ email_blast，”写开发信”→ email_craft。
- 客户名单保留 `delivered/bounced/complained` 真实状态；顶部筛选只保留”全部/未写/已写/已发送/失败”。
- 发送确认弹窗参数：发送策略 `send_mode`、每日上限 `daily_limit`、最小/最大间隔 `delay_min/delay_max`（无 dry-run）。
- 公司画像保存后生成邮箱推荐配置：`sender_name` 从公司名提取，`from_email_prefix` 默认 `sales`，`MAIL_DOMAIN=clientconnet.com`。
- `user_settings.confirmed_at` 区分推荐态/确认态：客户名单首次点击发送会引导到邮箱配置页确认。
- 2026-05-06 端到端联调已完成：Resend 真实发送成功、webhook 回写验证通过、Alembic 迁移同步确认。
- 2026-05-07 Resend webhook 控制台 endpoint 已配置为 `https://api.clientconnet.com/api/emails/resend/webhook`；后续生产部署必须让后端公网 API 真正跑在 `api.clientconnet.com`。
- 2026-05-07 Better Auth 注册/登录/退出闭环已完成：Next.js 提供 `/api/auth/[...all]`，FastAPI 通过 Better Auth session cookie 识别真实 `users.id`，`CurrentUser=1` stub 已移除。
- 生产部署时：`NEXT_PUBLIC_API_URL=https://api.clientconnet.com`；后端生产环境设置真实 `RESEND_WEBHOOK_SECRET` 和与前端一致的 `BETTER_AUTH_SECRET`；后端 `CORS_ORIGINS` 加入前端 Vercel/正式域名。
- 如果前端和后端分属 `clientconnet.com` 子域，设置 `BETTER_AUTH_COOKIE_DOMAIN=.clientconnet.com`，确保登录 cookie 能发送到 `api.clientconnet.com`。

关键文件：
- backend/app/services/email_blast_pipeline_service.py：email-blast 编排、Resend 发送、时区窗口、预检。
- backend/app/services/chat_service.py：email-blast 对话入口、邮箱配置追问、start_email_blast_pipeline。
- backend/app/services/intent_router.py：LLM 意图识别（email_craft/email_blast 已强化区分）。
- backend/app/routers/tasks.py：confirmType=”email_blast” 启动入口。
- backend/app/routers/emails.py + backend/app/services/email_service.py：Resend webhook。
- frontend/components/customer-list.tsx：客户名单、发送确认弹窗、发送设置 UI。
- frontend/components/email-config.tsx：邮箱配置页（精简版 + 实时预览）。
- frontend/components/pipeline-timeline.tsx：时间轴组件（步骤名称+消息上下两行排列）。
- frontend/app/page.tsx / frontend/lib/api.ts / frontend/components/chat-area.tsx：参数透传。
- frontend/lib/auth.ts / frontend/lib/auth-client.ts / frontend/app/api/auth/[...all]/route.ts：Better Auth 服务端配置、客户端实例、Next.js Auth 路由。
- frontend/components/auth-screen.tsx / frontend/components/sidebar.tsx：登录注册界面、用户邮箱展示、退出登录。
- backend/app/dependencies.py / backend/app/models/auth.py / backend/alembic/versions/9b2c3d4e5f6a_add_better_auth_tables.py：FastAPI session cookie 校验、Better Auth 表模型和迁移。

下一步小任务：
1. 部署上线（Vercel + 腾讯云/后端），确保后端公网 API 绑定 `api.clientconnet.com`。
2. 生产环境变量核对：真实 `RESEND_API_KEY`、真实 `RESEND_WEBHOOK_SECRET`、`MAIL_DOMAIN=clientconnet.com`、`NEXT_PUBLIC_API_URL=https://api.clientconnet.com`、前后端一致的 `BETTER_AUTH_SECRET`、生产 `BETTER_AUTH_URL`/`BETTER_AUTH_DATABASE_URL`。
3. 部署后烟测：注册/登录/退出、`/api/settings`、客户名单首次发送配置确认、Resend webhook、小批量真实发送。
4. Seed 脚本适配多用户。

验证命令：
- cd backend && python -m alembic upgrade head
- cd backend && python -m compileall -f app
- cd frontend && cmd /c npx tsc --noEmit
- cd frontend && cmd /c npm run build

注意：不要重构 backend/app/services/pipeline_service.py；不要引入 lead_lists 新表；每次完成一个小任务后更新 doc/progress-todo.md。
```

```text
请先阅读 doc/progress-todo.md 中”已完成 Pipeline”和”TODO：剩余 Pipeline / email-blast”部分。这个项目是 AI 外贸员智能体，4 个核心 pipeline（客户搜索、公司画像、开发信撰写、批量发送）全部已接通，客户名单页面和对话历史持久化也已完成。

项目概览：
- 前端：Next.js 14 + TypeScript + Tailwind CSS，目录 frontend/
- 后端：Python FastAPI + SQLAlchemy async + PostgreSQL，目录 backend/
- 4 个已接通 Pipeline：customer-acquisition、company-profile、email-craft、email-blast
- 客户名单页面：frontend/components/customer-list.tsx（整行点击打开详情抽屉，支持批量选择/删除/生成开发信/发送邮件/重写/复制/手动编辑邮件主题与正文/导出）
- 对话历史：conversations + conversation_messages 表，前端自动从后端加载历史会话

已完成的关键能力：
1. 客户搜索 → Serper搜索 → Playwright爬取 → AI分析 → 筛选排序 → 存DB → SSE实时进度
2. 公司画像 → Playwright爬官网 → AI结构化画像 → 增量更新/重新采集/补充资料
3. 开发信撰写 → 加载画像+线索(DB/上传/手动输入) → AI逐条生成 → 覆盖策略(草稿覆盖/已发送保留新建) → 查看/导出 Excel → 用户可手动编辑主题和正文
4. 批量发送 → dry-run 已移除，全部真实 Resend 发送 → 逐封 sending/sent/failed 状态回写 → Resend webhook 回写 delivered/bounced/failed/complained → 完成后”前往客户名单”按钮
5. 客户名单 → 表格(搜索/筛选/排序/分页) → 详情抽屉(整行点击) → 批量生成/重写/删除/复制/编辑/导出
6. 对话历史 → 后端持久化(conversations表) → 前端自动加载历史会话 → 上下文记忆
7. LLM意图识别 → Replicate GPT + 正则fallback → email_craft/email_blast 已强化区分
8. 邮箱配置 → 精简版配置页(实时预览) + 系统推荐态/用户确认态区分
9. Resend webhook → POST `/api/emails/resend/webhook`，Svix 签名校验
10. SPF/DKIM/DMARC 三套 DNS 认证齐全
11. Better Auth 登录注册 → Next.js `/api/auth/[...all]` + 前端登录/注册/退出 + FastAPI 读取 Better Auth session cookie 映射真实 `users.id`

重要边界：
1. 不要修改 backend/app/services/pipeline_service.py，避免把已经稳定的 customer-acquisition 客户开发 pipeline 改坏。
2. 不要大重构，不要引入 lead_lists 新表；MVP 继续用 tasks 作为来源 List。
3. 每次只做小任务，做完更新 doc/progress-todo.md。
4. 后端启动：cd backend && PYTHONUTF8=1 uvicorn app.main:app --reload --port 8002；当前本机 `8002` 有旧 uvicorn 残留时可临时用 `8011`，并同步改 `frontend/.env.local`。
5. 前端启动：cd frontend && npm run dev（端口3000）
6. Python 编码：Windows 环境，需设置 PYTHONUTF8=1
7. 生产部署约定：后端公网 API 使用 `https://api.clientconnet.com`，Resend webhook URL 保持 `https://api.clientconnet.com/api/emails/resend/webhook`。
8. Auth/跨域约定：生产 `NEXT_PUBLIC_API_URL=https://api.clientconnet.com`；前后端设置同一个 `BETTER_AUTH_SECRET`；后端 `CORS_ORIGINS` 加入前端 Vercel/正式域名；跨子域时设置 `BETTER_AUTH_COOKIE_DOMAIN=.clientconnet.com`。

下一步小任务：
1. 部署上线（Vercel + 腾讯云/后端），确保 `api.clientconnet.com` 指到后端。
2. 生产环境变量核对：真实 `RESEND_API_KEY`、真实 `RESEND_WEBHOOK_SECRET`、`MAIL_DOMAIN=clientconnet.com`、`NEXT_PUBLIC_API_URL=https://api.clientconnet.com`、前后端一致的 `BETTER_AUTH_SECRET`、生产 `BETTER_AUTH_URL`/`BETTER_AUTH_DATABASE_URL`。
3. 部署后烟测：注册/登录/退出、`/api/settings`、客户名单首次发送配置确认、Resend webhook、小批量真实发送。
4. Seed 脚本适配多用户。

完成后请运行：
1. cd backend && python -m alembic upgrade head
2. cd backend && python -m compileall -f app
3. cd frontend && cmd /c npx tsc --noEmit
4. cd frontend && cmd /c npm run build

完成后更新 doc/progress-todo.md，写清楚做了什么、还没做什么、下一步怎么接。
```
