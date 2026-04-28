---
name: customer-acquisition
description: |
  B2B客户获取自动化工具。触发条件：
  - 用户提到"开发客户"、"找客户"、"潜在客户"、"客户获取"
  - 用户提到"找公司"、"找供应商"、"找分销商"、"找批发商"、"找制造商"
  - 用户提到"lead generation"、"prospecting"、"customer acquisition"
  - 用户提到"开发海外客户"、"外贸开发"、"拓客"
  - 用户要求搜索某个行业的公司信息
---

# Customer Acquisition Skill

本 Skill 自动化 B2B 客户获取全流程：搜索公司 → 抓取官网 → AI分析 → 存储到飞书表格。

脚本路径：`__SKILL_DIR__/customer-acquisition/scripts/`

## 首次配置

首次使用本 Skill 或环境变量缺失时，按以下流程引导用户完成配置：

1. 检查环境变量状态：
   ```bash
   python __SKILL_DIR__/customer-acquisition/scripts/run.py --setup
   ```
2. 如果返回 `status: "ok"`，跳过配置，直接进入核心流程。
3. 如果 `missing_vars` 不为空，逐个使用 AskUserQuestion 向用户收集值：
   - 展示 `description` 和 `hint` 引导用户输入
   - 收集到值后立即写入：
     ```bash
     python __SKILL_DIR__/customer-acquisition/scripts/run.py --setup KEY=VALUE
     ```
4. 所有变量配置完成后，再次运行 `--setup` 确认 status 为 "ok"。

## Step 1: 识别意图 & 收集参数

当用户触发此 Skill 时，**主动引导**收集以下参数。用户已提供的不重复问，缺少的逐个确认：

| 参数 | 必填 | 引导话术 |
|------|------|----------|
| `--industry` | 是 | "您要搜索哪个行业？比如 LED、ceiling aluminum、solar panel" |
| `--country` | 是 | "目标国家或地区是哪里？比如 USA、Germany、UK" |
| `--keywords` | 否 | "要找什么类型的公司？比如 manufacturer（制造商）、distributor（分销商）、wholesaler（批发商），多个用逗号分隔" |
| `--num` | 否 | "要找多少家公司？默认 30 家" |
| `--my-profile` | 推荐 | 如已有 company-profile 档案会自动加载，无需手动提供 |
| `--my-company` | 条件 | 如未加载 profile，则询问"您公司的名称是什么？" |
| `--my-products` | 条件 | 如未加载 profile，则询问"您公司主要做什么产品或服务？" |

**company-profile 联动**：如果 company-profile skill 已产出 `profile.json`（默认路径 `__SKILL_DIR__/company-profile/profile.json`），AI 分析阶段会自动加载，将产品线、核心竞争力、代表性案例、独特卖点、资质认证、合作模式、客户匹配指南等丰富信息注入 AI prompt，大幅提升 `business_match_points` 和 `outreach_suggestion` 的分析质量。加载 profile 后无需手动提供 `--my-company` 和 `--my-products`。

**示例对话**：

```
用户: 我想开发美国的LED客户，帮我找一些做wholesale的

Claude: 好的，我来帮您搜索美国的 LED 行业 wholesale 类型公司。

要找多少家公司？默认 30 家。

检测到已有 company-profile 档案，AI 分析阶段将自动加载公司画像数据，无需手动提供公司信息。
```

```
用户: 20家就行

Claude: 收到！参数确认：
- 行业: LED
- 国家: USA
- 关键词: wholesale
- 数量: 20
- 公司画像: 已自动加载

开始搜索...
```

**无 profile 时的对话**（company-profile 未产出时）：

```
用户: 我想开发德国的solar panel客户

Claude: 好的，我来帮您搜索德国的 solar panel 行业公司。

要找多少家公司？默认 30 家。

未检测到 company-profile 档案，请提供您公司的名称和主要产品，AI 会据此做更精准的匹配分析。
```

## Step 2: 运行数据收集（Phase 1-3）

参数确认后，执行以下命令：

```bash
cd __SKILL_DIR__/customer-acquisition/scripts

python run.py \
  --industry "LED" \
  --country "USA" \
  --keywords "wholesale" \
  --num 20 \
  --platform csv \
  --keep-intermediate
```

> 注：如未检测到 company-profile，需手动添加 `--my-company "公司名" --my-products "产品描述"`。

**注意**：先用 `--platform csv` 完成数据收集，飞书存储在下一步单独处理。

### 耗时预估

提前告知用户：
- Phase 1 搜索: ~30秒
- Phase 2 抓取: 5-10分钟（30家约10分钟，每家10-20秒）
- Phase 3 AI分析: 3-5分钟

### 错误处理

- 如果 run.py 报错 `SERPER_API_KEY not set` → 检查 `<project-root>/.env`
- 如果 Phase 1 找到 0 家 → 建议用户换关键词或放宽条件
- 如果 Phase 1 找到不足目标数量 → 告知用户实际数量，询问是否继续
- 如果 Phase 2 部分失败 → 正常现象，继续即可
- 如果 Phase 3 AI 超时 → 自动重试，无需干预

## Step 3: 飞书表格存储

> **重要：只能使用 lark-cli，严禁使用飞书 API**
>
> - **严禁**使用飞书 OpenAPI、`lark-base` skill 或其他任何飞书 API 方式创建/操作表格
> - 飞书 API 创建的表格**列顺序错乱、有空行、格式不正确**，无法与后续流程兼容
> - **必须且只能**通过 `lark-cli` 命令行工具操作飞书多维表格
> - 如果 lark-cli 未授权，**必须先完成授权**，不能绕过

数据收集完成后，**主动询问**用户是否需要存到飞书表格：

