"""
Code for the resource-list-submission AWS Lambda. Disables itself
if invoked too often. Statements printed to stdout will be logged by AWS in
CloudWatch.

The AWS Lambda must be called with the path /add or /edit, and with the POST
method. The body of the POST is passed to a github action in the
RiC-ResourceList repository at GitHub, triggered by an API call which requires
authentication. This authentication relies upon a private key for the AWS
Lambda which has to be included as a separate file
'egad_github_app_private_key.pem'.
"""

from base64 import b64decode as base64_decode
from dataclasses import dataclass, field
from datetime import datetime, timezone
from time import time
from typing import Callable

from boto3 import client
from jwt import encode
from requests import post as post_request, HTTPError

MAX_INVOCATIONS_PER_HOUR = 50
MAX_INVOCATIONS_PER_DAY = 200


def _egad_github_app_private_key() -> str:
    with open(
            "egad_github_app_private_key.pem",
            "r",
            encoding="utf-8") as private_key_file:
        return private_key_file.read()


EGAD_GITHUB_APP_CLIENT_ID = "Iv23li07sxNURUZ9Ixgf"
EGAD_GITHUB_APP_PRIVATE_KEY = _egad_github_app_private_key()

type Json = dict[str, Json | int | str | bool | None | float]
FormSubmission = str
SubmissionType = str
Token = str


class InvalidHttpMethodException(Exception):
    """
    Thrown if the AWS Lambda is called with a HTTP method that is not POST
    """


class InvalidPathException(Exception):
    """
    Thrown if the AWS Lambda is called with a path that is not /add or /edit
    """


class TooManyInvocationsThisHourException(Exception):
    """
    Thrown if too many invocations have been made during the present hour
    """


class TooManyInvocationsThisDayException(Exception):
    """
    Thrown if too many invocations have been made during the present day
    """


def _generate_jwt_token(private_key: str) -> Token:
    """
     See https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-json-web-token-jwt-for-a-github-app # pylint: disable=line-too-long
    """
    issued_at_time = int(time())
    expiration_time = issued_at_time + 60  # 1 minute (10 minutes is the max)
    return encode(
        {
            "iat": issued_at_time,
            "exp": expiration_time,
            "iss": EGAD_GITHUB_APP_CLIENT_ID
        },
        private_key,
        algorithm="RS256"
    )


def _generate_installation_token(jwt_token: Token) -> Token:
    """
    Here 64136623 is the 'installation ID' of the RiC-ResourceList installation
    of the app, obtainable by a GET request to /installations.
    """
    response = post_request(
        "https://api.github.com/app/installations/64136623/access_tokens",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {jwt_token}",
            "X-GitHub-Api-Version": "2022-11-28"
        },
        timeout=45
    )
    response.raise_for_status()
    return response.json()["token"]


def _disable_lambda() -> None:
    aws_client = client("lambda")
    aws_client.put_function_concurrency(
        FunctionName="resource-list-submission",
        ReservedConcurrentExecutions=0,  # Throttles all requests (no charge)
    )


@dataclass
class Limiter:
    """
    Keeps track of how many times the Lambda has been invoked per hour
    and per day, and shuts it down if either of these exceeeds certain limits
    """
    current_hour_fetcher: Callable[[], int] = lambda: datetime.now(
        timezone.utc).hour
    invocations_this_hour: int = 0
    invocations_this_day: int = 0
    this_hour: int = field(init=False)

    def __post_init__(self) -> None:
        self.this_hour = self.current_hour_fetcher()

    def handle_invocation(self) -> None:
        """
        Increments the per hour and per day invocation counters for the Lambda,
        and shuts it down if either of these exceeeds certain limits
        """
        current_hour = self.current_hour_fetcher()
        # We assume that the lambda function will never live idly for several
        # hours
        if current_hour != self.this_hour:
            self.invocations_this_hour = 0
            # Following can likely only occur if current_hour == 0, since max
            # idle time is likely less than an hour, but we formulate it like
            # this to be on the safe side!
            if current_hour < self.this_hour:
                self.invocations_this_day = 0
            self.this_hour = current_hour
        self.invocations_this_hour += 1
        self.invocations_this_day += 1
        if self.invocations_this_hour > MAX_INVOCATIONS_PER_HOUR:
            _disable_lambda()
            raise TooManyInvocationsThisHourException
        if self.invocations_this_day > MAX_INVOCATIONS_PER_DAY:
            _disable_lambda()
            raise TooManyInvocationsThisDayException


def _extract_form_submission(event) -> tuple[FormSubmission, SubmissionType]:
    if event["requestContext"]["http"]["method"] != "POST":
        raise InvalidHttpMethodException

    submission = base64_decode(event["body"]).decode("utf-8") if event[
        "isBase64Encoded"] else event["body"]
    path = event["requestContext"]["http"]["path"]
    if not path or path[1:] not in ["add", "edit"]:
        raise InvalidPathException
    return submission, path[1:]


def _trigger_github_action(
        submission: FormSubmission,
        submission_type: SubmissionType) -> None:
    installation_token = _generate_installation_token(_generate_jwt_token(
        EGAD_GITHUB_APP_PRIVATE_KEY))
    response = post_request(
        "https://api.github.com/repos/ICA-EGAD/RiC-ResourceList/dispatches",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {installation_token}",
            "X-GitHub-Api-Version": "2022-11-28"
        },
        json={
            "event_type": f"{submission_type}_resource",
            "client_payload": {
                "form_submission": submission
            }
        },
        timeout=45
    )
    response.raise_for_status()


limiter = Limiter()


def lambda_handler(event, _) -> Json:
    """
    Function called by AWS when the Lambda is invoked
    """
    print(f"Event: {event}")
    root_redirect_url = "https://ica-egad.github.io/RiC-ResourceList"
    failure_url = f"{root_redirect_url}/failure.html"
    try:
        limiter.handle_invocation()
    except TooManyInvocationsThisHourException:
        print(f"Too many invocations this hour. Hour: {limiter.this_hour}")
        return {
            "statusCode": 303,
            "headers": {
                "Location": failure_url
            },
            "body": "Too many resources have been added during this hour"

        }
    except TooManyInvocationsThisDayException:
        print("Too many invocations this day")
        return {
            "statusCode": 303,
            "headers": {
                "Location": failure_url
            },
            "body": "Too many resources have been added today"
        }
    try:
        submission, submission_type = _extract_form_submission(event)
    except InvalidHttpMethodException:
        print(f"Invalid HTTP method: {event['http']['method']}")
        return {
            "statusCode": 303,
            "headers": {
                "Location": failure_url
            },
            "body": "Invalid HTTP method"
        }
    except InvalidPathException:
        print(
            f"Invalid HTTP method: {event['requestContext']['http']['method']}")
        return {
            "statusCode": 303,
            "headers": {
                "Location": failure_url
            },
            "body": "Called with path that is not /add or /edit"
        }
    try:
        _trigger_github_action(submission, submission_type)
    except HTTPError as exception:
        print(f"HTTPError: {exception}")
        return {
            "statusCode": 303,
            "headers": {
                "Location": failure_url
            },
            "body": "An error occurred when making an API call involved in "
                    "triggering adding or editing a resource in github"
        }
    print(f"Successfully passed to GitHub! Submission type: {submission_type}. "
          f"Submission: {submission}")
    return {
        "statusCode": 303,
        "headers": {
            "Location": f"{root_redirect_url}/{submission_type}_success.html"
        },
        "body": "Successfully passed on form submission to GitHub"
    }
