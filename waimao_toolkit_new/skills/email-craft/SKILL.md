---
description: "定制化开发信批量撰写工具。根据客户公司画像、近期动态、行业属性，结合本公司能力档案，为每个潜在客户生成个性化 cold email。"
triggers:
  - "写开发信"
  - "撰写开发信"
  - "生成开发信"
  - "cold email"
  - "outreach email"
  - "email draft"
  - "给客户写信"
  - "跟进邮件"
  - "开发信撰写"
  - "批量写邮件"
  - "定制化邮件"
  - "写邮件"
  - "email craft"
---

# Email Craft Skill — 定制化开发信批量撰写

## 概述

根据飞书表格中的客户数据（公司画像、AI分析摘要、业务匹配点、开发建议），结合 `company-profile` 中的本公司能力档案，为每个潜在客户生成"看起来像认真做过研究"的定制化开发信。

## 首次配置

首次使用本 Skill 或环境变量缺失时，按以下流程引导用户完成配置：

1. 检查环境变量状态：
   ```bash
   python __SKILL_DIR__/email-craft/scripts/run.py --setup
   ```
2. 如果返回 `status: "ok"`，跳过配置，直接进入核心流程。
3. 如果 `missing_vars` 不为空，逐个使用 AskUserQuestion 向用户收集值：
   - 展示 `description` 和 `hint` 引导用户输入
   - 收集到值后立即写入：
     ```bash
     python __SKILL_DIR__/email-craft/scripts/run.py --setup KEY=VALUE
     ```
4. 所有变量配置完成后，再次运行 `--setup` 确认 status 为 "ok"。

## 核心流程

1. **确定数据源** — 自动检测 customer-acquisition 刚用过的表格，或用户提供飞书链接
2. **检查/创建字段** — 确保"开发信"和"邮件主题"字段存在
3. **读取客户记录** — 过滤已有邮箱且开发信为空的记录
4. **展示客户列表** — 用户选择要写开发信的客户
5. **AI 生成开发信** — 逐个调用 Replicate API 生成个性化邮件
6. **写回飞书** — 将邮件主题和正文写回飞书表格

## 执行步骤

### Step 1: 确定数据源 & 收集参数

1. 检查 customer-acquisition 的 config.json 是否在 24 小时内使用过：
   ```bash
   python __SKILL_DIR__/email-craft/scripts/run.py --show-config
   ```
   - 如果自动检测到 → 告知用户"检测到刚使用过的客户表格：{table_name}"
   - 未检测到 → 要求用户提供飞书表格链接

   **表格记忆机制**: 每次使用表格时，email-craft 会自动将表格信息（含行业标签+日期）保存到 `config.json` 的 history 列表中。email-blast 可以读取此历史来选择发信表格。

2. 询问用户：
   - 邮件语言（默认英文 `--language en`，中文 `--language cn`）
   - 表格标签（可选，如 `--label "美国吊顶公司"`；不指定则自动从数据中提取行业关键词）
   - 是否有参考邮件要添加到 `references/` 目录

3. 检查飞书授权：
   ```bash
   python __SKILL_DIR__/email-craft/scripts/run.py --check-auth
   ```

   - 如果返回 `OK: authenticated as user` → 授权正常，继续
   - 如果返回 `NOT OK: not_authenticated` → 运行 `--get-auth-url` 获取授权链接，将链接展示给用户，等待用户在浏览器中完成授权后，再次运行 `--check-auth` 确认
   - 如果返回 `NOT OK: lark-cli not installed` → 引导安装 `npm install -g @larksuite/cli`，然后运行 `--get-auth-url`

### Step 2: 展示客户列表 & 选择

不带选择参数运行，展示可写开发信的客户列表：
```bash
python __SKILL_DIR__/email-craft/scripts/run.py
```

向用户展示输出结果，让用户选择：
- 全部生成：`--all`
- 指定客户：`--select recXXX,recYYY`
- 重新生成：`--regenerate recXXX`

### Step 3: 运行开发信生成

根据用户选择构建命令：

**全部生成：**
```bash
python __SKILL_DIR__/email-craft/scripts/run.py --language en --all
```

**指定客户：**
```bash
python __SKILL_DIR__/email-craft/scripts/run.py --language en --select recXXX,recYYY
```

**预览模式（不写入飞书）：**
```bash
python __SKILL_DIR__/email-craft/scripts/run.py --language en --select recXXX --dry-run
```

**重新生成：**
```bash
python __SKILL_DIR__/email-craft/scripts/run.py --language en --regenerate recXXX
```

### Step 4: 展示结果

1. 汇总：生成了 X 封，成功写入 Y 封
2. 展示前 3 封邮件的 subject + body 前 200 字
3. 告知用户可在飞书表格中查看完整内容

