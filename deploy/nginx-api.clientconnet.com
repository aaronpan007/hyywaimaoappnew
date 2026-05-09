upstream waimao_backend {
    server 127.0.0.1:8000;
    keepalive 64;
}

upstream waimao_auth {
    server 127.0.0.1:8001;
    keepalive 64;
}

map $http_origin $cors_origin {
    default "";
    "https://clientconnet.com" $http_origin;
    "https://www.clientconnet.com" $http_origin;
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

    location /api/auth/ {
        add_header Access-Control-Allow-Origin $cors_origin always;
        add_header Vary "Origin" always;
        add_header Access-Control-Allow-Methods "GET, POST, PUT, PATCH, DELETE, OPTIONS" always;
        add_header Access-Control-Allow-Headers $http_access_control_request_headers always;
        add_header Access-Control-Allow-Credentials "true" always;
        add_header Access-Control-Max-Age 86400 always;

        if ($request_method = OPTIONS) {
            return 204;
        }

        proxy_pass http://waimao_auth;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
    }

    location / {
        proxy_pass http://waimao_backend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }

    access_log /var/log/nginx/api.clientconnet.com.access.log;
    error_log /var/log/nginx/api.clientconnet.com.error.log;
}
