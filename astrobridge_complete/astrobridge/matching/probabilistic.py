"""Probabilistic cross-matching – BayesianMatcher with normalised posteriors.

Key fix over the previous implementation:
    The old code computed  posterior = likelihood * prior  then clamped to [0,1].
    That is *not* Bayes' theorem – it ignores P(data) and means two equally-good
    candidates both score identically, making best-of-N selection arbitrary.

    The corrected implementation:
    1. Computes unnormalised posteriors for every candidate in the search window.
    2. Normalises by the sum of all posteriors so they represent a proper
       probability distribution over candidates (plus a "no-match" mass equal to
       the complement of the prior).
    3. Selects the highest-posterior candidate if it exceeds ``confidence_threshold``.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import numpy as np

from astrobridge.geometry import angular_distance_deg
from astrobridge.matching.base import Matcher
from astrobridge.matching.confidence import ConfidenceScorer
from astrobridge.matching.spatial import SpatialIndex
from astrobridge.models import MatchResult, Source

logger = logging.getLogger(__name__)


class BayesianMatcher(Matcher):
    """Bayesian probabilistic cross-matcher with normalised posteriors."""

    def __init__(
        self,
        positional_sigma_threshold: float = 3.0,
        confidence_threshold: float = 0.05,
        prior_match_prob: float = 0.7,
        confidence_scorer: Optional[ConfidenceScorer] = None,
        proper_motion_aware: bool = False,
        match_epoch: Optional[datetime] = None,
    ) -> None:
        self.positional_sigma_threshold = positional_sigma_threshold
        self.confidence_threshold = confidence_threshold
        self.prior_match_prob = prior_match_prob
        self.confidence_scorer = confidence_scorer or ConfidenceScorer()
        self.proper_motion_aware = proper_motion_aware
        self.match_epoch = match_epoch
        self.calibration_metrics: dict[str, float] = {
            "accuracy": 0.0, "precision": 0.0, "recall": 0.0
        }

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def match(
        self,
        ref_sources: list[Source],
        candidate_sources: list[Source],
    ) -> list[MatchResult]:
        """Match reference sources to the best candidate from ``candidate_sources``."""
        logger.info(
            "Matching %d ref sources against %d candidates",
            len(ref_sources), len(candidate_sources),
        )
        if not candidate_sources:
            logger.warning("No candidate sources provided")
            return []

        spatial_index: Optional[SpatialIndex] = None
        if not self.proper_motion_aware:
            spatial_index = SpatialIndex(candidate_sources)

        search_radius_arcsec = 60.0
        matches: list[MatchResult] = []

        for ref_source in ref_sources:
            reference_epoch = self.match_epoch or ref_source.provenance.query_timestamp

            if self.proper_motion_aware:
                ref_ra, ref_dec = self._coordinate_at_epoch(ref_source, reference_epoch)
                nearby_indices = [
                    i for i, c in enumerate(candidate_sources)
                    if self._angular_distance(
                        ref_ra, ref_dec,
                        *self._coordinate_at_epoch(c, reference_epoch),
                    ) * 3600.0 <= search_radius_arcsec
                ]
            else:
                assert spatial_index is not None
                nearby_indices = spatial_index.query_radius(
                    ref_source.coordinate.ra,
                    ref_source.coordinate.dec,
                    search_radius_arcsec,
                )

            if not nearby_indices:
                logger.debug("No candidates near %s", ref_source.name)
                continue

            # --- Compute unnormalised likelihoods for each candidate ---
            likelihoods: list[float] = []
            for idx in nearby_indices:
                lhood = self._likelihood(
                    ref_source,
                    candidate_sources[idx],
                    target_epoch=reference_epoch if self.proper_motion_aware else None,
                )
                likelihoods.append(lhood)

            # --- Normalise to proper posteriors ---
            # P(match_i | data) ∝ L(data | match_i) * prior
            # P(no_match | data) ∝ (1 - prior) * 1/N  (uniform null)
            prior = self.prior_match_prob
            null_mass = max(0.0, 1.0 - prior)
            unnorm = [lh * prior for lh in likelihoods]
            total = sum(unnorm) + null_mass
            posteriors = [u / total for u in unnorm] if total > 0 else [0.0] * len(unnorm)

            best_local = int(np.argmax(posteriors))
            best_prob = posteriors[best_local]

            if best_prob < self.confidence_threshold:
                continue

            best_match = candidate_sources[nearby_indices[best_local]]

            if self.proper_motion_aware:
                ref_ra, ref_dec = self._coordinate_at_epoch(ref_source, reference_epoch)
                bm_ra, bm_dec = self._coordinate_at_epoch(best_match, reference_epoch)
            else:
                ref_ra, ref_dec = ref_source.coordinate.ra, ref_source.coordinate.dec
                bm_ra, bm_dec = best_match.coordinate.ra, best_match.coordinate.dec

            separation_arcsec = self._angular_distance(ref_ra, ref_dec, bm_ra, bm_dec) * 3600.0

            runner_up_sep: Optional[float] = None
            runner_up_distances = []
            for i, idx in enumerate(nearby_indices):
                if i == best_local:
                    continue
                c = candidate_sources[idx]
                if self.proper_motion_aware:
                    c_ra, c_dec = self._coordinate_at_epoch(c, reference_epoch)
                else:
                    c_ra, c_dec = c.coordinate.ra, c.coordinate.dec
                runner_up_distances.append(
                    self._angular_distance(ref_ra, ref_dec, c_ra, c_dec) * 3600.0
                )
            if runner_up_distances:
                runner_up_sep = min(runner_up_distances)

            confidence_result = self.confidence_scorer.compute_score(
                ref_source,
                best_match,
                separation_arcsec=separation_arcsec,
                runner_up_separation_arcsec=runner_up_sep,
            )

            matches.append(
                MatchResult(
                    source1_id=ref_source.id,
                    source2_id=best_match.id,
                    match_probability=best_prob,
                    separation_arcsec=separation_arcsec,
                    confidence=confidence_result.confidence,
                )
            )
            logger.debug(
                "Match: %s -> %s  prob=%.3f  sep=%.2f\"",
                ref_source.name, best_match.name, best_prob, separation_arcsec,
            )

        return matches

    def calculate_match_probability(
        self,
        source_ref: Source,
        source_candidate: Source,
        target_epoch: Optional[datetime] = None,
    ) -> float:
        """Single-pair Bayesian posterior (unnormalised over the pair only).

        Used for unit testing and inspection.  For multi-candidate matching,
        use ``match()`` which normalises over the full candidate set.
        """
        lh = self._likelihood(source_ref, source_candidate, target_epoch=target_epoch)
        prior = self.prior_match_prob
        unnorm = lh * prior
        total = unnorm + (1.0 - prior)
        return float(unnorm / total) if total > 0 else 0.0

    def set_thresholds(
        self,
        confidence_threshold: Optional[float] = None,
        positional_sigma_threshold: Optional[float] = None,
    ) -> None:
        if confidence_threshold is not None:
            if not 0.0 <= confidence_threshold <= 1.0:
                raise ValueError("confidence_threshold must be in [0, 1]")
            self.confidence_threshold = confidence_threshold
        if positional_sigma_threshold is not None:
            if positional_sigma_threshold <= 0:
                raise ValueError("positional_sigma_threshold must be positive")
            self.positional_sigma_threshold = positional_sigma_threshold

    def get_calibration_metrics(self) -> dict[str, float]:
        return self.calibration_metrics.copy()

    def set_calibration_metrics(
        self, accuracy: float, precision: float, recall: float
    ) -> None:
        self.calibration_metrics = {
            "accuracy": accuracy, "precision": precision, "recall": recall
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _likelihood(
        self,
        source_ref: Source,
        source_cand: Source,
        target_epoch: Optional[datetime] = None,
    ) -> float:
        """Combined positional × photometric likelihood."""
        pos = self._positional_likelihood(source_ref, source_cand, target_epoch)
        photo = self._photometric_likelihood(source_ref, source_cand)
        return pos * photo

    def _positional_likelihood(
        self,
        source_ref: Source,
        source_cand: Source,
        target_epoch: Optional[datetime] = None,
    ) -> float:
        if target_epoch is not None:
            ref_ra, ref_dec = self._coordinate_at_epoch(source_ref, target_epoch)
            cand_ra, cand_dec = self._coordinate_at_epoch(source_cand, target_epoch)
        else:
            ref_ra, ref_dec = source_ref.coordinate.ra, source_ref.coordinate.dec
            cand_ra, cand_dec = source_cand.coordinate.ra, source_cand.coordinate.dec

        distance_deg = self._angular_distance(ref_ra, ref_dec, cand_ra, cand_dec)
        distance_arcsec = distance_deg * 3600.0

        combined_error_arcsec = 0.1
        if source_ref.uncertainty and source_cand.uncertainty:
            combined_error_arcsec = float(np.sqrt(
                source_ref.uncertainty.ra_error ** 2
                + source_cand.uncertainty.ra_error ** 2
            ))

        sigma = max(combined_error_arcsec, 1e-9)
        return float(np.exp(-(distance_arcsec ** 2) / (2.0 * sigma ** 2)))

    def _photometric_likelihood(
        self, source_ref: Source, source_cand: Source
    ) -> float:
        ref_bands = {p.band: p.magnitude for p in source_ref.photometry}
        cand_bands = {p.band: p.magnitude for p in source_cand.photometry}
        common = set(ref_bands) & set(cand_bands)
        if not common:
            return 1.0
        mean_diff = float(np.mean([abs(ref_bands[b] - cand_bands[b]) for b in common]))
        tolerance = 0.5
        return float(np.exp(-(mean_diff ** 2) / (2.0 * tolerance ** 2)))

    @staticmethod
    def _angular_distance(
        ra1: float, dec1: float, ra2: float, dec2: float
    ) -> float:
        return angular_distance_deg(ra1, dec1, ra2, dec2)

    @staticmethod
    def _coordinate_at_epoch(
        source: Source, target_epoch: datetime
    ) -> tuple[float, float]:
        ra = source.coordinate.ra
        dec = source.coordinate.dec
        source_epoch = source.provenance.query_timestamp
        delta_years = (
            (target_epoch - source_epoch).total_seconds() / (365.25 * 24.0 * 3600.0)
        )
        pm_ra = source.coordinate.pm_ra_mas_per_year or 0.0
        pm_dec = source.coordinate.pm_dec_mas_per_year or 0.0
        ra = (ra + (pm_ra * delta_years) / (1000.0 * 3600.0)) % 360.0
        dec = max(-90.0, min(90.0, dec + (pm_dec * delta_years) / (1000.0 * 3600.0)))
        return ra, dec
