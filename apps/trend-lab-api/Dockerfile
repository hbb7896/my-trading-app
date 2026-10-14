FROM node:24-alpine
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev
COPY server.mjs analysis.js import.mjs supabase-store.mjs stock-codes.json workbook.mjs kiwoom-engine.mjs ./
ENV HOST=0.0.0.0 PORT=8787 DATA_DIR=/data
EXPOSE 8787
CMD ["node", "server.mjs"]
