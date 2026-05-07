module.exports = {
  apps: [{
    name: "waimao-api",
    script: "bash",
    args: "-c 'source .venv/bin/activate && PYTHONUTF8=1 PYTHONUNBUFFERED=1 uvicorn app.main:app --host 127.0.0.1 --port 8000'",
    cwd: "/var/www/hyyskill/backend",
    instances: 1,
    autorestart: true,
    max_restarts: 10,
    restart_delay: 5000,
    log_date_format: "YYYY-MM-DD HH:mm:ss",
    error_file: "/var/www/hyyskill/backend/logs/error.log",
    out_file: "/var/www/hyyskill/backend/logs/out.log",
  }],
};
