FROM python:3.10-slim

WORKDIR /app

RUN pip install --upgrade pip

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create necessary directories
RUN mkdir -p app/static/voices app/static/output app/static/tasks

# Expose the port the app runs on
EXPOSE 5000

# Set required environment variables
ENV COQUI_TOS_AGREED=1

# Command to run the application with Gunicorn
# Use 2 worker processes, bind to all interfaces on port 5000, timeout after 300 seconds
# Added max-requests to recycle workers and prevent memory leaks
CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:5000", "--timeout", "300", "--max-requests", "10", "--max-requests-jitter", "5", "run:app"]
