# 部署上线指南

> 前端：`https://clientconnet.com`（Vercel）
> 后端：`https://api.clientconnet.com`（腾讯云 Nginx + PM2）
> 数据库：PostgreSQL 17（腾讯云同服务器）

---

## Step 0：本地代码修改

已完成的本地修改（`scraper.py` 已改为跨平台 Chromium 路径，`ecosystem.config.cjs` 已创建），提交代码：

```bash
git add backend/app/utils/scraper.py backend/ecosystem.config.cjs
git commit -m "deployment: cross-platform Chromium path + PM2 config"
git push origin main
```

---

## 一、腾讯云服务器环境搭建

SSH 登录服务器后，依次执行以下步骤。

### 1. 系统基础依赖

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl wget git unzip build-essential libssl-dev libffi-dev libpq-dev
```

### 2. PostgreSQL 17

```bash
# 添加官方源
sudo sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -
sudo apt update
sudo apt install -y postgresql-17
sudo systemctl enable postgresql && sudo systemctl start postgresql

# 设置密码（替换 <YOUR_DB_PASSWORD> 为你的数据库密码）
sudo -u postgres psql -c "ALTER USER postgres PASSWORD '<YOUR_DB_PASSWORD>';"
sudo -u postgres psql -c "CREATE DATABASE waimao;"
```

**配置远程访问**（Better Auth 需要从 Vercel 直连）：

```bash
# 编辑 postgresql.conf：监听所有 IP
sudo sed -i "s/#listen_addresses = 'localhost'/listen_addresses = '*'/" /etc/postgresql/17/main/postgresql.conf

# 编辑 pg_hba.conf：允许 Vercel serverless IP 段连接
# 先获取 Vercel IP 段：https://vercel.com/changelog/vercel-serverless-functions-now-have-static-ips
# 在 pg_hba.conf 末尾添加（替换 <YOUR_DB_PASSWORD>）：
echo "host  waimao  postgres  76.76.21.0/24  md5" | sudo tee -a /etc/postgresql/17/main/pg_hba.conf
# 如果需要开发调试，也可以临时允许所有 IP：
# echo "host  all  all  0.0.0.0/0  md5" | sudo tee -a /etc/postgresql/17/main/pg_hba.conf

sudo systemctl restart postgresql
```

### 3. Python 3.13（via pyenv）

```bash
# 安装 pyenv 构建依赖
sudo apt install -y make libbz2-dev libreadline-dev libsqlite3-dev libncurses5-dev \
    libncursesw5-dev xz-utils tk-dev liblzma-dev zlib1g-dev

curl https://pyenv.run | bash

# 添加到 shell（按 pyenv 安装提示执行）
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
echo '[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
echo 'eval "$(pyenv init -)"' >> ~/.bashrc
source ~/.bashrc

pyenv install 3.13
pyenv global 3.13
python --version    # 确认 3.13.x
pip install --upgrade pip
```

### 4. Node.js 20

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
node --version    # 确认 v20.x
```

### 5. Nginx + Certbot + PM2

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
sudo systemctl enable nginx
sudo npm install -g pm2
```

### 6. Playwright Chromium

```bash
sudo npx playwright install-deps chromium    # 系统级依赖（libx11 等）
npx playwright install chromium               # 浏览器二进制
```

### 7. 防火墙（UFW）

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'        # 80 + 443
sudo ufw allow 5432/tcp             # PostgreSQL 远程（Vercel Better Auth 需要）
sudo ufw --force enable
sudo ufw status
```

---

## 二、后端部署

### 1. 克隆代码

```bash
sudo mkdir -p /var/www && sudo chown $USER:$USER /var/www
cd /var/www && git clone https://github.com/<your-username>/hyyskill.git hyyskill
cd /var/www/hyyskill
```

### 2. 安装 Python 依赖

```bash
cd /var/www/hyyskill/backend
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
```

### 3. 创建生产环境变量

```bash
cat > /var/www/hyyskill/.env << 'ENVEOF'
# API Keys
SERPER_API_KEY=<你的 Serper API Key>
REPLICATE_API_TOKEN=<你的 Replicate API Token>
REPLICATE_MODEL=openai/gpt-5.2
RESEND_API_KEY=<你的 Resend API Key>
RESEND_WEBHOOK_SECRET=<你的 Resend Webhook Secret>

# Email
MAIL_DOMAIN=clientconnet.com

# Auth（必须与前端完全一致）
BETTER_AUTH_SECRET=JMnI6WRbmVZsZRAUvJlrjFdIW2BLc0V6Wp9AGSPR1Oo

# Database（本机 PostgreSQL）
DATABASE_URL=postgresql+asyncpg://postgres:<YOUR_DB_PASSWORD>@localhost:5432/waimao

# CORS（只允许前端正式域名）
CORS_ORIGINS=https://clientconnet.com,https://www.clientconnet.com
ENVEOF
```

