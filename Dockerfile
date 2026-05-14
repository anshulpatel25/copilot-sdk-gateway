FROM python:3.15.0b1-slim-trixie

# Update and upgrade system packages, then clean cache to minimize image size
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Create the gateway user and group
RUN groupadd -r gateway && useradd -m -g gateway gateway

# Set the working directory
WORKDIR /app

# Copy project files
COPY . /app/

# Change ownership of /app to the gateway user
RUN chown -R gateway:gateway /app

# Install dependencies as root
RUN uv pip install --no-cache-dir --system .

# Install GitHub Copilot CLI to /usr/local/bin (runs as root)
RUN curl -fsSL https://gh.io/copilot-install | bash

# Add labels
LABEL maintainer="Anshul Patel <er.anshul.patel@gmail.com>"
LABEL description="copilot-sdk-gateway: An OpenAI-API-compatible HTTP proxy backed by GitHub Copilot SDK."

# Expose the API port
EXPOSE 11434

# Add healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:11434/api/version || exit 1

# Switch to the gateway user
USER gateway

# Define entrypoint and command
ENTRYPOINT ["python", "-m", "copilot_sdk_gateway.main"]
