FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:1.27-alpine

ENV API_BASE_URL=http://backend:8000 \
    DOCS_URL=http://backend:8000/docs

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY docker-entrypoint.sh /docker-entrypoint.sh
COPY --from=builder /app/dist /usr/share/nginx/html
COPY --from=builder /app/public/runtime-config.js /usr/share/nginx/html/runtime-config.js

RUN chmod +x /docker-entrypoint.sh

EXPOSE 80

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
