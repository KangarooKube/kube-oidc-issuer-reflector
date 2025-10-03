FROM registry.access.redhat.com/ubi10/ubi-minimal

ARG USER_NAME=containeruser
ARG USER_UID=1000
ARG USER_GID=$USER_UID
ARG GROUP_NAME=$USER_NAME

# Install Python 3, pip, and shadow-utils (for useradd/groupadd)
RUN microdnf install -y python3 python3-pip shadow-utils \
    && microdnf clean all

COPY app /app
WORKDIR /app

# Create the runtime user/group up front (used for owning writable app dirs)
RUN groupadd -g "$USER_GID" "$GROUP_NAME" \
    && useradd -m -u "$USER_UID" -g "$GROUP_NAME" "$USER_NAME"

# Create a virtual environment as root, install dependencies into it,
# precompile bytecode, then lock down the venv so the runtime user only
# has read+execute access (no write). Clean caches and tmp files.
ENV PYTHONDONTWRITEBYTECODE=1
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt \
    # Precompile .py to .pyc so runtime doesn't need to write bytecode
    && /opt/venv/bin/python -m compileall -q /opt/venv || true \
    # Clean pip and system caches and temporary files
    && rm -rf /root/.cache /root/.cache/pip /tmp/* /var/tmp/* /var/cache/* \
    && microdnf clean all || true \
    \
    # Make the venv owned by root and remove write permission for non-root runtime user:
    && chown -R root:root /opt/venv \
    && find /opt/venv -type d -exec chmod 0755 {} + \
    && find /opt/venv -type f -exec chmod 0644 {} + \
    && find /opt/venv/bin -type f -exec chmod 0755 {} +

# Ensure the application directory is writable by the non-root runtime user
RUN chown -R "$USER_UID:$USER_GID" /app

# Ensure the venv is used by default (read/execute only for app user)
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

USER $USER_NAME

EXPOSE 8080

ENTRYPOINT ["gunicorn","--config", "gunicorn_config.py", "main:app"]
