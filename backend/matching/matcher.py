"""Market matching engine using TF-IDF cosine similarity + entity overlap.

Vectorizes ALL market titles into a single TF-IDF space, then computes
cross-platform similarities efficiently.
"""

import logging
from dataclasses import dataclass

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from backend.matching.normalizer import extract_entities, normalize_title

logger = logging.getLogger(__name__)


@dataclass
class MatchCandidate:
    market_a_id: str
    market_a_platform: str
    market_a_title: str
    market_b_id: str
    market_b_platform: str
    market_b_title: str
    similarity: float
    entity_overlap: float
    confidence: float


@dataclass
class MarketInfo:
    """Lightweight market representation for matching."""

    platform: str
    platform_id: str
    title: str
    category: str
    close_time: object  # datetime | None


def find_matches(
    markets: list[MarketInfo],
    confidence_threshold: float = 0.80,
    max_close_time_diff_days: int = 7,
) -> list[MatchCandidate]:
    """Find matching markets across platforms using TF-IDF similarity.

    Strategy:
    1. Vectorize all titles into a single TF-IDF space
    2. For each platform pair, compute cosine similarity matrix
    3. Filter by confidence threshold (TF-IDF + entity overlap)
    """
    if len(markets) < 2:
        return []

    # Group by platform
    by_platform: dict[str, list[tuple[int, MarketInfo]]] = {}
    for idx, m in enumerate(markets):
        by_platform.setdefault(m.platform, []).append((idx, m))

    platforms = list(by_platform.keys())
    if len(platforms) < 2:
        return []

    # Normalize all titles and build TF-IDF matrix over entire corpus
    normalized = [normalize_title(m.title) for m in markets]

    vectorizer = TfidfVectorizer(
        analyzer="word",
        ngram_range=(1, 3),
        min_df=1,
        max_df=0.98,
        sublinear_tf=True,
    )

    try:
        tfidf_matrix = vectorizer.fit_transform(normalized)
    except ValueError:
        return []

    # Pre-compute entities for all markets
    entities = [extract_entities(m.title) for m in markets]

    matches: list[MatchCandidate] = []

    # Compare across every platform pair
    for i, p1 in enumerate(platforms):
        for p2 in platforms[i + 1 :]:
            indices_a = [idx for idx, _ in by_platform[p1]]
            indices_b = [idx for idx, _ in by_platform[p2]]

            if not indices_a or not indices_b:
                continue

            # Compute similarity sub-matrix: |A| x |B|
            vecs_a = tfidf_matrix[indices_a]
            vecs_b = tfidf_matrix[indices_b]
            sim_matrix = cosine_similarity(vecs_a, vecs_b)

            # Find pairs above a loose pre-filter (entity/token overlap can boost significantly)
            pre_filter = 0.05  # Very loose — let entity/token overlap rescue weak TF-IDF
            row_indices, col_indices = np.where(sim_matrix > pre_filter)

            for r, c in zip(row_indices, col_indices, strict=True):
                idx_a = indices_a[r]
                idx_b = indices_b[c]
                m_a = markets[idx_a]
                m_b = markets[idx_b]

                # Close time filter
                if m_a.close_time and m_b.close_time:
                    try:
                        diff = abs((m_a.close_time - m_b.close_time).total_seconds())
                        if diff > max_close_time_diff_days * 86400:
                            continue
                    except (TypeError, AttributeError):
                        pass

                sim = float(sim_matrix[r, c])

                # Entity overlap
                ents_a = entities[idx_a]
                ents_b = entities[idx_b]
                entity_overlap = 0.0
                if ents_a and ents_b:
                    intersection = ents_a & ents_b
                    union = ents_a | ents_b
                    entity_overlap = len(intersection) / len(union) if union else 0.0

                # Token overlap (Jaccard on normalized words)
                words_a = set(normalized[idx_a].split())
                words_b = set(normalized[idx_b].split())
                token_overlap = 0.0
                if words_a and words_b:
                    token_overlap = len(words_a & words_b) / len(words_a | words_b)

                # Combined confidence: 40% TF-IDF + 35% entity overlap + 25% token overlap
                # Entity overlap is weighted higher because entity matches (names, dates, numbers)
                # are strong signals of semantic equivalence
                confidence = 0.40 * sim + 0.35 * entity_overlap + 0.25 * token_overlap

                if confidence >= confidence_threshold:
                    matches.append(
                        MatchCandidate(
                            market_a_id=m_a.platform_id,
                            market_a_platform=m_a.platform,
                            market_a_title=m_a.title,
                            market_b_id=m_b.platform_id,
                            market_b_platform=m_b.platform,
                            market_b_title=m_b.title,
                            similarity=round(sim, 4),
                            entity_overlap=round(entity_overlap, 4),
                            confidence=round(confidence, 4),
                        )
                    )

    matches.sort(key=lambda m: m.confidence, reverse=True)
    logger.info(
        "Matching: found %d matches above %.2f threshold", len(matches), confidence_threshold
    )
    return matches
