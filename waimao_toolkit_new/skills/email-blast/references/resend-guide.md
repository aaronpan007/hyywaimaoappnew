# Resend 配置指南（新手版）

> 这份指南将手把手带你完成 Resend 的注册、域名验证和环境配置，全程不需要技术背景。
> 整个过程大约 20-30 分钟。

---

## 1. 什么是 Resend？

Resend 是一个专业的邮件发送服务（Email API），类似于"专业版邮箱"。
它可以让我们的系统自动批量发送开发信，并且有专业的发件域名（比如 `sales@yourcompany.com`），而不是用个人邮箱发，这样看起来更专业，也不容易被当成垃圾邮件。

---

## 2. 第一步：注册账号

1. 打开浏览器，访问 **https://resend.com**
2. 点击右上角 **"Sign Up"** 按钮
3. 推荐使用 **Google 账号**注册（点击 "Continue with Google"），最快
   - 如果没有 Google 账号，也可以用邮箱注册（需要验证邮箱）
4. 注册完成后，会自动跳转到 Resend 的控制台（Dashboard）
5. 首次登录可能会让你填写一些基本信息（公司名称等），随便填就行

---

## 3. 第二步：获取 API Key

API Key 是一串密码，让我们的系统能够通过 Resend 发送邮件。

1. 在 Resend 控制台左侧菜单，点击 **"API Keys"**
   - 或直接访问 **https://resend.com/api-keys**
2. 点击 **"Create API Key"** 按钮
3. 填写：
   - **Name**: 随便填，比如 `email-blast`
   - **Permission**: 选择 **"Sending access"**（发送权限就够了，不需要完整权限）
4. 点击 **"Add"**
5. 复制生成的 API Key（格式为 `re_xxxxxxxx` 开头的一串字符）

> **重要提示**: API Key 只显示一次！复制后请妥善保存。如果不小心关掉了，只能删除重新创建。

---

## 4. 第三步：添加并验证域名

这是最关键的一步。**不验证域名就无法发送邮件。**

### 什么是域名？

域名就是你的网站地址，比如 `nongtehub.com`、`prancebuilding.com`。
如果你有自己的公司网站，那个网站地址就是你的域名。
如果你没有域名，需要先去购买一个（阿里云、腾讯云、GoDaddy 等都可以买，一年几十块）。

### 4.1 在 Resend 添加域名

1. 在 Resend 控制台左侧菜单，点击 **"Domains"**
   - 或直接访问 **https://resend.com/domains**
2. 点击 **"Add Domain"**
3. 输入你的域名（比如 `nongtehub.com`），点击 **"Add"**
4. 此时 Resend 会显示一组 **DNS 记录**，你需要把这些记录添加到你的域名管理面板

### 4.2 DNS 记录是什么？

简单说，DNS 记录就是告诉全世界"这个域名是合法的邮件发件人"。
Resend 会给你 4 类记录，每一类都有不同的作用：

| 记录类型 | 作用 | 重要程度 |
|---------|------|---------|
| **MX** | 接收退信通知 | 可选 |
| **SPF** | 证明你有权从该域名发邮件 | 必须 |
| **DKIM** | 邮件数字签名，防止伪造 | 必须 |
| **DMARC** | 邮件认证策略（Google/Yahoo/Microsoft 要求） | 必须 |

### 4.3 方法 A：自动配置（Cloudflare 用户推荐）

如果你的域名使用了 **Cloudflare** 管理 DNS（很多域名默认就走 Cloudflare），可以一键配置：

1. 在 Resend 添加域名后，点击 **"Add DKIM record automatically"** 或类似的一键配置按钮
2. Resend 会自动通过 Cloudflare API 添加所有 DNS 记录
3. 等待几分钟，点击 **"Verify DNS Records"** 验证

### 4.4 方法 B：手动配置（通用方法）

如果你不确定域名托管在哪里，或者不用 Cloudflare，需要手动添加：

#### 第一步：找到你的 DNS 管理面板

- **阿里云（万网）**: 登录阿里云控制台 → 域名 → 解析设置
- **腾讯云**: 登录腾讯云控制台 → 域名注册 → 我的域名 → 解析
- **Cloudflare**: 登录 Cloudflare → 选择域名 → DNS
- **GoDaddy**: 登录 GoDaddy → My Products → DNS
- **Namecheap**: 登录 Namecheap → Domain List → Manage → Advanced DNS

如果找不到，可以在搜索引擎搜"你的域名服务商 + DNS 设置"。

#### 第二步：逐条添加记录

在 Resend 显示的 DNS 记录列表中，每条记录有以下信息：
- **Type**: 记录类型（MX / TXT / CNAME）
- **Name**: 主机记录/名称
- **Value**: 记录值

按照 Resend 显示的内容，在你的 DNS 管理面板中**逐条添加**：

**MX 记录**（接收退信）:
- 类型: MX
- 名称/主机: 填 Resend 给的值（通常是 `send` 或 `@`）
- 值/指向: 填 Resend 给的邮件服务器地址
- 优先级: 填 Resend 给的数值

