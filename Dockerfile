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

# Command to run the application
CMD ["python", "run.py"]