### Step 5: 参考邮件管理

用户可随时提供优秀开发信范文。Claude 应：
1. 保存到 `__SKILL_DIR__/email-craft/references/` 目录
2. 文件格式：`.txt` 或 `.md`，包含完整的 subject + body
3. 去除敏感信息（真实公司名等）
4. 下次生成时 AI 自动学习风格

## CSV 模式（飞书不可用时）

当飞书 CLI 授权未通过或飞书不可用时，可以用 CSV 文件替代飞书作为数据通道。

### 数据流

```
customer-acquisition → CSV (15列) → email-craft --csv → CSV (17列，含开发信) → email-blast --pipeline-csv → CSV (状态已更新)
```

### 使用方法

```bash
# 读取 CSV 中的客户记录，展示列表（不生成）
python __SKILL_DIR__/email-craft/scripts/run.py --csv customers.csv

# 为所有无开发信的客户生成
python __SKILL_DIR__/email-craft/scripts/run.py --csv customers.csv --all --language en

# 为指定行生成（行号从 0 开始）
python __SKILL_DIR__/email-craft/scripts/run.py --csv customers.csv --select 0,2,5 --language en

# 重新生成（忽略已有开发信）
python __SKILL_DIR__/email-craft/scripts/run.py --csv customers.csv --regenerate 0,1 --language en

# 预览模式
python __SKILL_DIR__/email-craft/scripts/run.py --csv customers.csv --all --dry-run --language en
```

### CSV 格式要求

- 编码：UTF-8 with BOM（`utf-8-sig`）
- 表头：中文表头（与飞书字段名一致）或英文 key 均可
- 必须包含的列：`公司名称`（company_name）、`邮箱`（email）
- customer-acquisition 的 `export_csv()` 已输出 14 列标准格式，可直接使用

### 降级规则

> **重要：即使飞书不可用，开发信生成也必须走 `generate_emails.py` 脚本（Replicate API），而不是让 AI agent 自己写邮件。**
>
> 如果因任何原因无法调用脚本、AI agent 需要自行撰写邮件，必须遵守以下规则：
>
> 1. **纯文本输出** — 严禁 Markdown 格式标记（`**粗体**`、`## 标题`、`- 列表`、`[链接](URL)` 等）
> 2. **禁止模板腔** — 不用 "Hope you are well"、"We are a leading company" 等空洞开场白
> 3. **禁止分段标题** — 不用 "## About Us"、"## Why Choose Us" 之类的结构化标题
> 4. **长度控制** — 英文 150-300 词，中文 200-400 字，宁可短不要长
> 5. **语气自然** — 像有经验的商务人士直接沟通，不要营销话术
> 6. **禁止编造** — 只用客户数据中已有的信息
> 7. **CTA 轻量** — 询问兴趣为主，不要硬性推销

## 高级用法

| 参数 | 说明 |
|------|------|
| `--csv FILE` | 从 CSV 文件读取客户（飞书不可用时使用） |
| `--dry-run` | 只生成不写入飞书，用于预览 |
| `--regenerate recXXX` | 重新生成特定客户（忽略已有开发信）|
| `--language cn` | 生成中文版本 |
| `--feishu-link LINK` | 手动指定飞书表格链接 |
| `--profile PATH` | 指定 profile.json 路径 |
| `--label LABEL` | 手动指定表格标签（如 `--label "美国吊顶公司"`，默认自动提取） |

## AI 生成规则（7条）

1. 开头自然且有针对性 — 1句简短寒暄/引入（提及对方项目或动态），禁止 "Hope you are well" 等空洞模板
2. 中间说明匹配理由 — 客户需求 × 我司能力交叉分析
3. 案例必须相关 — 智能选择与客户行业/地区最相关的 1-2 个案例
4. 语气专业自然 — 像有经验的商务人士直接沟通
5. CTA 要轻量 — 询问兴趣为主，不要硬性推销
6. 禁止编造 — 只用客户数据中已有的信息
7. 长度控制 — 英文 150-300 词，中文 200-400 字

## 文件结构

```
email-craft/
├── SKILL.md              # 本文件
├── references/
│   └── README.md         # 参考邮件说明
└── scripts/
    ├── run.py            # 主编排器（CLI 入口）
    ├── utils.py          # 共享工具函数
    ├── csv_io.py         # CSV 读写封装
    ├── read_feishu.py    # 读取飞书客户记录
    ├── generate_emails.py # AI 开发信生成
    └── write_feishu.py   # 写回飞书表格
```

## 依赖

- `python-dotenv` — 环境变量加载
- `replicate` — AI 模型调用（openai/gpt-5.2）
- `lark-cli` — 飞书多维表格操作
- `company-profile/profile.json` — 本公司能力档案（自动检测）