**SPF 记录**（发送权限）:
- 类型: TXT
- 名称/主机: `@`
- 值/内容: `v=spf1 include:... ~all`（完整复制 Resend 给的内容）

**DKIM 记录**（邮件签名）:
- 类型: CNAME（Resend 可能显示为 TXT）
- 名称/主机: 填 Resend 给的值（通常以 `resend._domainkey` 开头）
- 值/指向: 填 Resend 给的目标地址

**DMARC 记录**（认证策略 — Google/Yahoo/Microsoft 要求大发件人必须配置）:
- 类型: TXT
- 名称/主机: `_dmarc`
- 值/内容: `v=DMARC1; p=none; rua=mailto:dmarc@你的域名`
- 如果 Resend 提供的 rua 地址不同，以 Resend 为准
- 如果 DNS 面板已有 DMARC 记录，请更新为 Resend 提供的值

> **注意**: DNS 记录的"值"字段可能很长，请确保**完整复制**，不要遗漏任何字符。

#### 第三步：验证域名

添加完所有 DNS 记录后：
1. 回到 Resend 的域名页面
2. 点击 **"Verify DNS Records"**
3. 通常几分钟到几小时内就能验证通过
4. 验证通过后，域名旁边会显示绿色勾号

> **如果验证失败**:
> - 检查每条记录是否**完全一致**（包括最后的点号）
> - DNS 传播需要时间，等 10-30 分钟再试
> - 用 https://www.whatsmydns.net 检查 DNS 是否已生效

---

## 5. 第四步：配置环境变量

完成以上步骤后，你需要把 API Key 和邮箱信息告诉我们的系统。

在项目根目录的 `.env` 文件中添加以下 3 个变量：

```env
# Resend API 密钥（从第二步获取）
RESEND_API_KEY=re_xxxxxxxx

# 发件邮箱（系统会自动帮你拼装，格式为：品牌名 <前缀@域名>）
FROM_EMAIL=PRANCE Building <sales@nongtehub.com>

# 回复邮箱（客户回复开发信时会发到这个地址）
REPLY_TO_EMAIL=yourname@gmail.com
```

### 说明

- **RESEND_API_KEY**: 替换为你在第 3 步复制的 API Key
- **FROM_EMAIL**: 首次使用时系统会自动引导你配置，格式为 `品牌名 <前缀@你的域名>`
  - 品牌名: 从你的公司档案中自动提取
  - 前缀: 可选 `sales`（销售）/ `info`（信息）/ `contact`（联系）
  - 域名: 你在 Resend 验证的域名
- **REPLY_TO_EMAIL**: 你平时用的邮箱，客户回复开发信时会发到这里

---

## 6. 第五步：验证配置

配置好 `.env` 文件后，运行环境预检确认一切正常：

```bash
python E:\hyyskill\.claude\skills\email-blast\scripts\run.py --check-env
```

如果所有检查都通过，就可以开始发送邮件了！

建议首次使用时先运行预演模式（不会真正发送邮件）：

```bash
python E:\hyyskill\.claude\skills\email-blast\scripts\run.py --dry-run
```

---

## 7. 常见问题 FAQ

### Q1: 发送失败提示"域名未验证"

**原因**: DNS 记录没有添加完整，或者还没生效。

**解决**:
1. 回到 Resend 域名页面，检查每条 DNS 记录的状态
2. 确认 SPF 和 DKIM 记录已添加（这是必须的）
3. 如果刚添加，等 10-30 分钟让 DNS 传播
4. 重新点击 "Verify DNS Records"

### Q2: 邮件进了客户的垃圾箱

**原因**: 新域名的发信信誉还没建立起来，这是正常现象。

**建议**:
- **第一天**: 只发 5-10 封
- **第二天**: 可以发 10-20 封
- **之后**: 逐步增加到每天 50 封
- 确保收件人是真实有效的邮箱
- 避免发送到大量无效地址（会损害域名信誉）
- 让客户把你的邮箱加到通讯录/白名单

### Q3: 提示"API 限流"

**原因**: 发送频率超过了 Resend 的限制。

**解决**: 增大邮件间隔时间，比如 `--delay-min 120 --delay-max 300`

### Q4: 我的域名 DNS 在哪里配置？

**查找方法**:
1. 查看你购买域名时的服务商（阿里云、腾讯云、GoDaddy 等）
2. 登录服务商网站，找到"域名管理"或"DNS 解析"
3. 如果域名托管在其他地方（比如 Cloudflare），需要去那个平台配置
4. 不确定的话，可以用 https://who.is 查询域名的 NS 记录，就知道 DNS 托管在哪里了

### Q5: 想用个人邮箱发（如 @gmail.com）

Resend 支持通过连接 Gmail 账号发送，但需要额外配置，而且每天只能发很少的邮件。
**强烈建议使用自定义域名**，更专业且没有发送限制。

### Q6: 免费版有什么限制？

Resend 免费版的主要限制：
- 每天最多发送 **100 封**邮件
- 每月最多发送 **3,000 封**邮件
- 只能验证 **1 个域名**

对于刚开始做外贸开发的用户来说，免费版完全够用。
如果后续需要更大发送量，可以升级到 Pro 版（$20/月，每天 1,000 封）。
