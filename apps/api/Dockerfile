FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    git \
    curl \
    openssh-client \
    && curl -fsSL https://get.docker.com | sh \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r apps/api/requirements.txt && \
    pip install bcrypt==4.0.1 "uvicorn[standard]"

EXPOSE 8000

CMD ["uvicorn", "apps.api.src.main:app", "--host", "0.0.0.0", "--port", "8000"]