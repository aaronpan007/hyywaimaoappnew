# Waimao Toolkit — 外贸客户开发 AI 工具包

一套为 AI Agent（Claude Code、OpenClaw、OpenCode 等）设计的**外贸客户开发全流程自动化工具**。从找客户、写开发信到批量发送，全部由 AI 驱动完成。

## 工作流程

```
company-profile    customer-acquisition    email-craft       email-blast
 整理公司资料  →     搜索目标客户      →   撰写开发信    →    批量发送
  (素材底座)        (数据收集)           (AI生成)          (执行发送)
```

## 包含的 Skill

| Skill | 功能 | 依赖 |
|-------|------|------|
| **company-profile** | 构建企业能力档案（产品、案例、卖点等） | Python + requests |
| **customer-acquisition** | 搜索目标公司、抓取官网、AI分析匹配度 | Serper API + Replicate API |
| **email-craft** | 根据客户画像自动生成个性化开发信 | Replicate API + lark-cli |
| **email-blast** | 批量发送开发信，自动更新飞书状态 | Resend API + lark-cli |

共享模块：`_shared/setup_env.py` — 统一的环境变量管理（--setup 首次配置流程）。

## 快速安装

### Claude Code（默认）

```bash
# 1. 克隆或下载 waimao_toolkit_new 到你的项目目录
cd /path/to/your/project

# 2. 运行安装脚本
bash waimao_toolkit_new/install.sh
```

### 其他 AI Agent

```bash
# OpenCode / OpenClaw / Codex 等
bash waimao_toolkit_new/install.sh --target-dir .openode/skills

# 或自定义目录
bash waimao_toolkit_new/install.sh --target-dir .my-agent/skills
```

### Windows

```cmd
install.bat
install.bat --target-dir .openode\skills
```

### 安装后配置

1. **编辑 `.env` 文件**，填入你的 API Key：
   ```
   SERPER_API_KEY=your_key
   REPLICATE_API_TOKEN=your_token
   RESEND_API_KEY=your_key
   FROM_EMAIL=Brand Name <sales@yourdomain.com>
   ```

2. **重启 AI Agent** 使新 Skill 生效

3. （可选）安装 Python 依赖：
   ```bash
   pip install requests python-dotenv replicate playwright
   python -m playwright install chromium
   ```

4. （可选）安装飞书 CLI（用于飞书表格存储）：
   ```bash
   npm install -g @larksuite/cli
   ```

## 文件结构

```
waimao_toolkit_new/
├── README.md              # 本文件
├── .env.example           # 环境变量模板（合并所有 Skill）
├── install.sh             # Linux/Mac 安装脚本
├── install.bat            # Windows 安装脚本
└── skills/
    ├── _shared/
    │   └── setup_env.py   # 共享环境变量管理模块
    ├── company-profile/
    │   ├── SKILL.md
    │   ├── profile.json.example
    │   ├── references/
    │   │   └── json-schema.md
    │   └── scripts/
    │       └── scrape_website.py
    ├── customer-acquisition/
    │   ├── SKILL.md
    │   ├── .env.example
    │   └── scripts/
    │       ├── run.py
    │       ├── search_companies.py
    │       ├── scrape_websites.py
    │       ├── analyze_companies.py
    │       ├── store_results.py
    │       ├── utils.py
    │       └── config.json.example
    ├── email-craft/
    │   ├── SKILL.md
    │   ├── .env.example
    │   ├── scripts/
    │   │   ├── run.py
    │   │   ├── generate_emails.py
    │   │   ├── read_feishu.py
    │   │   ├── write_feishu.py
    │   │   ├── utils.py
    │   │   └── config.json.example
    │   └── references/
    │       └── README.md
    └── email-blast/
        ├── SKILL.md
        ├── .env.example
        ├── scripts/
        │   ├── run.py
        │   ├── send_emails.py
        │   ├── check_env.py
        │   ├── timezone.py
        │   ├── update_status.py
        │   ├── read_pending.py
        │   └── utils.py
        └── references/
            └── resend-guide.md
```

## 使用方法

安装完成后，直接用自然语言与 AI Agent 对话即可：

- **"帮我建立公司档案"** → 触发 company-profile
- **"找美国做 LED 的 wholesale 客户"** → 触发 customer-acquisition
- **"给这些客户写开发信"** → 触发 email-craft
- **"发送这些开发信"** → 触发 email-blast

首次使用每个 Skill 时，AI 会自动引导你完成 API Key 配置（`--setup` 流程）。

## API Key 获取

| Key | 用途 | 获取地址 |
|-----|------|----------|
| `SERPER_API_KEY` | Google 搜索公司 | https://serper.dev （免费 2500次/月） |
| `REPLICATE_API_TOKEN` | AI 分析匹配 + 生成开发信 | https://replicate.com/account/api-tokens |
| `RESEND_API_KEY` | 邮件发送 | https://resend.com/api-keys |
| `FROM_EMAIL` | 发件人邮箱 | 需在 Resend 验证域名 |

## 注意事项

- 本工具包不包含任何用户特定数据（profile.json、config.json、CSV 等）
- 安装脚本会自动将 SKILL.md 中的路径占位符替换为实际安装路径
- `<project-root>` 占位符需用户根据实际项目路径自行理解（指向项目根目录）
- 飞书 CLI 为可选依赖，不安装时可降级为 CSV 导出
