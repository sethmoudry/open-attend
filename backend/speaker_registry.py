"""Speaker registry for cross-chunk speaker consistency.

Maintains a session-level registry of speaker profiles using voice
embeddings. When a new chunk arrives with pyannote speaker IDs,
the registry matches them against accumulated profiles using cosine
similarity to maintain consistent identities.
"""

import threading
from dataclasses import dataclass, field
from typing import Optional

import numpy as np


@dataclass
class SpeakerProfile:
    consistent_id: str  # e.g. "spk_0", "spk_1"
    role: Optional[str] = None  # e.g. "doctor", "patient" -- set by T-035
    embeddings: list[list[float]] = field(default_factory=list)
    mean_embedding: Optional[list[float]] = None  # running average

    def update_mean(self) -> None:
        """Recompute mean embedding from all accumulated embeddings."""
        if not self.embeddings:
            self.mean_embedding = None
            return
        self.mean_embedding = np.mean(self.embeddings, axis=0).tolist()

    def to_dict(self) -> dict:
        return {
            "consistent_id": self.consistent_id,
            "role": self.role,
            "embeddings": self.embeddings,
            "mean_embedding": self.mean_embedding,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SpeakerProfile":
        profile = cls(
            consistent_id=data["consistent_id"],
            role=data.get("role"),
            embeddings=data.get("embeddings", []),
            mean_embedding=data.get("mean_embedding"),
        )
        return profile


class SpeakerRegistry:
    """Maintains consistent speaker identities across audio chunks.

    Thread-safe via a reentrant lock. Supports 2-8 speakers per session.
    Falls back to sequential ID assignment when no embeddings are available.
    """

    SIMILARITY_THRESHOLD = 0.65
    MAX_SPEAKERS = 6

    def __init__(self) -> None:
        self.profiles: list[SpeakerProfile] = []
        self._next_id: int = 0
        self._lock = threading.Lock()

    # -- public API --

    def match_speakers(
        self,
        chunk_speaker_ids: list[str],
        chunk_embeddings: list[dict],
    ) -> dict[str, str]:
        """Map raw pyannote speaker IDs to consistent session-level IDs.

        Args:
            chunk_speaker_ids: Raw pyannote IDs for this chunk
                (e.g. ["SPEAKER_00", "SPEAKER_01"]).
            chunk_embeddings: List of dicts with keys ``speaker_id`` (str)
                and ``embedding`` (list[float] or None).

        Returns:
            ``{raw_id: consistent_id}`` mapping.
        """
        with self._lock:
            return self._match_speakers_locked(chunk_speaker_ids, chunk_embeddings)

    def get_role(self, consistent_id: str) -> Optional[str]:
        """Get the assigned role for a speaker."""
        with self._lock:
            for p in self.profiles:
                if p.consistent_id == consistent_id:
                    return p.role
        return None

    def set_role(self, consistent_id: str, role: str) -> None:
        """Set the role for a speaker (called by T-035 role assignment)."""
        with self._lock:
            for p in self.profiles:
                if p.consistent_id == consistent_id:
                    p.role = role
                    return
            raise KeyError(f"No speaker profile with id {consistent_id!r}")

    def get_all_profiles(self) -> list[dict]:
        """Return all speaker profiles with IDs and roles."""
        with self._lock:
            return [p.to_dict() for p in self.profiles]

    # -- serialization --

    def to_dict(self) -> list[dict]:
        """Serialize the entire registry for storage in session state."""
        with self._lock:
            return [p.to_dict() for p in self.profiles]

    @classmethod
    def from_dict(cls, data: list) -> "SpeakerRegistry":
        """Reconstruct a registry from serialized session state.

        Accepts either raw dicts or Pydantic SpeakerProfile objects
        (from models.py) — the latter are converted via .model_dump().
        """
        registry = cls()
        for item in data:
            if isinstance(item, dict):
                d = item
            elif hasattr(item, "model_dump"):
                d = item.model_dump()
            else:
                d = {"consistent_id": getattr(item, "consistent_id", f"spk_{len(registry.profiles)}"),
                     "role": getattr(item, "role", None)}
            profile = SpeakerProfile.from_dict(d)
            registry.profiles.append(profile)
        # Derive _next_id from existing profiles
        if registry.profiles:
            max_idx = max(
                int(p.consistent_id.split("_")[1]) for p in registry.profiles
            )
            registry._next_id = max_idx + 1
        return registry

    def merge_by_role(self) -> dict[str, str]:
        """Merge profiles that share the same role into a single profile.

        Returns a mapping of {old_id: merged_id} for all merged profiles.
        """
        with self._lock:
            role_groups: dict[str, list[SpeakerProfile]] = {}
            for p in self.profiles:
                if p.role:
                    role_groups.setdefault(p.role, []).append(p)

            id_map: dict[str, str] = {}
            for role, profiles in role_groups.items():
                if len(profiles) <= 1:
                    continue
                # Keep the profile with the most embeddings as the primary
                profiles.sort(key=lambda p: len(p.embeddings), reverse=True)
                primary = profiles[0]
                for secondary in profiles[1:]:
                    # Absorb embeddings
                    primary.embeddings.extend(secondary.embeddings)
                    id_map[secondary.consistent_id] = primary.consistent_id
                    self.profiles.remove(secondary)
                primary.update_mean()

            return id_map

    # -- internals --

    def _match_speakers_locked(
        self,
        chunk_speaker_ids: list[str],
        chunk_embeddings: list[dict],
    ) -> dict[str, str]:
        # Build a lookup: raw_id -> embedding (may be None or contain NaN)
        emb_lookup: dict[str, Optional[list[float]]] = {}
        for entry in chunk_embeddings:
            emb = entry.get("embedding")
            # Treat NaN/Inf embeddings as None (unusable for matching)
            if emb is not None:
                import math
                if any(math.isnan(v) or math.isinf(v) for v in emb):
                    emb = None
            emb_lookup[entry["speaker_id"]] = emb

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique_ids: list[str] = []
        for sid in chunk_speaker_ids:
            if sid not in seen:
                seen.add(sid)
                unique_ids.append(sid)

        mapping: dict[str, str] = {}
        # Track which profiles have already been claimed this round
        claimed: set[str] = set()

        for raw_id in unique_ids:
            embedding = emb_lookup.get(raw_id)

            if embedding is not None and self.profiles:
                # Try embedding-based matching
                best_sim = -1.0
                best_profile: Optional[SpeakerProfile] = None
                for profile in self.profiles:
                    if profile.consistent_id in claimed:
                        continue
                    if profile.mean_embedding is None:
                        continue
                    sim = self._cosine_similarity(embedding, profile.mean_embedding)
                    if sim > best_sim:
                        best_sim = sim
                        best_profile = profile

                if best_profile is not None and best_sim >= self.SIMILARITY_THRESHOLD:
                    # Match found -- accumulate embedding
                    best_profile.embeddings.append(embedding)
                    best_profile.update_mean()
                    mapping[raw_id] = best_profile.consistent_id
                    claimed.add(best_profile.consistent_id)
                    continue

            # No embedding or no match above threshold
            # If no embedding and we already have profiles, assign to the
            # least-recently-used unclaimed profile instead of creating a new one
            if embedding is None and self.profiles:
                for profile in self.profiles:
                    if profile.consistent_id not in claimed:
                        mapping[raw_id] = profile.consistent_id
                        claimed.add(profile.consistent_id)
                        break
                else:
                    mapping[raw_id] = self.profiles[-1].consistent_id
                continue

            # Create new profile if under cap
            if len(self.profiles) >= self.MAX_SPEAKERS:
                # Cap reached: assign to closest existing profile regardless,
                # or the last one if no embeddings to compare
                if embedding is not None and self.profiles:
                    best_sim = -1.0
                    best_profile = None
                    for profile in self.profiles:
                        if profile.consistent_id in claimed:
                            continue
                        if profile.mean_embedding is None:
                            continue
                        sim = self._cosine_similarity(
                            embedding, profile.mean_embedding
                        )
                        if sim > best_sim:
                            best_sim = sim
                            best_profile = profile
                    if best_profile is not None:
                        best_profile.embeddings.append(embedding)
                        best_profile.update_mean()
                        mapping[raw_id] = best_profile.consistent_id
                        claimed.add(best_profile.consistent_id)
                        continue

                # Fallback: pick first unclaimed profile
                for profile in self.profiles:
                    if profile.consistent_id not in claimed:
                        mapping[raw_id] = profile.consistent_id
                        claimed.add(profile.consistent_id)
                        break
                else:
                    # Everything claimed -- reuse the last profile
                    mapping[raw_id] = self.profiles[-1].consistent_id
                continue

            new_id = f"spk_{self._next_id}"
            self._next_id += 1
            profile = SpeakerProfile(consistent_id=new_id)
            if embedding is not None:
                profile.embeddings.append(embedding)
                profile.update_mean()
            self.profiles.append(profile)
            mapping[raw_id] = new_id
            claimed.add(new_id)

        return mapping

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two embedding vectors."""
        a_arr = np.asarray(a, dtype=np.float64)
        b_arr = np.asarray(b, dtype=np.float64)
        dot = np.dot(a_arr, b_arr)
        norm_a = np.linalg.norm(a_arr)
        norm_b = np.linalg.norm(b_arr)
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return float(dot / (norm_a * norm_b))
