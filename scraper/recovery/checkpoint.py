"""Checkpoint management for resumable crawls."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field


class CrawlCheckpoint(BaseModel):
    """Checkpoint state for a crawl session."""

    checkpoint_id: str
    run_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Crawl progress
    visited_urls: Set[str] = Field(default_factory=set)
    queued_urls: List[tuple[float, str, int, str]] = Field(default_factory=list)
    failed_urls: Dict[str, List[str]] = Field(default_factory=dict)
    completed_domains: Set[str] = Field(default_factory=set)

    # Statistics
    pages_crawled: int = 0
    pages_failed: int = 0
    records_extracted: int = 0

    # Configuration snapshot
    config_snapshot: Dict[str, Any] = Field(default_factory=dict)

    # Custom state
    custom_state: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {
            set: list,
            datetime: lambda v: v.isoformat(),
        }


class CheckpointManager:
    """Manage crawl checkpoints for resume capability."""

    def __init__(self, checkpoint_dir: Path) -> None:
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def save_checkpoint(self, checkpoint: CrawlCheckpoint) -> Path:
        """Save a checkpoint to disk."""
        checkpoint.updated_at = datetime.now(timezone.utc)
        checkpoint_path = self.checkpoint_dir / f"{checkpoint.checkpoint_id}.json"

        # Convert sets to lists for JSON serialization
        data = checkpoint.model_dump(mode="json")
        data["visited_urls"] = list(checkpoint.visited_urls)
        data["completed_domains"] = list(checkpoint.completed_domains)

        with open(checkpoint_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

        return checkpoint_path

    def load_checkpoint(self, checkpoint_id: str) -> Optional[CrawlCheckpoint]:
        """Load a checkpoint from disk."""
        checkpoint_path = self.checkpoint_dir / f"{checkpoint_id}.json"
        if not checkpoint_path.exists():
            return None

        try:
            with open(checkpoint_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Convert lists back to sets
            if "visited_urls" in data:
                data["visited_urls"] = set(data["visited_urls"])
            if "completed_domains" in data:
                data["completed_domains"] = set(data["completed_domains"])

            return CrawlCheckpoint.model_validate(data)
        except Exception:
            return None

    def list_checkpoints(self) -> List[str]:
        """List all available checkpoint IDs."""
        return [p.stem for p in self.checkpoint_dir.glob("*.json")]

    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint."""
        checkpoint_path = self.checkpoint_dir / f"{checkpoint_id}.json"
        if checkpoint_path.exists():
            checkpoint_path.unlink()
            return True
        return False

    def get_latest_checkpoint(self, run_id: Optional[str] = None) -> Optional[CrawlCheckpoint]:
        """Get the most recent checkpoint, optionally filtered by run_id."""
        checkpoints = []
        for checkpoint_id in self.list_checkpoints():
            checkpoint = self.load_checkpoint(checkpoint_id)
            if checkpoint:
                if run_id is None or checkpoint.run_id == run_id:
                    checkpoints.append(checkpoint)

        if not checkpoints:
            return None

        return max(checkpoints, key=lambda c: c.updated_at)

    def cleanup_old_checkpoints(self, keep_count: int = 10) -> int:
        """Clean up old checkpoints, keeping only the most recent ones."""
        checkpoints = []
        for checkpoint_id in self.list_checkpoints():
            checkpoint = self.load_checkpoint(checkpoint_id)
            if checkpoint:
                checkpoints.append(checkpoint)

        if len(checkpoints) <= keep_count:
            return 0

        # Sort by update time and delete oldest
        checkpoints.sort(key=lambda c: c.updated_at, reverse=True)
        deleted_count = 0
        for checkpoint in checkpoints[keep_count:]:
            if self.delete_checkpoint(checkpoint.checkpoint_id):
                deleted_count += 1

        return deleted_count
