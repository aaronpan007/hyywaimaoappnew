---
description: "开发信批量发送与发送状态更新工具。当用户确认开发信已经写好想要发送、提供了待发送的邮件列表（飞书表格/Excel/CSV）、提到'发送开发信'、'批量发邮件'、'群发'、'开始发送'、'email blast'、'send cold emails'、'batch send'、'send emails'时，务必使用此 skill。即使没有明确说'发送'，只要用户在讨论把已经写好的开发信发出去、安排发信计划、查看发送状态，都应该触发此 skill。"
---

# Email Blast Skill — 开发信批量发送与状态更新

## 概述

把 email-craft 生成的（或用户自行准备的）开发信真正发出去。这不是一个简单的"发邮件按钮"，而是外贸开发流程的执行层——负责批量控制、发送节奏、状态记录和飞书表格回写。

## 与其他 Skill 的关系

```
customer-acquisition → email-craft → email-blast（本 Skill）
     找客户              写开发信          发邮件 + 更新状态
```

- **上游**: email-craft 把开发信写进飞书表格的"开发信"和"邮件主题"字段（或通过 `--csv` 模式写进 CSV 文件）
- **本 Skill**: 读取这些待发送记录，调用 Resend API 发出，更新发送状态（写回飞书表格或 CSV）
- **下游**: 后续可对接回复监控（"已回复"字段）

## 发送前预检（必须执行）

### 首次使用配置（两阶段）

首次使用本 Skill 时，配置分为两个阶段：

#### 阶段 A：基础配置（可立即完成）

1. 检查环境变量状态：
   ```bash
   python __SKILL_DIR__/email-blast/scripts/run.py --setup
   ```
2. 如果返回 `status: "ok"`，跳过配置，直接进入核心流程。
3. 如果 `missing_vars` 不为空，逐个使用 AskUserQuestion 向用户收集值：
   - 优先收集 `RESEND_API_KEY`（必须）
   - `FROM_EMAIL` 标注为"发送前配置"，可在阶段 B 再填写
   - `REPLY_TO_EMAIL` 为可选项
   - 展示 `description` 和 `hint` 引导用户输入
   - 收集到值后立即写入：
     ```bash
     python __SKILL_DIR__/email-blast/scripts/run.py --setup KEY=VALUE
     ```
4. 所有变量配置完成后，再次运行 `--setup` 确认 status 为 "ok"。

> **重要：阶段 A 严禁自动填写 FROM_EMAIL**
>
> - **不要**在阶段 A 收集 FROM_EMAIL 的值，即使 `missing_vars` 中包含它，也要**跳过**
> - **不要**用域名自动拼接品牌名（如用户提供 `nongtehub.com`，不能自动生成 `NongteHub <sales@nongtehub.com>`）——域名≠公司名/品牌名
> - FROM_EMAIL 的品牌名必须来自 company-profile 生成的公司档案（`profile.json` 中的公司名/品牌名）
> - 正确流程：先完成 company-profile → 从档案获取正确品牌名 → 在阶段 B 配置 FROM_EMAIL

> **注意**: `--setup` 负责检查/写入 .env 占位符。配置完成后，仍需运行 `--check-env` 验证 API Key 有效性、域名验证等。

#### 阶段 B：发送前配置（准备发邮件时完成）

在准备发送邮件之前，运行环境检查：

```bash
python __SKILL_DIR__/email-blast/scripts/run.py --check-env
```

如果域名验证或 FROM_EMAIL 未通过，`--check-env` 会自动输出详细的配置指引，包括：
1. 如何在 Resend 控制台添加并验证域名（注册 → 添加域名 → DNS → 验证）
2. 如何配置 FROM_EMAIL（格式示例：`Brand Name <sales@yourdomain.com>`）
3. resend-guide.md 的参考路径
4. **重要**: DNS 记录必须包含 SPF + DKIM + DMARC 三条记录，缺一不可。
   缺少 DMARC 会导致 Google/Yahoo/Microsoft 拒收邮件。
   如果 Resend 提示 "No DMARC record found"，请按 resend-guide.md 添加 DMARC TXT 记录。

完成配置后，再次运行 `--check-env` 确认所有检查通过。

### 环境预检命令

配置完成后，运行环境检查确认一切正常：

在展示待发送列表之前，先做环境检查：

```bash
python __SKILL_DIR__/email-blast/scripts/run.py --check-env
```

这会检查：
1. `RESEND_API_KEY` 是否已配置且有效（调用 Resend /domains 验证）
2. `FROM_EMAIL` 是否已配置
3. 发件域名是否已在 Resend 验证通过
4. 飞书表格连接是否正常

