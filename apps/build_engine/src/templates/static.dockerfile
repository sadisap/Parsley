FROM python:3.11-slim

WORKDIR /app

COPY . .

EXPOSE {{PORT}}

CMD ["sh", "-c", "{{START_COMMAND}}"]