> 替换所有 `<...>` 占位符为实际值。

### 4. 数据库迁移

```bash
cd /var/www/hyyskill/backend
source .venv/bin/activate
PYTHONUTF8=1 python -m alembic upgrade head
```

### 5. PM2 启动

```bash
mkdir -p /var/www/hyyskill/backend/logs
cd /var/www/hyyskill/backend
pm2 start ecosystem.config.cjs
pm2 save
pm2 startup    # 按提示执行输出的 sudo 命令，设置开机自启

# 验证
curl http://127.0.0.1:8000/health
# 应返回: {"status":"ok"}
```

---

## 三、Nginx 反向代理 + SSL

### 1. 申请 SSL 证书

**前提**：DNS A 记录 `api.clientconnet.com → <服务器公网IP>` 已生效。

```bash
# 确认 DNS 解析已生效
dig api.clientconnet.com +short    # 应返回服务器 IP

# 先写一个临时 server block 让 certbot 验证域名
sudo tee /etc/nginx/sites-available/api.clientconnet.com << 'EOF'
server {
    listen 80;
    server_name api.clientconnet.com;
    location / {
        return 200 'ok';
    }
}
EOF
sudo ln -s /etc/nginx/sites-available/api.clientconnet.com /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# 申请证书
sudo certbot certonly --nginx -d api.clientconnet.com

# 启用自动续期
sudo systemctl enable certbot.timer
```

### 2. 正式 Nginx 配置

```bash
sudo tee /etc/nginx/sites-available/api.clientconnet.com << 'EOF'
upstream waimao_backend {
    server 127.0.0.1:8000;
    keepalive 64;
}

server {
    listen 80;
    server_name api.clientconnet.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.clientconnet.com;

    ssl_certificate /etc/letsencrypt/live/api.clientconnet.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.clientconnet.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    client_max_body_size 20M;

    # SSE 支持（关键！关闭缓冲，长超时）
    location / {
        proxy_pass http://waimao_backend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection '';
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }

    access_log /var/log/nginx/api.clientconnet.com.access.log;
    error_log /var/log/nginx/api.clientconnet.com.error.log;
}
EOF

sudo nginx -t && sudo systemctl reload nginx

# 验证 HTTPS
curl -s https://api.clientconnet.com/health
# 应返回: {"status":"ok"}
```

---

## 四、DNS 配置

在域名注册商（阿里云/腾讯云/Cloudflare 等）处添加以下记录：

| 类型 | 名称 | 值 | 说明 |
|------|------|----|------|
| A | `api` | `<腾讯云服务器公网 IP>` | 后端 API |
| A | `@` | `76.76.21.21` | Vercel apex 域名 |
| CNAME | `www` | `cname.vercel-dns.com` | Vercel www |

**Resend 邮件认证 DNS**（如果 `clientconnet.com` 还没在 Resend 验证）：

| 类型 | 名称 | 值 |
|------|------|----|
| TXT | `@` | `v=spf1 include:relay.resend.com ~all` |
| CNAME | `resend._domainkey` | `(由 Resend 控制台提供)` |
| TXT | `_dmarc` | `v=DMARC1; p=none; rua=mailto:dmarc@clientconnet.com` |

---

## 五、前端 Vercel 部署

### 1. 连接 GitHub 仓库

