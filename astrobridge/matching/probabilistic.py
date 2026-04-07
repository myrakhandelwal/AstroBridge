"""Probabilistic cross-matching implementation."""
import logging
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from astrobridge.models import Source, MatchResult
from astrobridge.matching.base import Matcher, MatcherError
from astrobridge.matching.spatial import SpatialIndex

logger = logging.getLogger(__name__)


class BayesianMatcher(Matcher):
    """Bayesian probabilistic cross-matcher for astronomical sources."""
    
    def __init__(
        self,
        positional_sigma_threshold: float = 3.0,
        confidence_threshold: float = 0.05,  # Lowered to 0.05 for realistic matching
        prior_match_prob: float = 0.7  # Increased from 0.1 for more permissive matching
    ):
        """
        Initialize Bayesian matcher.
        
        Args:
            positional_sigma_threshold: Max positional deviation in sigma
            confidence_threshold: Min posterior probability for match
            prior_match_prob: Prior probability that two sources match
        """
        self.positional_sigma_threshold = positional_sigma_threshold
        self.confidence_threshold = confidence_threshold
        self.prior_match_prob = prior_match_prob
        
        self.calibration_metrics = {"accuracy": 0.0, "precision": 0.0, "recall": 0.0}
    
    def match(
        self, 
        ref_sources: List[Source], 
        candidate_sources: List[Source]
    ) -> List[MatchResult]:
        """
        Match reference sources to candidates.
        
        Args:
            ref_sources: Reference sources to match
            candidate_sources: Candidate sources to match against
            
        Returns:
            List of MatchResult objects
        """
        logger.info(f"Matching {len(ref_sources)} ref sources against {len(candidate_sources)} candidates")
        
        if not candidate_sources:
            logger.warning("No candidate sources provided")
            return []
        
        # Build spatial index on candidates
        spatial_index = SpatialIndex(candidate_sources)
        
        matches = []
        search_radius_arcsec = 60.0  # Default search radius (sufficient for typical astrometric errors)
        
        for ref_source in ref_sources:
            # Find nearby candidates
            nearby_indices = spatial_index.query_radius(
                ref_source.coordinate.ra,
                ref_source.coordinate.dec,
                search_radius_arcsec
            )
            
            if not nearby_indices:
                logger.debug(f"No candidates near {ref_source.name}")
                continue
            
            # Compute match probabilities
            best_match = None
            best_prob = self.confidence_threshold
            
            for cand_idx in nearby_indices:
                candidate = candidate_sources[cand_idx]
                
                prob = self.calculate_match_probability(ref_source, candidate)
                
                if prob > best_prob:
                    best_prob = prob
                    best_match = candidate
            
            if best_match is not None:
                # Compute detailed scores
                pos_sig = self._positional_significance(ref_source, best_match)
                photo_cons = self._photometric_consistency(ref_source, best_match)
                
                confidence = "high" if best_prob > 0.8 else "medium" if best_prob > 0.6 else "low"
                match_type = "combined" if photo_cons > 0.5 and pos_sig < self.positional_sigma_threshold else \
                             "photometric" if photo_cons > 0.5 else "positional"
                
                # Calculate angular separation in arcseconds
                distance_deg = self._angular_distance(
                    ref_source.coordinate.ra, ref_source.coordinate.dec,
                    best_match.coordinate.ra, best_match.coordinate.dec
                )
                separation_arcsec = distance_deg * 3600.0
                
                # Convert confidence string to float
                confidence_map = {"high": 0.9, "medium": 0.7, "low": 0.5}
                confidence_score = confidence_map.get(confidence, 0.5)
                
                match_result = MatchResult(
                    source1_id=ref_source.id,
                    source2_id=best_match.id,
                    match_probability=best_prob,
                    separation_arcsec=separation_arcsec,
                    confidence=confidence_score
                )
                matches.append(match_result)
                logger.debug(f"Match found: {ref_source.name} -> {best_match.name} ({best_prob:.2f})")
        
        return matches
    
    def calculate_match_probability(self, source_ref: Source, source_candidate: Source) -> float:
        """
        Calculate posterior probability that sources are the same object.
        
        Uses Bayesian formula:
        P(match|data) = P(data|match) * P(match) / P(data)
        
        Args:
            source_ref: Reference source
            source_candidate: Candidate source
            
        Returns:
            Match probability (0-1)
        """
        # Position likelihood
        pos_likelihood = self._positional_likelihood(source_ref, source_candidate)
        
        # Photometry likelihood
        photo_likelihood = self._photometric_likelihood(source_ref, source_candidate)
        
        # Combined likelihood
        combined_likelihood = pos_likelihood * photo_likelihood
        
        # Bayesian update: P(match|data) = P(data|match) * P(match) / P(data)
        # Assuming P(data) is normalized and same for all candidates
        posterior = combined_likelihood * self.prior_match_prob
        
        # Normalize to [0, 1]
        posterior = min(1.0, max(0.0, posterior))
        
        return posterior
    
    def set_thresholds(
        self, 
        confidence_threshold: float = None, 
        positional_sigma_threshold: float = None
    ) -> None:
        """Set matching thresholds."""
        if confidence_threshold is not None:
            if not (0.0 <= confidence_threshold <= 1.0):
                raise ValueError("confidence_threshold must be in [0, 1]")
            self.confidence_threshold = confidence_threshold
        
        if positional_sigma_threshold is not None:
            if positional_sigma_threshold <= 0:
                raise ValueError("positional_sigma_threshold must be positive")
            self.positional_sigma_threshold = positional_sigma_threshold
        
        logger.info(f"Thresholds updated: conf={self.confidence_threshold}, sigma={self.positional_sigma_threshold}")
    
    def get_calibration_metrics(self) -> Dict[str, float]:
        """Get calibration metrics."""
        return self.calibration_metrics.copy()
    
    def set_calibration_metrics(self, accuracy: float, precision: float, recall: float) -> None:
        """Set calibration metrics from test set."""
        self.calibration_metrics = {"accuracy": accuracy, "precision": precision, "recall": recall}
    
    def _positional_likelihood(self, source_ref: Source, source_cand: Source) -> float:
        """Compute positional likelihood."""
        distance_deg = self._angular_distance(
            source_ref.coordinate.ra, source_ref.coordinate.dec,
            source_cand.coordinate.ra, source_cand.coordinate.dec
        )
        
        # Use total uncertainty (combined from both sources)
        combined_error = 0.1  # Default 0.1 arcsec
        
        if source_ref.uncertainty and source_cand.uncertainty:
            # RMS of errors
            combined_error_arcsec = np.sqrt(
                source_ref.uncertainty.ra_error**2 + 
                source_cand.uncertainty.ra_error**2
            )
            combined_error = combined_error_arcsec / 3600.0
        
        distance_arcsec = distance_deg * 3600.0
        combined_error_arcsec = combined_error * 3600.0
        
        # Gaussian likelihood
        sigma = combined_error_arcsec
        likelihood = np.exp(-(distance_arcsec**2) / (2 * sigma**2))
        
        return likelihood
    
    def _photometric_likelihood(self, source_ref: Source, source_cand: Source) -> float:
        """Compute photometric likelihood."""
        # Find common bands
        ref_bands = {p.band: p.magnitude for p in source_ref.photometry}
        cand_bands = {p.band: p.magnitude for p in source_cand.photometry}
        
        common_bands = set(ref_bands.keys()) & set(cand_bands.keys())
        
        if not common_bands:
            # No common bands - neutral likelihood
            return 1.0
        
        # Compute magnitude difference for common bands
        mag_diffs = []
        for band in common_bands:
            diff = abs(ref_bands[band] - cand_bands[band])
            mag_diffs.append(diff)
        
        mean_diff = np.mean(mag_diffs)
        
        # Gaussian likelihood with 0.5 magnitude tolerance
        tolerance = 0.5
        likelihood = np.exp(-(mean_diff**2) / (2 * tolerance**2))
        
        return likelihood
    
    def _positional_significance(self, source_ref: Source, source_cand: Source) -> float:
        """Compute positional significance in sigma."""
        distance_deg = self._angular_distance(
            source_ref.coordinate.ra, source_ref.coordinate.dec,
            source_cand.coordinate.ra, source_cand.coordinate.dec
        )
        
        combined_error = 0.1  # Default arcsec
        if source_ref.uncertainty and source_cand.uncertainty:
            combined_error_arcsec = np.sqrt(
                source_ref.uncertainty.ra_error**2 + 
                source_cand.uncertainty.ra_error**2
            )
            combined_error = combined_error_arcsec / 3600.0
        
        distance_arcsec = distance_deg * 3600.0
        combined_error_arcsec = combined_error * 3600.0
        
        # Significance in sigma
        if combined_error_arcsec > 0:
            significance = distance_arcsec / combined_error_arcsec
        else:
            significance = float('inf') if distance_arcsec > 0 else 0.0
        
        return significance
    
    def _photometric_consistency(self, source_ref: Source, source_cand: Source) -> float:
        """Compute photometric consistency score (0-1)."""
        ref_bands = {p.band: p.magnitude for p in source_ref.photometry}
        cand_bands = {p.band: p.magnitude for p in source_cand.photometry}
        
        common_bands = set(ref_bands.keys()) & set(cand_bands.keys())
        
        if not common_bands:
            return 0.5  # Neutral if no common bands
        
        # RMS magnitude difference
        mag_diffs = [abs(ref_bands[b] - cand_bands[b]) for b in common_bands]
        rms_diff = np.sqrt(np.mean(np.array(mag_diffs)**2))
        
        # Convert to consistency score (1 = perfect, 0 = very different)
        consistency = np.exp(-rms_diff**2 / (2 * 0.5**2))
        
        return consistency
    
    @staticmethod
    def _angular_distance(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
        """Compute angular distance in degrees (simple Euclidean, not Haversine)."""
        return np.sqrt((ra1 - ra2)**2 + (dec1 - dec2)**2)
