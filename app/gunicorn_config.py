import os
import datetime
import logging
import sys
import json_log_formatter
loglevel = os.environ.get('LOG_LEVEL', 'INFO').upper()
workers = int(os.environ.get('GUNICORN_PROCESSES', '2'))
threads = int(os.environ.get('GUNICORN_THREADS', '4'))
timeout = int(os.environ.get('GUNICORN_TIMEOUT', '120'))
forwarded_allow_ips = '*'
secure_scheme_headers = { 'X-Forwarded-Proto': 'https' }
accesslog = "-"
errorlog = "-"
bind = '0.0.0.0:8080'

class JsonRequestFormatter(json_log_formatter.JSONFormatter):
    def json_record(
        self,
        message: str,
        extra: dict[str, str | int | float],
        record: logging.LogRecord
    ) -> dict[str, str | int | float]:
        """
        Convert a log record to a JSON object.

        The access log format is specified at
        https://docs.gunicorn.org/en/stable/settings.html#access-log-format

        The output JSON object will have the following keys:
        - remote_ip: The IP address of the client.
        - method: The HTTP request method.
        - path: The URL path of the request.
        - status: The HTTP status code of the response.
        - time: The time the request was received.
        - user_agent: The User-Agent header of the request.
        - referrer: The Referrer header of the request.
        - duration_in_ms: The time taken to process the request in milliseconds.
        - pid: The process ID of the Gunicorn worker.
        """
        response_time = datetime.datetime.strptime(
            record.args["t"], "[%d/%b/%Y:%H:%M:%S %z]"
        )
        url = record.args["U"]
        if record.args["q"]:
            url += f"?{record.args['q']}"

        return dict(
            remote_ip=record.args["{X-Forwarded-For}i"],
            method=record.args["m"],
            path=url,
            status=str(record.args["s"]),
            time=response_time.isoformat(),
            user_agent=record.args["a"],
            referer=record.args["f"],
            duration_in_ms=record.args["M"],
            pid=record.args["p"],
        )

class JsonErrorFormatter(json_log_formatter.JSONFormatter):
    def json_record(
        self,
        message: str,
        extra: dict[str, str | int | float],
        record: logging.LogRecord
    ) -> dict[str, str | int | float]:
        """
        Override the default json_record method to add the log level to the
        error log payload.
        """
        payload: dict[str, str | int | float] = super().json_record(
            message, extra, record
        )
        payload["level"] = record.levelname
        return payload

# Ensure the two named loggers that Gunicorn uses are configured to use a custom
# JSON formatter.
logconfig_dict = {
    "version": 1,
    "formatters": {
        "json_request": {
            "()": JsonRequestFormatter,
        },
        "json_error": {
            "()": JsonErrorFormatter,
        },
    },
    "handlers": {
        "json_request": {
            "class": "logging.StreamHandler",
            "stream": sys.stdout,
            "formatter": "json_request",
        },
        "json_error": {
            "class": "logging.StreamHandler",
            "stream": sys.stdout,
            "formatter": "json_error",
        },
    },
    "root": {"level": loglevel, "handlers": []},
    "loggers": {
        "gunicorn.access": {
            "level": loglevel,
            "handlers": ["json_request"],
            "propagate": False,
        },
        "gunicorn.error": {
            "level": loglevel,
            "handlers": ["json_error"],
            "propagate": False,
        },
    },
}
