FROM python:3.12-slim-trixie

ARG USER_NAME=containeruser
ARG USER_UID=1000
ARG USER_GID=${USER_UID}
ARG GROUP_NAME=${USER_NAME}

# Prevent Python from writing .pyc files at runtime and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Set a non-interactive frontend for any apt operations
ENV DEBIAN_FRONTEND=noninteractive

# System setup:
#  - Update package index
#  - Install any needed runtime dependencies
#  - Clean apt caches to keep image small
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ca-certificates \
       curl \
       # (Uncomment if your Python dependencies need compilation) \
       # build-essential \
       # libssl-dev \
       # libffi-dev \
       # gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy application code
WORKDIR /app
COPY app /app

# Create a dedicated virtual environment owned by root, install deps into it,
# precompile Python bytecode, then remove write perms for the runtime user.
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && if [ -f requirements.txt ]; then /opt/venv/bin/pip install --no-cache-dir -r requirements.txt; fi \
    # Precompile bytecode so runtime user doesn't need to write .pyc at runtime
    && /opt/venv/bin/python -m compileall -q /opt/venv || true \
    # Lock down venv (root owns; others r+x, binaries executable)
    && chown -R root:root /opt/venv \
    && find /opt/venv -type d -exec chmod 0755 {} + \
    && find /opt/venv -type f -exec chmod 0644 {} + \
    && find /opt/venv/bin -type f -exec chmod 0755 {} + \
    # Clean caches
    && rm -rf /root/.cache /tmp/*

# Create non-root runtime user & group explicitly
RUN groupadd -g "${USER_GID}" "${GROUP_NAME}" \
    && useradd -m -u "${USER_UID}" -g "${GROUP_NAME}" "${USER_NAME}"

# Ensure application directory is owned by the runtime user (if it needs write access)
RUN chown -R "${USER_UID}:${USER_GID}" /app

# Activate virtual environment by default
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

USER ${USER_NAME}

EXPOSE 8080

# Gunicorn entrypoint (unchanged from original)
ENTRYPOINT ["gunicorn","--config","gunicorn_config.py","main:app"]
