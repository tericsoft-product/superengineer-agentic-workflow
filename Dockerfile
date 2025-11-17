FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    graphviz \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY agent.py tools.py cli.py ./

# Set environment variable for working directory
ENV WORK_DIR=/workspace

# Set API key (TEMPORARY - for development only)
# TODO: Remove this and use -e flag or secrets management in production
ENV ANTHROPIC_API_KEY=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

# Create workspace directory
RUN mkdir -p ${WORK_DIR}

# Set default working directory to workspace
WORKDIR ${WORK_DIR}

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Default command
ENTRYPOINT ["/entrypoint.sh"]

