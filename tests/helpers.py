"""Fake Gemini SDK client used to mock Gemini at the SDK boundary."""
from types import SimpleNamespace


class FakeGemini:
    """Returns queued replies in order; an Exception in the queue is raised."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []
        self.models = SimpleNamespace(generate_content=self._generate)

    def _generate(self, model, contents):
        self.prompts.append(contents)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return SimpleNamespace(text=reply)


class FakeAPIError(Exception):
    """Mimics google.genai.errors.APIError (has .code) incl. a secret-bearing message."""

    def __init__(self, code, message="boom"):
        super().__init__(message)
        self.code = code
        self.message = message
