FROM python:3.12-slim

# Base packages
RUN apt-get update && apt-get install -y \
    git \
    curl \
    wget \
    unzip \
    build-essential \
    dnsutils \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# -----------------------------
# Install Go
# -----------------------------
RUN wget https://go.dev/dl/go1.24.6.linux-amd64.tar.gz && \
    tar -C /usr/local -xzf go1.24.6.linux-amd64.tar.gz && \
    rm go1.24.6.linux-amd64.tar.gz

ENV PATH="/usr/local/go/bin:/root/go/bin:${PATH}"

RUN pip install --no-cache-dir bbot
RUN go install github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest
RUN go install github.com/owasp-amass/amass/v5/...@latest

WORKDIR /workspace

CMD ["/bin/bash"]