"""One-command dataset build: fetch FIRMS + ERA5 for a region/window, join, write.

    python -m vectis.calibration.data.build --region california \\
        --start 2020-06-01 --end 2020-10-31

Re-runnable for any registered region and window — the whole Step-1/2 pipeline behind a
single command, as a future maintainer should expect. Requires ``VECTIS_FIRMS_API_KEY``
(labels) and network reach to the two archives; it fails loudly with instructions
otherwise, never silently substituting synthetic data.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

from vectis.calibration.data.base import CalibrationDataError
from vectis.calibration.data.dataset import build_dataset, write_dataset
from vectis.calibration.data.era5 import Era5Client
from vectis.calibration.data.firms_archive import FirmsArchiveClient
from vectis.core.config import get_settings
from vectis.data.regions import REGIONS, get_region


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", default="california", choices=sorted(REGIONS))
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--negatives-per-positive", type=float, default=3.0)
    parser.add_argument("--seed", type=int, default=34)
    args = parser.parse_args(argv)

    settings = get_settings()
    try:
        dataset = build_dataset(
            get_region(args.region),
            args.start,
            args.end,
            firms=FirmsArchiveClient(),
            era5=Era5Client(),
            negatives_per_positive=args.negatives_per_positive,
            seed=args.seed,
        )
        path = write_dataset(dataset, settings.data_dir)
    except CalibrationDataError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    m = dataset.manifest
    print(
        f"wrote {m['rows_written']} rows ({m['positive_cell_days']} fire / "
        f"{m['negative_cell_days']} no-fire) to {path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
