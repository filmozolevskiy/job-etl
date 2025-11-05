"""
Publisher-Hyper CLI entry point.
"""

import argparse
import logging
import sys

from services.publisher_hyper.exporter import export_from_env


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export marts tables to Tableau .hyper file")
    parser.add_argument("--output-dir", type=str, default="artifacts", help="Output directory for .hyper file")
    parser.add_argument("--filename", type=str, default="jobs_ranked.hyper", help="Hyper filename")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        path = export_from_env(output_dir=args.output_dir, hyper_filename=args.filename)
        logger.info("Hyper export completed", extra={"hyper_path": path})
        print(f"Hyper file created: {path}")
        return 0
    except Exception as e:
        logger.error(f"Export failed: {e}")
        print(f"ERROR: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())


