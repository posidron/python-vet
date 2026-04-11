"""Rich console helpers for pyvet."""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

console = Console()
error_console = Console(stderr=True)


def print_success(message: str) -> None:
    console.print(f"[bold green]✓[/] {message}")


def print_error(message: str) -> None:
    error_console.print(f"[bold red]✗[/] {message}")


def print_warning(message: str) -> None:
    console.print(f"[bold yellow]![/] {message}")


def print_info(message: str) -> None:
    console.print(f"[bold blue]ℹ[/] {message}")


def make_table(title: str, columns: list[tuple[str, str]]) -> Table:
    """Create a rich table with the given title and (name, style) columns."""
    table = Table(title=title, show_header=True, header_style="bold magenta")
    for name, style in columns:
        table.add_column(name, style=style)
    return table
