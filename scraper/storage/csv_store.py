"""CSV export helpers."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable, List

from scraper.schemas import FundingProgrammeRecord


class CSVStore:
    """Write normalized records to a flat CSV file for analyst review."""

    def write(self, records: Iterable[FundingProgrammeRecord], path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = list(FundingProgrammeRecord.model_fields.keys()) + ["overall_confidence"]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for record in records:
                row = record.model_dump(mode="json")
                for key, value in list(row.items()):
                    if isinstance(value, (list, dict)):
                        row[key] = json.dumps(value, ensure_ascii=False)
                row["overall_confidence"] = record.overall_confidence()
                writer.writerow(row)
        return path

