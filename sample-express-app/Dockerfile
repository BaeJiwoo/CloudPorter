FROM node:22-slim

WORKDIR /app
COPY package*.json ./
RUN npm install --include=dev
COPY . .
ENV PORT=8080
CMD ["npm", "start"]
