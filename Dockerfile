FROM python:3.11-slim

WORKDIR /app

# Install system dependencies: curl and zstd (zstd needed by Ollama installer)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    zstd \
    && rm -rf /var/lib/apt/lists/*

# Install Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project files
COPY . .

# Create necessary directories
RUN mkdir -p data logs chroma_db

# Expose Flask port
EXPOSE 5000

# Start Ollama, pull model, then run app
CMD ["sh", "-c", "ollama serve & sleep 5 && ollama pull llama3.2:latest && python app.py"]