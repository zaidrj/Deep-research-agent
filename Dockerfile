# Use the recommended stable, Alpine-based Python base image with no detected vulnerabilities
FROM python:3.13-alpine

# Set environment variables for non-interactive operations
ENV PYTHONUNBUFFERED 1 \
    PIP_NO_CACHE_DIR off \
    PIP_DISABLE_PIP_VERSION_CHECK on \
    PIP_DEFAULT_TIMEOUT 100

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies required by some Python packages (like Prisma binary needs Node.js)
# and potentially for database connectors.
# We install Node.js (nodejs) and PostgreSQL client (postgresql-client)
# Use apk add --no-cache for Alpine
RUN apk add --no-cache nodejs postgresql-client

# Copy the requirements file first to leverage Docker caching
# This step is only re-run if requirements.txt changes
COPY requirements.txt .

# Install Python dependencies from requirements.txt
RUN pip install -r requirements.txt

# Copy the rest of your application code into the working directory
# This includes main.py, the prisma directory, agent_core.py, etc.
COPY . .

# Generate the Prisma client code
# This uses the Prisma binary downloaded by the prisma Python package
# It needs the schema.prisma file (which is now copied)
RUN python -m prisma generate

# --- The following section defines the command that runs when the container starts ---

# The default command to run when the container starts.
# It first applies Prisma database migrations and then starts the Uvicorn server.
# DATABASE_URL must be provided as an environment variable in Koyeb for migrations and the app to connect.
# The --schema flag is good practice here to be explicit about the schema location.
# uvicorn runs the main:app object, binds to all interfaces (0.0.0.0), and uses the port specified by Koyeb ($PORT).
CMD python -m prisma migrate deploy --schema=./prisma/schema.prisma && uvicorn main:app --host 0.0.0.0 --port $PORT