FROM node:20-alpine

WORKDIR /app

COPY package.json /app/package.json
RUN npm install --no-audit --no-fund

COPY next.config.js /app/next.config.js
COPY .eslintrc.json /app/.eslintrc.json
COPY .prettierrc.json /app/.prettierrc.json
COPY tsconfig.json /app/tsconfig.json
COPY postcss.config.js /app/postcss.config.js
COPY tailwind.config.ts /app/tailwind.config.ts
COPY src /app/src

ENV NODE_ENV=production
RUN npm run build

EXPOSE 3000
CMD ["npm", "run", "start", "--", "-p", "3000"]
