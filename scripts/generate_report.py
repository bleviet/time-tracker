"""
Script to generate matrix reports based on a YAML configuration.
"""

import sys
import yaml
import asyncio
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.matrix_report_service import MatrixReportService, ReportConfiguration


async def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_report.py <config_file.yaml>")
        sys.exit(1)

    config_path = Path(sys.argv[1])
    if not config_path.exists():
        print(f"Error: Config file '{config_path}' not found.")
        sys.exit(1)

    print(f"Loading configuration from {config_path}...")
    with open(config_path, 'r') as f:
        config_data = yaml.safe_load(f)

    try:
        config = ReportConfiguration(**config_data)
    except Exception as e:
        print(f"Error parsing configuration: {e}")
        sys.exit(1)

    print(f"Generating report for period: {config.period}")
    service = MatrixReportService()
    
    csv_content = await service.generate_report(config)
    
    # Determine output path
    if config.output_path:
        output_file = Path(config.output_path)
    else:
        output_file = config_path.parent / f"report_{config.period}.csv"
        
    # Ensure directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(csv_content)
        
    print(f"Report successfully saved to: {output_file.absolute()}")


if __name__ == "__main__":
    asyncio.run(main())
