class HasColoredOutput:
    """Adds colorful output helpers to Cleo commands.

    Complements Cleo's built-in info(), line(), comment(), and question()
    with additional methods that use Cleo's IO so output is captured in tests.
    """

    def success(self, message: str) -> None:
        """Bold green — operation succeeded."""
        self.line(f"<info> OK </> {message}")

    def warn(self, message: str) -> None:
        """Yellow — non-fatal warning."""
        self.line(f"<comment> WARNING </> {message}")

    def error(self, message: str) -> None:
        """Red — error message."""
        self.line(f"<error> ERROR </> {message}")

    def danger(self, message: str) -> None:
        """Alias for error."""
        self.error(message)

    def muted(self, message: str) -> None:
        """Dim — low-emphasis output."""
        self.line(f"<comment>{message}</>")

    def new_line(self, count: int = 1) -> None:
        """Print one or more blank lines."""
        for _ in range(count):
            self.line("")
