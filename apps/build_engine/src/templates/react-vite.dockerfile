FROM node:20-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .
RUN {{BUILD_COMMAND}}

FROM node:20-alpine

WORKDIR /app
RUN npm install -g serve

COPY --from=build /app/dist ./dist

EXPOSE {{PORT}}

CMD ["sh", "-c", "{{START_COMMAND}}"]