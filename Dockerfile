FROM python:3.10-slim

WORKDIR /app

RUN pip install --upgrade pip

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create necessary directories
RUN mkdir -p app/static/voices app/static/output

# Expose the port the app runs on
EXPOSE 5000

# Set required environment variables
ENV COQUI_TOS_AGREED=1

# Command to run the application with Gunicorn
CMD ["gunicorn", "run:app"]
