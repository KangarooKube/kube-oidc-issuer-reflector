import os
import traceback
from flask import Flask, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
import json
import logging
import typing as t
from kubernetes import client, config

default_rate_limit = os.environ.get('DEFAULT_RATE_LIMIT', '10 per second')

app = Flask(__name__)
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True

csrf = CSRFProtect(app)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[default_rate_limit],
    storage_uri="memory://",
)

class EndpointFilter(logging.Filter):
    def __init__(
        self,
        path: str,
        *args: t.Any,
        **kwargs: t.Any,
    ):
        """
        Initialize the EndpointFilter instance.

        Args:
            path (str): The URL path that should be excluded from the log output.
            *args: Additional positional arguments to be passed to the superclass.
            **kwargs: Additional keyword arguments to be passed to the superclass.
        """
        super().__init__(*args, **kwargs)
        self._path = path

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Filter out log records that contain the specified path.

        Args:
            record (logging.LogRecord): The log record to be filtered.

        Returns:
            bool: True if the record should be processed, False otherwise.
        """
        return record.getMessage().find(self._path) == -1


# Setup logging
if __name__ != '__main__':
    gunicorn_error_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers = gunicorn_error_logger.handlers
    app.logger.setLevel(gunicorn_error_logger.level)
    gunicorn_access_logger = logging.getLogger("gunicorn.access")
    gunicorn_access_logger.addFilter(EndpointFilter(path="/livez"))
    gunicorn_access_logger.addFilter(EndpointFilter(path="/readyz"))

def get_exception_description(e: Exception) -> str:
    """
    Return a string describing the exception.

    The string is a single line and includes the exception type and message.

    :param e: The exception to be described.
    :type e: Exception
    :return: A single line string describing the exception.
    :rtype: str
    """
    # Format the exception using the traceback module
    # The format_exception_only function takes the exception type and the
    # exception instance as arguments and returns a list of strings.
    # The list contains the exception type and the exception message.
    exc_desc_lines = traceback.format_exception_only(type(e), e)
    # Join the list of strings into a single string
    # The rstrip method is used to remove the trailing newline character
    exc_desc = ''.join(exc_desc_lines).rstrip()
    # Return the string
    return exc_desc

# Return a client based on config type   
def get_k8s_client() -> client:
    """
    Return a Kubernetes client based on the configuration type.

    This function attempts to determine the appropriate configuration for
    connecting to a Kubernetes cluster and returns a client object that
    can be used to interact with the cluster.

    The function first checks if the application is running within a
    Kubernetes cluster by looking for the "KUBERNETES_SERVICE_HOST" environment
    variable. If it is present, it loads the in-cluster configuration.

    If the application is not running within a Kubernetes cluster, it attempts
    to load the kubeconfig file from the default location (usually ~/.kube/config).
    If loading the kubeconfig file fails, the function logs the error.

    Returns:
        client: The Kubernetes client object.
    """
    # Check if the application is running inside a Kubernetes cluster
    if "KUBERNETES_SERVICE_HOST" in os.environ:
        # Load the in-cluster configuration
        config.load_incluster_config()
    else:
        # Attempt to load the kubeconfig file from the default location
        try:
            config.load_kube_config()
        except config.ConfigException as e:
            # Log the error if loading the kubeconfig file fails
            app.logger.error(get_exception_description(e))
    
    # Return the Kubernetes client object
    return client

# Route for OIDC discovery document which contains the metadata about the issuer’s configurations
@app.route('/.well-known/openid-configuration', methods=['GET'])
def get_openid_configuration() -> t.Tuple[str, int]:
    """
    This function handles the GET request to the /.well-known/openid-configuration endpoint.

    The /.well-known/openid-configuration endpoint is a standard endpoint in the OpenID Connect
    specification that returns the OIDC discovery document. This document contains the metadata
    about the issuer's configurations, such as the URLs of the authorization endpoint, token endpoint,
    userinfo endpoint, and the supported response types, subject types, ID Token signing algorithms,
    claims, and other parameters.

    The OIDC discovery document is returned in the JSON format.

    If there is an error while retrieving the OIDC discovery document, an error message is logged
    and a 500 error is returned with the error message.

    Returns:
        Tuple[str, int]: A tuple containing the JSON response of the OIDC discovery document and
                         the HTTP status code.
    """
    allowed_user_agent = os.environ.get('ALLOWED_USER_AGENT')
    if allowed_user_agent and request.headers.get('User-Agent') != allowed_user_agent:
        # If the User-Agent does not match the allowed value, return a 403 error
        return "Forbidden", 403

    try:
        # Get an instance of the WellKnown API client
        k8s_client: client.WellKnownApi = get_k8s_client().WellKnownApi()

        # Call the WellKnown API to get the OIDC discovery document
        api_response: client.ApiResponse = k8s_client.get_service_account_issuer_open_id_configuration(
            _preload_content=False)

        # Load the OIDC discovery document from the API response
        openid_configuration: dict = json.loads(api_response.data)
    except Exception as e:
        # If there is an error, log it and return a 500 error with the error message
        app.logger.error(f"kubernetes.client.WellKnownApi.Exception: {e}")
        return "Internal error check logs", 500

    # Return the OIDC discovery document as a JSON response
    return jsonify(openid_configuration), 200

# Route for JSON Web Key Sets (JWKS) document which contains the public signing key(s) for service accounts
@app.route('/openid/v1/jwks', methods=['GET'])
def get_jwks() -> t.Tuple[str, int]:
    """
    Return the JSON Web Key Sets (JWKS) document which contains the public signing key(s) for service accounts.

    This document is used to validate the signature of the ID Tokens issued by the cluster.

    Returns:
        Tuple[str, int]: A tuple containing the JSON response of the JWKS document and the HTTP status code.
    """
    allowed_user_agent = os.environ.get('ALLOWED_USER_AGENT')
    if allowed_user_agent and request.headers.get('User-Agent') != allowed_user_agent:
        # If the User-Agent does not match the allowed value, return a 403 error
        return "Forbidden", 403

    # Try to get the JWKS document from the Kubernetes API server
    try:
        # Get an instance of the OpenID API client
        k8s_client: client.OpenidApi = get_k8s_client().OpenidApi()

        # Call the OpenID API to get the JWKS document
        api_response: client.ApiResponse = k8s_client.get_service_account_issuer_open_id_keyset(_preload_content=False)

        # Load the JWKS document from the API response
        jwks: str = json.loads(api_response.data)
    except Exception as e:
        # If there is an error, log it and return a 500 error with the error message
        app.logger.error(f"kubernetes.client.OpenidApi.Exception: {e}")
        return "Internal error check logs", 500

    # Return the JWKS document as a JSON response
    return jsonify(jwks), 200

@app.route('/livez')
@limiter.exempt
def health_liveness() -> t.Tuple[str, int]:
    """
    Kubernetes liveness probe handler.

    The purpose of this route is to be used by Kubernetes to determine if the pod is
    running and healthy. It does this by checking if the Kubernetes API server is
    available and can be queried for its version.

    If the pod is not healthy, the liveness probe will restart the pod. This is
    useful for catching unexpected errors that may cause the pod to crash.

    This route is exempt from rate limiting because it is important for the pod to
    respond to the liveness probe quickly and correctly. Rate limiting may cause
    the pod to not respond to the liveness probe in a timely manner, which could
    cause the pod to be restarted unnecessarily.

    The route returns a tuple containing a string indicating the pod's health
    status and an HTTP status code. The string is a simple message that is
    logged to the pod's logs.

    If the pod is healthy, the HTTP status code is 200. If the pod is not healthy,
    the HTTP status code is 500.

    Returns:
        Tuple[str, int]: A tuple containing a string indicating the pod's health
                         status and an HTTP status code.
    """
    try:
        k8s_client: client.VersionApi = get_k8s_client().VersionApi()
        # Attempt to query the Kubernetes API server for its version.
        # If the API server is unavailable or does not respond, this will raise an
        # exception.
        api_response: client.V1Version = k8s_client.get_code()
    except Exception as e:
        # If the API server is unavailable or does not respond, log an error
        # message and return a 500 HTTP status code.
        app.logger.error("Health check failed!")
        app.logger.error(f"kubernetes.client.VersionApi.Exception: {e}")
        return "I am unhealthy!", 500
    
    # If the API server responded with a valid version string, log a message
    # indicating that the pod is healthy and return a 200 HTTP status code.
    return (
        f"I am healthy! Running on Kubernetes version {api_response.git_version}.",
        200,
    )
    
@app.route('/readyz')
@limiter.exempt
def health_readiness() -> t.Tuple[str, int]:
    """
    Kubernetes readiness probe endpoint.

    This endpoint is used by Kubernetes to determine if the container is ready to
    receive traffic. The endpoint will return a tuple containing a string and an
    HTTP status code.

    The readiness probe is used to determine if the container is ready to receive
    traffic. If the container is not ready, the readiness probe will return a
    non-200 HTTP status code, indicating that the container is not ready to
    receive traffic.

    In this case, the readiness probe will return a tuple containing a string
    indicating that the container is ready and an HTTP status code of 200.

    :return: A tuple containing a string indicating that the container is ready
             and an HTTP status code.
    :rtype: Tuple[str, int]
    """
    # Return a tuple containing a string indicating that the container is ready
    # and an HTTP status code of 200.
    return "I am ready!", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