1. 登录 [Vercel Dashboard](https://vercel.com/dashboard)
2. 点击 **Add New → Project**
3. 导入 GitHub 仓库 `hyyskill`
4. **Framework Preset**: Next.js
5. **Root Directory**: `frontend`

### 2. 设置环境变量

在 Vercel 项目的 **Settings → Environment Variables** 中添加：

| 变量名 | 值 |
|--------|----|
| `NEXT_PUBLIC_API_URL` | `https://api.clientconnet.com` |
| `BETTER_AUTH_URL` | `https://clientconnet.com` |
| `BETTER_AUTH_SECRET` | `JMnI6WRbmVZsZRAUvJlrjFdIW2BLc0V6Wp9AGSPR1Oo` |
| `BETTER_AUTH_COOKIE_DOMAIN` | `.clientconnet.com` |
| `BETTER_AUTH_DATABASE_URL` | `postgresql://postgres:<YOUR_DB_PASSWORD>@<服务器公网IP>:5432/waimao` |

> `BETTER_AUTH_DATABASE_URL` 允许 Vercel serverless 函数直连腾讯云 PostgreSQL（用于 session 校验）。

### 3. 绑定自定义域名

1. Vercel Dashboard → 项目 → **Settings → Domains**
2. 添加 `clientconnet.com` 和 `www.clientconnet.com`
3. Vercel 会自动配置 DNS（如已配置 CNAME 指向 `cname.vercel-dns.com`）

### 4. 部署

```bash
# 推送到 main 后 Vercel 自动构建部署
git push origin main
```

或在 Vercel Dashboard 点击 **Redeploy**。

---

## 六、Resend Webhook 配置

1. 登录 [Resend Dashboard](https://resend.com/webhooks)
2. 创建 Webhook，URL 填：`https://api.clientconnet.com/api/emails/resend/webhook`
3. 勾选事件：`email.sent`、`email.delivered`、`email.bounced`、`email.failed`、`email.complained`

后端的 Svix 签名校验会自动验证 `RESEND_WEBHOOK_SECRET`。

---

## 七、跨域 Cookie 认证原理

```
用户在 clientconnet.com 登录
    ↓
Better Auth 写 auth_sessions 表 + 设置 cookie (domain=.clientconnet.com)
    ↓
前端调 api.clientconnet.com
    ↓
浏览器自动携带 .clientconnet.com 域的 cookie
    ↓
后端 dependencies.py 读 cookie → HMAC 验证签名 → 查 DB session → 返回 user_id
```

**关键前提**：
- 前后端 `BETTER_AUTH_SECRET` 完全一致
- `BETTER_AUTH_COOKIE_DOMAIN=.clientconnet.com` 跨子域共享
- Nginx 反代已正确传递 `Host` 头

---

## 八、验证清单

部署完成后，逐项验证：

- [ ] `curl https://api.clientconnet.com/health` 返回 `{"status":"ok"}`
- [ ] `https://clientconnet.com` 正常加载前端页面
- [ ] 注册新账号成功，登录后 cookie domain 为 `.clientconnet.com`
- [ ] 登录后 API 调用携带 cookie（浏览器 DevTools → Network 面板验证）
- [ ] 客户搜索 pipeline 端到端（SSE 流不中断，在 DevTools Network 查看 EventStream）
- [ ] 公司画像 pipeline（Playwright 爬取正常，无超时报错）
- [ ] 开发信撰写 + 预览
- [ ] 批量发送开发信（Resend 真实发送）
- [ ] Resend webhook 回调正常（`pm2 logs` 查看日志）
- [ ] `pm2 logs` 无持续报错
- [ ] `sudo certbot renew --dry-run` 证书续期正常

---

## 九、常用运维命令

```bash
# 查看后端日志
pm2 logs waimao-api

# 重启后端
pm2 restart waimao-api

# 查看后端状态
pm2 status

# 更新代码并重启
cd /var/www/hyyskill && git pull origin main
pm2 restart waimao-api

# 数据库迁移（代码更新 model 后）
cd /var/www/hyyskill/backend
source .venv/bin/activate
PYTHONUTF8=1 python -m alembic upgrade head
pm2 restart waimao-api

# Nginx 日志
sudo tail -f /var/log/nginx/api.clientconnet.com.error.log

# 证书续期（certbot timer 自动处理，手动检查）
sudo certbot renew --dry-run

# PostgreSQL 备份
sudo -u postgres pg_dump waimao > /var/www/hyyskill/backup_$(date +%Y%m%d).sql
```

---

## 十、风险点与注意事项

1. **Playwright Linux 兼容**：`playwright install-deps chromium` 安装系统库是必须的，部署后立即测试爬虫功能
2. **单 worker 限制**：`task_manager.py` 用内存 dict 管理任务，PM2 只能 1 个实例；后续可迁移到 Redis
3. **Vercel → PostgreSQL 直连**：Better Auth 从 Vercel serverless 直连腾讯云 PG，需开放 5432 + pg_hba.conf 允许 Vercel IP 段 `76.76.21.0/24`
4. **SSE 穿透 Nginx**：已配置 `proxy_buffering off` + 300s 超时，确保长连接不中断
5. **端口冲突**：部署前先 `sudo lsof -i :80 -i :443` 确认端口未被其他服务（如宝塔/OpenClaw）占用
6. **pyenv 全局生效**：PM2 通过 bash 启动，确保 `.bashrc` 中有 pyenv 初始化，否则 python 版本不对
