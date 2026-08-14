from music_migrator.config import RequestSettings


def setup_profile(requests: RequestSettings) -> str:
    return f"""
  # TIDAL authentication starts when a migration first uses TIDAL.
  # tidal:
  #   requests:
  #     max_concurrency: {requests.max_concurrency}
  #     rate_limit: {requests.rate_limit}
"""
