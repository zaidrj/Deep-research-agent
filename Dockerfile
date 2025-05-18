# Use a stable, slim Debian-based Python base image compatible with OpenSSL 1.1
# python:3.11-slim-bullseye is a good choice - slim keeps image size down, bullseye is Debian 11
FROM python:3.11-slim-bullseye

# Set environment variables for non-interactive operations
ENV PYTHONUNBUFFERED 1 \
    PIP_NO_CACHE_DIR off \
    PIP_DISABLE_PIP_VERSION_CHECK on \
    PIP_DEFAULT_TIMEOUT 100

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies required by some Python packages and the Prisma binary
# nodejs: Required for Prisma client generation.
# postgresql-client: Useful for basic PG interaction and might contain libs needed by Prisma.
# libssl1.1: **CRITICAL** Provides the OpenSSL 1.1 shared libraries specifically needed by Prisma's debian-openssl-1.1.x target.
RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs \
    postgresql-client \
    libssl1.1 \
    && rm -rf /var/lib/apt/lists/* # Clean up apt cache

# Copy the requirements file first to leverage Docker caching
COPY requirements.txt .

# Install Python dependencies from requirements.txt
RUN pip install -r requirements.txt

# Copy the rest of your application code into the working directory
COPY . .

# Generate the Prisma client code (build step)
# This command runs after code is copied but before the container starts.
# It finds schema.prisma automatically if it's in the standard ./prisma location.
RUN python -m prisma generate

# --- The following section defines the command that runs when the container starts (runtime) ---

# The default command to run when the container starts.
# It first applies Prisma database migrations and then starts the Uvicorn server.
# DATABASE_URL must be provided as an environment variable in Koyeb for migrations and the app to connect.
CMD python -m prisma migrate deploy --schema=./prisma/schema.prisma && uvicorn main:app --host 0.0.0.0 --port $PORT