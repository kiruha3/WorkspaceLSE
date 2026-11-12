FROM nginx:stable-alpine
COPY frontend/dist/ /usr/share/nginx/html/
COPY infra/stand/nginx.conf /etc/nginx/conf.d/default.conf
