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
# Use 4 worker processes, bind to all interfaces on port 5000, timeout after 120 seconds
CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:5000", "--timeout", "120", "run:app"]
