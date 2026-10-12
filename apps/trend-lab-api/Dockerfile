FROM node:24-alpine
WORKDIR /app
COPY package.json server.mjs analysis.js import.mjs stock-codes.json ./
ENV HOST=0.0.0.0 PORT=8787 DATA_DIR=/data
EXPOSE 8787
CMD ["node", "server.mjs"]
