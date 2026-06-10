"""FastAPI Startkit AI module.

Provides a LangGraph-powered declarative API for building AI agents backed
by Anthropic, OpenAI, or Google provider SDKs.

Also exposes a Laravel-style fluent API for image generation and text-to-speech::

    from fastapi_startkit.ai import Image, Audio, Files

    image = await Image.of("A donut on a counter").generate()
    audio = await Audio.of("Hello world").female().generate()
"""

from .agent import Agent
from .audio import Audio, AudioResponse
from .config import AIConfig, AnthropicConfig, GoogleConfig, OpenAIConfig
from .decorators import max_steps, max_tokens, memory, model, provider, timeout, top_p
from .document import Document
from .files import Files, ImageAttachment
from .image import Image, ImageResponse
from .providers.ai_provider import AIProvider
from .response import AgentResponse, AgentSnapshot

__all__ = [
    "Agent",
    "AgentResponse",
    "AgentSnapshot",
    "AIConfig",
    "AIProvider",
    "AnthropicConfig",
    "Audio",
    "AudioResponse",
    "Document",
    "Files",
    "GoogleConfig",
    "Image",
    "ImageAttachment",
    "ImageResponse",
    "OpenAIConfig",
    "max_steps",
    "max_tokens",
    "memory",
    "model",
    "provider",
    "timeout",
    "top_p",
]
