"""Usage tools - plan allowance windows and subscription tier."""

from ...services import ServiceError
from ...services import usage as usage_service
from ._utils import ResultDict, create_profile_client, error_result, get_client, logged_tool


@logged_tool()
def usage_get(profile: str | None = None) -> ResultDict:
    """Show how much of the plan's usage allowance is left, and when it resets.

    Gemini Notebook meters usage as compute against two windows at once: a short
    rolling window and a weekly one. Both are reported, each with the percentage
    used, the percentage remaining and the reset time in UTC.

    Args:
        profile: Optional authentication profile. Uses the configured default when omitted.
    """
    client = None
    explicit_profile = profile is not None
    try:
        client = create_profile_client(profile) if explicit_profile else get_client()
        result = usage_service.get_usage(client)
        return {"status": "success", **result}
    except ServiceError as e:
        return error_result(e.user_message, hint=e.hint)
    except Exception as e:
        return error_result(str(e))
    finally:
        if explicit_profile and client is not None:
            client.close()
