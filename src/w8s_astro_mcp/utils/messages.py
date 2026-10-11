"""Wording shared by several tools, so the same problem is always described the same way."""


def profile_not_found(profile_id) -> str:
    """The reply when a tool is given a profile_id that does not exist."""
    return f"Profile {profile_id} not found. Use list_profiles to see available profiles."


def profiles_not_found(profile_ids) -> str:
    """The reply when several profile_ids do not exist."""
    shown = ", ".join(str(pid) for pid in profile_ids)
    return f"Profile(s) {shown} not found. Use list_profiles to see available profiles."
