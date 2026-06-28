"""Tests for the Document attachment helper."""

import os
import tempfile
import unittest

from fastapi_startkit.ai.document import Document


class TestDocument(unittest.TestCase):
    def test_from_path_reads_file_content(self):
        content = "Hello from file!"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(content)
            path = f.name

        try:
            doc = Document.from_path(path)
            self.assertEqual(doc.content, content)
        finally:
            os.unlink(path)

    def test_from_path_sets_name_to_path(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("content")
            path = f.name

        try:
            doc = Document.from_path(path)
            self.assertEqual(doc.name, path)
        finally:
            os.unlink(path)

    def test_from_path_reads_multiline_content(self):
        content = "line one\nline two\nline three\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(content)
            path = f.name

        try:
            doc = Document.from_path(path)
            self.assertEqual(doc.content, content)
        finally:
            os.unlink(path)

    def test_from_path_raises_on_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            Document.from_path("/nonexistent/path/file.txt")

    def test_from_path_reads_empty_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("")
            path = f.name

        try:
            doc = Document.from_path(path)
            self.assertEqual(doc.content, "")
        finally:
            os.unlink(path)

    def test_to_anthropic_block_returns_dict(self):
        doc = Document(content="some text", name="report.txt")
        block = doc.to_anthropic_block()
        self.assertIsInstance(block, dict)

    def test_to_anthropic_block_has_type_document(self):
        doc = Document(content="some text", name="report.txt")
        block = doc.to_anthropic_block()
        self.assertEqual(block["type"], "document")

    def test_to_anthropic_block_has_source_key(self):
        doc = Document(content="some text")
        block = doc.to_anthropic_block()
        self.assertIn("source", block)

    def test_to_anthropic_block_source_type_is_text(self):
        doc = Document(content="some text")
        block = doc.to_anthropic_block()
        self.assertEqual(block["source"]["type"], "text")

    def test_to_anthropic_block_source_media_type_default(self):
        doc = Document(content="some text")
        block = doc.to_anthropic_block()
        self.assertEqual(block["source"]["media_type"], "text/plain")

    def test_to_anthropic_block_source_data_contains_content(self):
        doc = Document(content="the actual text content")
        block = doc.to_anthropic_block()
        self.assertEqual(block["source"]["data"], "the actual text content")

    def test_to_anthropic_block_title_is_name(self):
        doc = Document(content="text", name="my_document.txt")
        block = doc.to_anthropic_block()
        self.assertEqual(block["title"], "my_document.txt")

    def test_to_anthropic_block_custom_media_type(self):
        doc = Document(content="<html/>", name="page.html", media_type="text/html")
        block = doc.to_anthropic_block()
        self.assertEqual(block["source"]["media_type"], "text/html")

    def test_to_anthropic_block_full_structure(self):
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
        self.assertEqual(block, expected)

    def test_document_name_defaults_to_empty_string(self):
        doc = Document(content="text")
        self.assertEqual(doc.name, "")

    def test_document_media_type_defaults_to_text_plain(self):
        doc = Document(content="text")
        self.assertEqual(doc.media_type, "text/plain")

    def test_document_stores_content(self):
        doc = Document(content="stored content")
        self.assertEqual(doc.content, "stored content")
