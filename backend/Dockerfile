FROM python:3.11-slim

# Install curl and bash (needed to download and run the bob install script)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl bash ca-certificates gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install IBM Bob CLI
RUN curl -fsSL https://bob.ibm.com/download/bobshell.sh | bash

# Ensure bob is on PATH (install script puts it in ~/.local/bin by default)
ENV PATH="/root/.local/bin:${PATH}"


WORKDIR /app

# Install Python dependencies
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . ./backend/

# SQLite database will be created at runtime in /app
# Mount a Railway volume to /app if you want persistence across deploys

# Environment variable defaults — override these in Railway dashboard
ENV LLM_PROVIDER=bob
ENV DATABASE_URL=sqlite:///./bob_intelligence.db

EXPOSE 8000

# Accept bob license at runtime (needs BOB_API_KEY), then start the server
CMD ["sh", "-c", "bob --accept-license -p 'hello' && uvicorn backend.main:app --host 0.0.0.0 --port 8000"]
