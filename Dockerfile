FROM registry.access.redhat.com/ubi9/ubi-minimal

ARG USER_NAME=containeruser
ARG USER_UID=1000
ARG USER_GID=$USER_UID
ARG GROUP_NAME=$USER_NAME

# Install Python 3 and pip
RUN microdnf install -y python3 python3-pip \
    && microdnf clean all

COPY app /app

WORKDIR /app

RUN pip3 install --no-cache-dir -r requirements.txt \
    && groupadd -g "$USER_GID" "$GROUP_NAME" \
    && useradd -m -u "$USER_UID" -g "$GROUP_NAME" "$USER_NAME"

USER $USER_NAME

EXPOSE 8080

ENTRYPOINT ["gunicorn","--config", "gunicorn_config.py", "main:app"]