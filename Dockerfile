# Build Stage for React Frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app/ui
COPY ui/package*.json ./
RUN npm ci
COPY ui/ ./
RUN npm run build

# Runtime Stage for Python Backend
FROM python:3.11-slim
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Backend Code
COPY app/ ./app/
    # Copy modules removed as it is not used directly by app
# Copy built Frontend assets from builder stage
COPY --from=frontend-builder /app/ui/dist ./ui/dist

# Expose port
EXPOSE 8000

# Run the server
CMD ["python", "-m", "app.server"]
