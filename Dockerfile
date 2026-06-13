FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Set work directory
WORKDIR /app

# Install dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY src/ /app/src/
COPY models/ /app/models/
COPY database/ /app/database/
COPY .env /app/.env
COPY entrypoint.sh /app/

# Make entrypoint script executable
RUN chmod +x /app/entrypoint.sh

# Expose FastAPI port
EXPOSE 8000

# Use entrypoint script to launch service
ENTRYPOINT ["/bin/sh", "/app/entrypoint.sh"]
