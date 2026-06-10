"""Tests for the Document attachment helper."""

import os
import tempfile

import pytest
from fastapi_startkit.ai.document import Document


# ─── Document.from_path() ─────────────────────────────────────────────────────


def test_from_path_reads_file_content():
    content = "Hello from file!"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(content)
        path = f.name

    try:
        doc = Document.from_path(path)
        assert doc.content == content
    finally:
        os.unlink(path)


def test_from_path_sets_name_to_path():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("content")
        path = f.name

    try:
        doc = Document.from_path(path)
        assert doc.name == path
    finally:
        os.unlink(path)


def test_from_path_reads_multiline_content():
    content = "line one\nline two\nline three\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(content)
        path = f.name

    try:
        doc = Document.from_path(path)
        assert doc.content == content
    finally:
        os.unlink(path)


def test_from_path_raises_on_missing_file():
    with pytest.raises(FileNotFoundError):
        Document.from_path("/nonexistent/path/file.txt")


def test_from_path_reads_empty_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("")
        path = f.name

    try:
        doc = Document.from_path(path)
        assert doc.content == ""
    finally:
        os.unlink(path)


# ─── Document.to_anthropic_block() ────────────────────────────────────────────


def test_to_anthropic_block_returns_dict():
    doc = Document(content="some text", name="report.txt")
    block = doc.to_anthropic_block()
    assert isinstance(block, dict)


def test_to_anthropic_block_has_type_document():
    doc = Document(content="some text", name="report.txt")
    block = doc.to_anthropic_block()
    assert block["type"] == "document"


def test_to_anthropic_block_has_source_key():
    doc = Document(content="some text")
    block = doc.to_anthropic_block()
    assert "source" in block


def test_to_anthropic_block_source_type_is_text():
    doc = Document(content="some text")
    block = doc.to_anthropic_block()
    assert block["source"]["type"] == "text"


def test_to_anthropic_block_source_media_type_default():
    doc = Document(content="some text")
    block = doc.to_anthropic_block()
    assert block["source"]["media_type"] == "text/plain"


def test_to_anthropic_block_source_data_contains_content():
    doc = Document(content="the actual text content")
    block = doc.to_anthropic_block()
    assert block["source"]["data"] == "the actual text content"


def test_to_anthropic_block_title_is_name():
    doc = Document(content="text", name="my_document.txt")
    block = doc.to_anthropic_block()
    assert block["title"] == "my_document.txt"


def test_to_anthropic_block_custom_media_type():
    doc = Document(content="<html/>", name="page.html", media_type="text/html")
    block = doc.to_anthropic_block()
    assert block["source"]["media_type"] == "text/html"


def test_to_anthropic_block_full_structure():
    """Assert the complete expected block structure matches exactly."""
    doc = Document(content="contract text", name="contract.txt", media_type="text/plain")
    block = doc.to_anthropic_block()

    expected = {
        "type": "document",
        "source": {
            "type": "text",
            "media_type": "text/plain",
            "data": "contract text",
        },
        "title": "contract.txt",
    }
    assert block == expected


# ─── Document constructor ──────────────────────────────────────────────────────


def test_document_name_defaults_to_empty_string():
    doc = Document(content="text")
    assert doc.name == ""


def test_document_media_type_defaults_to_text_plain():
    doc = Document(content="text")
    assert doc.media_type == "text/plain"


def test_document_stores_content():
    doc = Document(content="stored content")
    assert doc.content == "stored content"
