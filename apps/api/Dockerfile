# apps/api/Dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the whole repo so internal imports work
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r apps/api/requirements.txt

# Expose port
EXPOSE 8000

# Run the API
CMD ["uvicorn", "apps.api.src.main:app", "--host", "0.0.0.0", "--port", "8000"]