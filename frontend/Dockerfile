FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG VITE_API_BASE_URL=/api/v1
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
# "storefront" (customers + sellers) or "admin" (separate admin console). Same code, two builds.
ARG VITE_APP_MODE=storefront
ARG VITE_ADMIN_URL=
ENV VITE_APP_MODE=$VITE_APP_MODE VITE_ADMIN_URL=$VITE_ADMIN_URL
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
