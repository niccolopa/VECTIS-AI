# VECTIS frontend image — build the static app, serve it with Vite preview.
FROM node:20-slim AS build
WORKDIR /app

# Copy the lockfile too so the build is reproducible (npm ci honors it exactly).
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY . .

# The API base URL must be baked at build time (the browser calls it directly).
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

EXPOSE 5173
CMD ["npm", "run", "preview", "--", "--host", "--port", "5173"]
