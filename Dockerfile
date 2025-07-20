FROM python:3.12-alpine

ARG USER_NAME=containeruser
ARG USER_UID=1000
ARG USER_GID=$USER_UID
ARG GROUP_NAME=$USER_NAME

COPY app /app

WORKDIR /app

RUN apk upgrade --update-cache \
    && rm -rf /var/cache/apk/* \
    && pip3 install --no-cache-dir -r requirements.txt \
    && addgroup --gid "$USER_GID" "$GROUP_NAME" \
    && adduser -D -h $(pwd) -G "$GROUP_NAME" -H -u "$USER_UID" "$USER_NAME"

USER $USER_NAME

EXPOSE 8080

ENTRYPOINT ["gunicorn","--config", "gunicorn_config.py", "main:app"]