```
数据收集完成！共找到 X 家公司，其中 Y 家有邮箱。

要把结果存到飞书多维表格吗？
```

如果用户选择存飞书，按以下流程操作：

### 3a. 检查飞书授权

```bash
cd __SKILL_DIR__/customer-acquisition/scripts
python run.py --check-auth
```

根据返回结果，严格按以下分支处理：

#### 分支 A：`OK: authenticated as user/bot`
授权正常，跳到 3b 选择目标表格。

#### 分支 B：`NOT OK: lark-cli not installed`
lark-cli 未安装。**这一步是安装工具，不是授权**。执行：

```bash
npm install -g @larksuite/cli
```

安装完成后，**不要**尝试创建表格或用飞书 API 替代。直接回到分支 C 执行授权。

#### 分支 C：`NOT OK: not_authenticated`
lark-cli 已安装但未授权。**这一步才是获取授权链接**。执行：

```bash
cd __SKILL_DIR__/customer-acquisition/scripts
python run.py --get-auth-url
```

将返回的 `verification_url` 展示给用户，明确告知：
```
请在浏览器中打开这个链接完成飞书授权（有效期 10 分钟）。
授权完成后告诉我，我会再次检查。
```

等待用户确认后，重新运行 `--check-auth`。如果仍失败，再次执行 `--get-auth-url` 获取新链接。

> **注意**：`--get-auth-url` 每次调用都会生成新链接，旧链接会失效。不要重复展示旧链接。

### 3b. 选择目标表格

```bash
python run.py --show-config
```

**情况 A: 已有保存的表格**

如果 config 中有 base_token 和 table_id：
```
您上次使用的表格是「{table_name}」，要继续用这个表格吗？
还是换一个表格？
```

- 用户说"用这个" → 直接跳到 3c 写入
- 用户说"换一个" → 进入情况 B

**情况 B: 没有保存的表格 / 用户要换**

```
请提供飞书多维表格链接，或者我帮您创建一个新表格。

1. 如果您已有表格，直接粘贴链接（格式如 https://xxx.feishu.cn/base/TOKEN?table=ID）
2. 如果要新建，告诉我表格名称，我帮您创建
```

- **用户提供链接** → 解析并保存：

```bash
python run.py --save-feishu-link "https://xxx.feishu.cn/base/TOKEN?table=ID"
```

- **用户要新建** → 通过 lark-cli 创建表格：

```bash
python run.py --create-table "客户获取列表"
```

如果创建失败，回退方案：
```
自动创建失败了。您可以在飞书中手动创建一个多维表格，然后把链接发给我。
```

> **再次提醒**：严禁使用飞书 API（`lark-base` skill 等）创建表格。如果 `--create-table` 失败，只能让用户手动创建后粘贴链接。

### 3c. 写入飞书

表格就绪后，执行 Phase 4 存储：

```bash
python run.py \
  --from-phase 4 \
  --to-phase 4 \
  --platform feishu \
  --industry "LED" \
  --country "USA" \
  --keywords "wholesale" \
  --num 20 \
  --keep-intermediate
```

**注意**：`--from-phase 4 --to-phase 4` 只执行存储阶段，使用已有的 Phase 3 输出文件。

- 如果写入成功 → 告知用户
- 如果写入失败 → 自动降级为 CSV 导出，告知用户：

```
飞书写入遇到问题，已自动导出为 CSV 文件：{path}
```

## Step 4: 展示结果汇总

所有步骤完成后，向用户展示汇总报告：

### 1. 数据概览

```
客户获取报告
行业: LED | 地区: USA
搜索公司: 20 家
成功抓取: 18 家
AI分析完成: 18 家
有邮箱: 15 家 | 有电话: 12 家
```

### 2. 高匹配度客户（Top 5）

从 run.py 的输出中提取 `_market_match == "High"` 的公司，展示：

```
高匹配度客户:
1. [公司名] - [公司角色] | 邮箱: x@x.com
   匹配点: [business_match_points 前100字]
```

### 3. 全部结果表格

以 Markdown 表格展示（取前 20 家）：

| # | 公司 | 角色 | 匹配 | 邮箱 | 电话 |
|---|------|------|------|------|------|
| 1 | ... | ... | ... | ... | ... |

### 4. 输出位置

告知用户：
- 飞书表格链接（如果存了飞书）
- CSV 文件路径（如果导出了 CSV）
- 数据已保存到飞书配置，下次可以直接使用

## 高级用法

### 断点续跑

如果流程中断（比如 Phase 2 超时），可以从断点继续：

```bash
python run.py --from-phase 3 \
  --industry "LED" --country "USA" --keywords "wholesale" \
  --num 20 \
  --platform csv --keep-intermediate
```

### 单独运行某个阶段

```bash
# 只搜索
python run.py --from-phase 1 --to-phase 1 --industry "LED" --country "USA" --num 10

# 只AI分析（已有抓取数据）
python run.py --from-phase 3 --to-phase 3 --industry "LED" --country "USA" --num 10
```

### 飞书工具命令

```bash
python run.py --check-auth          # 检查飞书授权状态
python run.py --get-auth-url        # 获取飞书授权链接（非阻塞）
python run.py --show-config         # 查看已保存的表格配置
python run.py --save-feishu-link URL  # 保存表格链接
python run.py --create-table "名称"    # 创建新表格
```

## Prerequisites

### API Keys（`<project-root>/.env`）

```
SERPER_API_KEY=your_key
REPLICATE_API_TOKEN=your_token
```

### Python 依赖

```bash
pip install requests python-dotenv replicate playwright
python -m playwright install chromium
```

### 飞书 CLI（可选，用于飞书存储）

```bash
npm install -g @larksuite/cli
python run.py --get-auth-url   # 获取授权链接，在浏览器中完成
```
