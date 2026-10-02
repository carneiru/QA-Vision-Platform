FROM node:22-alpine AS build
WORKDIR /app
COPY dashboard/package.json dashboard/package-lock.json ./
RUN npm ci
COPY dashboard/ ./
# SSO client ids are baked at build time (Vite); empty means the button is hidden.
ARG VITE_GOOGLE_CLIENT_ID=""
ARG VITE_MSAL_CLIENT_ID=""
ARG VITE_MSAL_AUTHORITY=""
ENV VITE_GOOGLE_CLIENT_ID=$VITE_GOOGLE_CLIENT_ID \
    VITE_MSAL_CLIENT_ID=$VITE_MSAL_CLIENT_ID \
    VITE_MSAL_AUTHORITY=$VITE_MSAL_AUTHORITY
RUN npm run build

FROM nginx:1.27-alpine
COPY dashboard/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
