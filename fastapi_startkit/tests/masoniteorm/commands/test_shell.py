import subprocess
import unittest
from unittest.mock import MagicMock, patch

from cleo.testers.command_tester import CommandTester

from fastapi_startkit.masoniteorm.commands import ShellCommand
from fastapi_startkit.masoniteorm.config.config import PostgresConfig, SQLiteConfig
from fastapi_startkit.masoniteorm.connections.manager import DatabaseManager


class TestShellCommand(unittest.TestCase):
    def setUp(self):
        self.command = ShellCommand()
        self.command_tester = CommandTester(self.command)

    def test_for_mysql(self):
        config = {
            "host": "localhost",
            "database": "orm",
            "user": "root",
            "port": "1234",
            "password": "secret",
            "prefix": "",
            "options": {"charset": "utf8mb4"},
            "full_details": {"driver": "mysql"},
        }
        command, _ = self.command.get_command(config)
        assert (
            command
            == "mysql orm --host localhost --port 1234 --user root --password secret --default-character-set utf8mb4"
        )

    def test_for_postgres(self):
        config = {
            "host": "localhost",
            "database": "orm",
            "user": "root",
            "port": "1234",
            "password": "secretpostgres",
            "prefix": "",
            "options": {"charset": "utf8mb4"},
            "full_details": {"driver": "postgres"},
        }
        command, env = self.command.get_command(config)
        assert command == "psql orm --host localhost --port 1234 --username root"
        assert env.get("PGPASSWORD", "secretpostgres")

    def test_for_sqlite(self):
        config = {
            "database": "orm.sqlite3",
            "prefix": "",
            "full_details": {"driver": "sqlite"},
        }
        command, _ = self.command.get_command(config)
        assert command == "sqlite3 orm.sqlite3"

    def test_for_mssql(self):
        config = {
            "host": "db.masonite.com",
            "database": "orm",
            "user": "root",
            "port": "1234",
            "password": "secretpostgres",
            "prefix": "",
            "options": {"charset": "utf8mb4"},
            "full_details": {"driver": "mssql"},
        }
        command, _ = self.command.get_command(config)
        assert command == "sqlcmd -d orm -U root -P secretpostgres -S tcp:db.masonite.com,1234"

    def _manager(self, connections, default="dev"):
        return DatabaseManager(MagicMock(), {"default": default, "connections": connections})

    def test_running_command_with_sqlite(self):
        manager = self._manager({"dev": SQLiteConfig(database="orm.sqlite3")})
        with patch("fastapi_startkit.masoniteorm.commands.ShellCommand.DB.instance", return_value=manager):
            with patch("subprocess.run") as run:
                assert self.command_tester.execute("-c dev") == 0
                assert "sqlite3" not in self.command_tester.io.fetch_output()
                assert run.call_args.args[0] == ["sqlite3", "orm.sqlite3"]

                assert self.command_tester.execute("-s 1") == 0
                assert "sqlite3 orm.sqlite3" in self.command_tester.io.fetch_output()

    def test_running_command_with_unknown_connection(self):
        manager = self._manager({})
        with patch("fastapi_startkit.masoniteorm.commands.ShellCommand.DB.instance", return_value=manager):
            with self.assertRaises(SystemExit):
                self.command_tester.execute("-c missing")
        assert "Connection configuration for 'missing' not found" in self.command_tester.io.fetch_output()

    def test_running_command_reports_missing_program(self):
        manager = self._manager({"dev": {"driver": "sqlite", "database": "orm.sqlite3"}})
        with patch("fastapi_startkit.masoniteorm.commands.ShellCommand.DB.instance", return_value=manager):
            with patch("subprocess.run", side_effect=FileNotFoundError):
                with self.assertRaises(SystemExit):
                    self.command_tester.execute("")
        assert "Cannot find sqlite program" in self.command_tester.io.fetch_output()

    def test_running_command_reports_process_error(self):
        manager = self._manager({"dev": SQLiteConfig(database="orm.sqlite3")})
        with patch("fastapi_startkit.masoniteorm.commands.ShellCommand.DB.instance", return_value=manager):
            with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "sqlite3")):
                with self.assertRaises(SystemExit):
                    self.command_tester.execute("")
        assert "An error happened calling the command." in self.command_tester.io.fetch_output()

    def test_connection_information_maps_username_to_user(self):
        config = self.command.get_connection_information(
            {"connections": {"pg": PostgresConfig(host="db", port=5432, database="orm", username="admin")}}, "pg"
        )
        assert config["user"] == "admin"
        assert config["options"] == {}
        assert config["full_details"]["driver"] == "postgres"
        command, _ = self.command.get_command(config)
        assert command == "psql orm --host db --port 5432 --username admin"

    def test_unsupported_driver_exits(self):
        with patch.object(self.command, "line") as line, self.assertRaises(SystemExit):
            self.command.get_command({"full_details": {"driver": "oracle"}})
        line.assert_called_once_with("<error>Connecting with driver 'oracle' is not implemented !</error>")

    def test_hiding_sensitive_options(self):
        config = {
            "host": "localhost",
            "database": "orm",
            "user": "root",
            "port": "",
            "password": "secret",
            "full_details": {"driver": "mysql"},
        }
        command, _ = self.command.get_command(config)
        cleaned_command = self.command.hide_sensitive_options(config, command)
        assert cleaned_command == "mysql orm --host localhost --user root --password ***"
