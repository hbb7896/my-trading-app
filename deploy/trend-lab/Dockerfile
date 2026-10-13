FROM node:24-alpine
WORKDIR /app
COPY apps/trend-lab-api/package.json apps/trend-lab-api/server.mjs apps/trend-lab-api/analysis.js apps/trend-lab-api/import.mjs apps/trend-lab-api/supabase-store.mjs apps/trend-lab-api/stock-codes.json ./
COPY apps/trend_lab_flutter/build/web ./web
ENV HOST=0.0.0.0 PORT=8787 DATA_DIR=/data WEB_DIR=/app/web
EXPOSE 8787
CMD ["node", "server.mjs"]