**如果任何一项失败，停止执行并告知用户具体问题和解决方法。不要跳过预检直接发邮件。**

## 核心流程

### Step 1: 确定数据源 & 读取待发送记录

1. 运行 `--list-tables` 查看 email-craft 记忆中的可用表格：
   ```bash
   python __SKILL_DIR__/email-blast/scripts/run.py --list-tables
   ```
2. 让用户选择发信表格：
   - 从历史中选择：`--table N`（N 为表格序号）
   - 直接指定飞书链接：`--feishu-link LINK`
3. 如果没有可用表格，提示用户先用 email-craft 生成开发信
4. 用户也可以 `--csv` 上传自己的表格

读取待发送记录：
```bash
python __SKILL_DIR__/email-blast/scripts/run.py --list-pending
```

筛选逻辑（脚本内部自动完成）：
- "邮箱"字段不为空
- "开发信"字段不为空
- "邮件主题"字段不为空
- "邮件已发送"字段为空或为"否"

### Step 2: 展示发送预览

向用户展示：
```
待发送邮件预览
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
共 X 封待发送邮件

#1  Acme Corp (john@acme.com)
    主题: Re: Your recent expansion in Southeast Asia
    预览: Dear John, I noticed Acme Corp recently...

#2  GlobalTech (sarah@globaltech.io)
    主题: Partnership opportunity for smart home solutions
    预览: Hi Sarah, Following up on GlobalTech's...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

询问用户确认：
- 确认发送这些邮件？
- 是否要排除某些客户？
- 发送策略参数（见下方）

### Step 3: 设置发送策略

**默认策略**（适合大多数场景）：
```
批次大小: 10 封/批
邮件间隔: 60-120 秒（随机）
每日上限: 50 封
时区策略: 自动（根据客户国家调整发送时间）
```

用户可以调整的参数：

| 参数 | 说明 | 默认值 | 推荐范围 |
|------|------|--------|----------|
| `--batch-size` | 每批多少封 | 10 | 5-20 |
| `--delay-min` | 最小间隔秒数 | 60 | 30-300 |
| `--delay-max` | 最大间隔秒数 | 120 | 60-600 |
| `--daily-limit` | 每日发送上限 | 50 | 20-100 |
| `--no-random` | 禁用随机延迟（固定间隔） | 关 | - |
| `--send-mode` | 发送模式 | auto | auto / immediate / schedule |
| `--dry-run` | 预演模式，不实际发送 | 关 | - |

**时区策略说明**：
- `auto`（默认）：根据"国家/地区"字段自动判断客户所在时区，仅在对方工作日 9:00-17:00 发送
- `immediate`：忽略时区，立即发送
- 如果当前时间不在目标客户的工作时间窗口内，会跳过并提示"将在对方工作时间发送"

### Step 4: 执行发送

确认后执行：
```bash
python __SKILL_DIR__/email-blast/scripts/run.py \
  --batch-size 10 \
  --delay-min 60 \
  --delay-max 120 \
  --daily-limit 50 \
  --send-mode auto
```

**或者指定特定客户：**
```bash
python __SKILL_DIR__/email-blast/scripts/run.py \
  --select recXXX,recYYY \
  --batch-size 5 \
  --delay-min 60 \
  --delay-max 120
```

**发送过程中的实时反馈：**
```
发送中... [3/15]
  → john@acme.com ✓ (message_id: msg_xxx)
  等待 87 秒...
发送中... [4/15]
  → sarah@globaltech.io ✓ (message_id: msg_yyy)
  等待 95 秒...
发送中... [5/15]
  → mike@invalid.xxx ✗ (错误: 邮箱格式无效)
```

### Step 5: 发送结果报告

发送完成后自动展示报告：

```
发送结果报告
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
成功: 12 封
失败: 2 封
跳过: 1 封（不在发送时间窗口）
未发送: 0 封（已达每日上限）

