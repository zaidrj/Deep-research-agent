# Use the recommended stable, Alpine-based Python base image with no detected vulnerabilities
FROM python:3.13-alpine

# Set environment variables for non-interactive operations
ENV PYTHONUNBUFFERED 1 \
    PIP_NO_CACHE_DIR off \
    PIP_DISABLE_PIP_VERSION_CHECK on \
    PIP_DEFAULT_TIMEOUT 100

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies required by some Python packages and the Prisma binary
# nodejs: Required for Prisma client generation and potentially some internal Prisma tools.
# postgresql-client: Useful for basic PG interaction, might contain libs needed by Prisma.
# openssl-dev: **CRITICAL** Provides OpenSSL development libraries required by the Prisma binary for TLS/SSL connections.
# libc6-compat: Provides compatibility layer for applications compiled against glibc (like the Prisma binary often is).
RUN apk add --no-cache nodejs postgresql-client openssl-dev libc6-compat \
    && rm -rf /var/cache/apk/* # Clean up apk cache

# Copy the requirements file first to leverage Docker caching
COPY requirements.txt .

# Install Python dependencies from requirements.txt
RUN pip install -r requirements.txt

# Copy the rest of your application code into the working directory
COPY . .

# Generate the Prisma client code (build step)
RUN python -m prisma generate

# --- The following section defines the command that runs when the container starts (runtime) ---

# The default command to run when the container starts.
# It first applies Prisma database migrations and then starts the Uvicorn server.
# DATABASE_URL must be provided as an environment variable in Koyeb for migrations and the app to connect.
CMD python -m prisma migrate deploy --schema=./prisma/schema.prisma && uvicorn main:app --host 0.0.0.0 --port $PORT