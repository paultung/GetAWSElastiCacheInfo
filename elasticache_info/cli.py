"""CLI entry point for AWS ElastiCache Info tool."""

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from elasticache_info.aws.client import ElastiCacheClient
from elasticache_info.aws.exceptions import AWSBaseError
from elasticache_info.formatters.csv_formatter import CSVFormatter
from elasticache_info.formatters.markdown_formatter import MarkdownFormatter
from elasticache_info.utils import (
    ensure_output_dir,
    parse_engines,
    parse_info_types,
    setup_logger,
)

app = typer.Typer(
    help="AWS ElastiCache Info CLI Tool - Query and export ElastiCache cluster information"
)
console = Console()


@app.command()
def main(
    region: str = typer.Option(..., "--region", "-r", help="AWS Region (必填)"),
    profile: str = typer.Option("default", "--profile", "-p", help="AWS Profile (預設: default)"),
    engine: str = typer.Option(
        "redis,valkey,memcached",
        "--engine",
        "-e",
        help="引擎類型篩選，逗號分隔 (預設: redis,valkey,memcached)"
    ),
    cluster: Optional[str] = typer.Option(
        None,
        "--cluster",
        "-c",
        help="叢集名稱篩選，支援萬用字元 (預設: 所有叢集)"
    ),
    info_type: str = typer.Option(
        "all",
        "--info-type",
        "-i",
        help="欄位選擇，逗號分隔或 'all' (預設: all)"
    ),
    output_format: str = typer.Option(
        "csv",
        "--output-format",
        "-f",
        help="輸出格式：csv 或 markdown (預設: csv)"
    ),
    output_file: str = typer.Option(
        "./output/",
        "--output-file",
        "-o",
        help="輸出檔案路徑 (預設: ./output/)"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="啟用詳細日誌輸出"
    ),
):
    """Query and export AWS ElastiCache cluster information.

    Examples:
        # Query all clusters in us-east-1
        get-aws-ec-info -r us-east-1

        # Query only Redis clusters
        get-aws-ec-info -r us-east-1 -e redis

        # Query with cluster name filter
        get-aws-ec-info -r us-east-1 -c "prod-*"

        # Select specific fields
        get-aws-ec-info -r us-east-1 -i region,type,name,node-type

        # Output as Markdown
        get-aws-ec-info -r us-east-1 -f markdown -o output.md
    """
    # Setup logger
    logger = setup_logger(verbose)

    try:
        # Parse and validate parameters
        logger.info("=== AWS ElastiCache Info CLI ===")
        logger.info(f"Region: {region}")
        logger.info(f"Profile: {profile}")
        logger.info(f"Engine filter: {engine}")
        logger.info(f"Cluster filter: {cluster or 'all'}")
        logger.info(f"Info type: {info_type}")
        logger.info(f"Output format: {output_format}")

        # Parse engines
        try:
            engines = parse_engines(engine)
        except ValueError as e:
            console.print(f"[red]錯誤：{e}[/red]")
            raise typer.Exit(1)

        # Parse fields
        try:
            fields = parse_info_types(info_type)
        except ValueError as e:
            console.print(f"[red]錯誤：{e}[/red]")
            raise typer.Exit(1)

        # Validate output format
        if output_format.lower() not in ["csv", "markdown"]:
            console.print(f"[red]錯誤：無效的輸出格式 '{output_format}'。有效格式：csv, markdown[/red]")
            raise typer.Exit(1)

        # Create ElastiCache client
        logger.info("初始化 AWS ElastiCache 客戶端...")
        try:
            client = ElastiCacheClient(region=region, profile=profile)
        except AWSBaseError as e:
            console.print(f"[red]錯誤：{e}[/red]")
            raise typer.Exit(1)

        # Query ElastiCache information with progress indicator
        logger.info("開始查詢 ElastiCache 叢集資訊...")
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("正在查詢 ElastiCache 叢集...", total=None)

            try:
                results = client.get_elasticache_info(engines=engines, cluster_filter=cluster)
            except AWSBaseError as e:
                progress.stop()
                console.print(f"[red]錯誤：{e}[/red]")
                raise typer.Exit(1)

            progress.update(task, completed=True)

        if not results:
            console.print("[yellow]未找到符合條件的 ElastiCache 叢集[/yellow]")
            logger.info("查詢完成：0 個叢集")
            return

        logger.info(f"查詢完成：找到 {len(results)} 個叢集")

        # Display results in terminal using Rich Table
        console.print(f"\n[bold green]找到 {len(results)} 個 ElastiCache 叢集[/bold green]\n")

        table = Table(show_header=True, header_style="bold magenta")

        # Add columns based on selected fields
        for field in fields:
            display_name = field.replace("_", " ").title()
            table.add_column(display_name)

        # Add rows
        for item in results:
            row = [str(getattr(item, field, "")) for field in fields]
            table.add_row(*row)

        console.print(table)

        # Format and write output file
        logger.info(f"準備輸出檔案：{output_file}")

        # Select formatter
        if output_format.lower() == "csv":
            formatter = CSVFormatter()
            extension = "csv"
        else:
            formatter = MarkdownFormatter()
            extension = "md"

        # Format data
        formatted_output = formatter.format(results, fields)

        # Determine output file path
        output_path = Path(output_file)

        # If output_file is a directory, generate filename
        if output_file.endswith("/") or output_path.is_dir():
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            filename = f"elasticache-{region}-{timestamp}.{extension}"
            output_path = output_path / filename

        # Ensure output directory exists
        ensure_output_dir(str(output_path.parent))

        # Write to file
        output_path.write_text(formatted_output, encoding="utf-8")

        console.print(f"\n[bold green]✓[/bold green] 輸出檔案已儲存：{output_path.absolute()}")
        logger.info(f"輸出檔案已儲存：{output_path.absolute()}")

    except typer.Exit:
        raise
    except KeyboardInterrupt:
        console.print("\n[yellow]操作已取消[/yellow]")
        logger.info("操作已取消")
        raise typer.Exit(130)
    except Exception as e:
        console.print(f"[red]未預期的錯誤：{e}[/red]")
        logger.exception("未預期的錯誤")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
