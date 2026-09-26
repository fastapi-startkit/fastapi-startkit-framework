from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cleo.testers.command_tester import CommandTester

from fastapi_startkit.console.publish_command import PublishCommand


def run(published_resources: dict, base_path: Path, args: str = "", inputs: str = "") -> CommandTester:
    fake_app = SimpleNamespace(
        published_resources=published_resources,
        use_base_path=lambda path: base_path / path,
    )
    tester = CommandTester(PublishCommand())
    with patch("fastapi_startkit.application.app", return_value=fake_app):
        tester.execute(args, inputs=inputs)
    return tester


def test_nothing_to_publish(tmp_path):
    tester = run({}, tmp_path)

    assert tester.status_code == 0
    assert "Nothing to publish." in tester.io.fetch_output()


def test_unknown_provider(tmp_path):
    tester = run({"LogProvider": {}}, tmp_path, "--provider missing")

    assert tester.status_code == 0
    assert "No provider found matching 'missing'." in tester.io.fetch_output()


def test_publishes_matching_provider_files(tmp_path):
    source = tmp_path / "source.py"
    source.write_text("LOG = True\n")
    resources = {
        "LogProvider": {str(source): "config/logging.py"},
        "OtherProvider": {str(source): "config/other.py"},
    }

    tester = run(resources, tmp_path / "project", "--provider log_provider")

    assert tester.status_code == 0
    assert (tmp_path / "project/config/logging.py").read_text() == "LOG = True\n"
    assert not (tmp_path / "project/config/other.py").exists()
    assert "[LogProvider] Published config/logging.py" in tester.io.fetch_output()


def test_skips_existing_file_when_overwrite_declined(tmp_path):
    source = tmp_path / "source.py"
    source.write_text("NEW\n")
    existing = tmp_path / "project/config/logging.py"
    existing.parent.mkdir(parents=True)
    existing.write_text("OLD\n")

    tester = run({"LogProvider": {str(source): "config/logging.py"}}, tmp_path / "project", inputs="no\n")

    assert tester.status_code == 0
    assert existing.read_text() == "OLD\n"
    assert "[LogProvider] Skipped config/logging.py" in tester.io.fetch_output()
