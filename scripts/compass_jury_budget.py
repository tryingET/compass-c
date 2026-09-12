"""Fixed AK5673 subscription request/attempt accounting and technical limits."""

MAX_CALLS = 24
MAX_TOKENS = 131072
MODEL_CONTEXT = 1_000_000
FRAMING_TOKENS = 4096
MESSAGE_LIMIT = MODEL_CONTEXT - MAX_TOKENS - FRAMING_TOKENS
REQUEST_LIMIT = 1_000_000
RESPONSE_LIMIT = 8_000_000
JUDGMENT_LIMIT = 512_000


def validate_capacity(message_bytes):
    # One token per ASCII-escaped message byte, plus framing and full output.
    if type(message_bytes) is not int or not 0 <= message_bytes <= MESSAGE_LIMIT:
        raise ValueError("technical context capacity exceeded")


class AttemptLedger:
    def __init__(self):
        self.calls = 0
        self.message_bytes = 0

    def record(self, message_bytes):
        validate_capacity(message_bytes)
        if self.calls >= MAX_CALLS:
            raise ValueError("pilot attempt cap reached")
        self.calls += 1
        self.message_bytes += message_bytes