失败明细:
  #5  mike@invalid.xxx — 邮箱格式无效
  #11 bob@company.com — Resend API: 域名未验证

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
飞书表格状态已更新。
```

**注意**: 每封邮件发送后都会立即更新飞书表格状态（不是等全部发完才更新），这样即使中途出错，已发送的记录也有状态记录。

## 发送失败处理

失败原因分类及建议：

| 错误类型 | 说明 | 建议 |
|----------|------|------|
| 邮箱格式无效 | 收件人邮箱格式不正确 | 检查"邮箱"字段 |
| 域名未验证 | FROM_EMAIL 的域名未在 Resend 验证 | 去 Resend 控制台验证域名 |
| API 限流 | 发送频率过高 | 增大 --delay-min 和 --delay-max |
| 邮箱不存在 | 收件地址无法投递 | 标记为无效邮箱 |
| 内容被拒 | 邮件内容触发了 Resend 的内容策略 | 修改开发信内容 |
| 网络超时 | 网络问题导致请求失败 | 自动重试 1 次 |

失败的邮件会在"备注"字段写入失败原因，"邮件已发送"保持为空，下次运行时仍会出现在待发送列表中。

## 高级用法

### 查看今日发送统计
```bash
python __SKILL_DIR__/email-blast/scripts/run.py --stats
```

### 重发失败的邮件
```bash
python __SKILL_DIR__/email-blast/scripts/run.py --retry-failed
```

### 仅检查不发送（预演模式）
```bash
python __SKILL_DIR__/email-blast/scripts/run.py --dry-run
```

### 从 Excel/CSV 发送
如果用户提供了 Excel 或 CSV 文件（而不是飞书表格），使用 `--csv` 参数：
```bash
python __SKILL_DIR__/email-blast/scripts/run.py --csv path/to/file.csv
```

CSV 文件至少需要包含列：`email`, `subject`, `body`

### 从 Pipeline CSV 发送（customer-acquisition → email-craft 导出的 CSV）

当飞书不可用时，可以使用 email-craft `--csv` 模式生成的 CSV 文件直接发送。这种 CSV 包含完整的 16 列 pipeline schema（中文表头），发送状态会回写到同一文件。

```bash
# 预览
python __SKILL_DIR__/email-blast/scripts/run.py --pipeline-csv customers.csv --dry-run

# 发送
python __SKILL_DIR__/email-blast/scripts/run.py --pipeline-csv customers.csv --delay-min 60 --delay-max 120
```

`--pipeline-csv` 与 `--csv` 的区别：

| | `--csv` | `--pipeline-csv` |
|---|---------|-----------------|
| CSV 格式 | 通用（email/subject/body） | Pipeline schema（16列中文字头） |
| 状态回写 | 无 | 写回 CSV（邮件已发送/发送时间/备注） |
| 数据来源 | 用户自备 | customer-acquisition → email-craft 产出 |
| 筛选逻辑 | 无 | 自动跳过已发送（邮件已发送=是）和缺失字段的行 |

## 环境变量

在 `<project-root>/.env` 中配置（首次使用时会自动引导配置）：

```env
# Resend API 密钥（从 Resend 网站获取，见 references/resend-guide.md）
RESEND_API_KEY=re_xxxxxxxx

# 发件人邮箱（系统自动拼装，格式：品牌名 <前缀@域名>）
FROM_EMAIL=Brand Name <sales@yourdomain.com>

# 客户回复邮箱（客户回复开发信时发送到此地址，可选）
REPLY_TO_EMAIL=yourname@gmail.com
```

## 飞书表格字段依赖

本 Skill 依赖以下字段（customer-acquisition 和 email-craft 已创建）：

| 字段名 | 用途 | 本 Skill 的操作 |
|--------|------|----------------|
| 邮箱 | 收件人地址 | 读取 |
| 开发信 | 邮件正文 | 读取 |
| 邮件主题 | 邮件标题 | 读取 + 写入 |
| 国家/地区 | 时区判断 | 读取 |
| 联系人 | 收件人称呼 | 读取 |
| 邮件已发送 | 发送状态 | 写入（是/否） |
| 发送时间 | 发送时间戳 | 写入 |
| 备注 | 失败原因等 | 写入（追加，不覆盖） |
| 已回复 | 回复状态 | 不再使用 |
| 回复摘要 | 回复内容 | 不再使用 |

## 文件结构

```
email-blast/
├── SKILL.md              # 本文件
├── references/
│   └── resend-guide.md   # Resend 配置指南
└── scripts/
    ├── run.py            # 主编排器（CLI 入口）
    ├── utils.py          # 共享工具函数
    ├── check_env.py      # 环境预检
    ├── read_pending.py   # 读取待发送记录
    ├── send_emails.py    # Resend API 发送
    ├── update_status.py  # 飞书表格状态回写
    └── timezone.py       # 时区判断与发送窗口
```

## 重要提醒

1. **先预检再发送** — 永远不要跳过环境检查，域名未验证直接发只会全部失败
2. **逐条更新状态** — 每发一封立即更新飞书，不要攒到最后批量更新
3. **尊重发送节奏** — 默认的 60-120 秒间隔是经过考虑的，不要建议用户缩短到 10 秒以下
4. **失败不丢记录** — 失败的邮件保持待发送状态，让用户知道还有没发出去的
5. **预演模式** — 首次使用或修改配置后，先用 `--dry-run` 跑一遍确认无误
