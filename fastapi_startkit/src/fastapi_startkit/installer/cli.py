from importlib.metadata import version

from cleo.application import Application

from .init_command import InitCommand


def create_cli() -> Application:
    cli = Application("fastapi-startkit", version("fastapi-startkit"))
    cli.add(InitCommand())
    return cli


def main() -> int:
    return create_cli().run()


if __name__ == "__main__":
    raise SystemExit(main())
