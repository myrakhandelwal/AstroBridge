"""Confidence scoring for astronomical source matches."""
import logging
from typing import Optional

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from astrobridge.models import Source

logger = logging.getLogger(__name__)


WEIGHTING_PROFILES = {
    "balanced": (0.7, 0.3),
    "position_first": (0.9, 0.1),
    "photometry_first": (0.4, 0.6),
}


class MatchScore(BaseModel):
    """Result of confidence scoring a source match."""
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0-1)")
    explanation: str = Field(..., description="Human-readable explanation of score")
    
    model_config = ConfigDict(frozen=True)


class ConfidenceScorer:
    """Compute confidence scores for astronomical source matches."""
    
    def __init__(
        self,
        astrometric_weight: float = 0.7,
        photometric_weight: float = 0.3,
        uncertainty_scaling: float = 3.0,
        max_separation_arcsec: float = 1200.0,
        weighting_profile: str = "balanced",
    ):
        """
        Initialize confidence scorer.
        
        Args:
            astrometric_weight: Weight for positional matching (0-1)
            photometric_weight: Weight for photometric matching (0-1)
            uncertainty_scaling: Sigma multiplier for astrometric tolerance
            max_separation_arcsec: Maximum separation to consider (beyond this = ~0 confidence)
        """
        if not (0.0 <= astrometric_weight <= 1.0):
            raise ValueError("astrometric_weight must be in [0, 1]")
        if not (0.0 <= photometric_weight <= 1.0):
            raise ValueError("photometric_weight must be in [0, 1]")
        if astrometric_weight + photometric_weight == 0.0:
            raise ValueError("At least one weight must be non-zero")
        
        # Normalize weights
        total = astrometric_weight + photometric_weight
        self.astrometric_weight = astrometric_weight / total
        self.photometric_weight = photometric_weight / total
        
        self.uncertainty_scaling = uncertainty_scaling
        self.max_separation_arcsec = max_separation_arcsec
        self.weighting_profile = weighting_profile

    @classmethod
    def from_profile(
        cls,
        profile: str,
        uncertainty_scaling: float = 3.0,
        max_separation_arcsec: float = 1200.0,
    ) -> "ConfidenceScorer":
        """Create scorer from a named weighting profile."""
        if profile not in WEIGHTING_PROFILES:
            raise ValueError(
                f"Unknown weighting profile '{profile}'. "
                f"Supported profiles: {', '.join(sorted(WEIGHTING_PROFILES.keys()))}"
            )
        astrometric_weight, photometric_weight = WEIGHTING_PROFILES[profile]
        return cls(
            astrometric_weight=astrometric_weight,
            photometric_weight=photometric_weight,
            uncertainty_scaling=uncertainty_scaling,
            max_separation_arcsec=max_separation_arcsec,
            weighting_profile=profile,
        )
    
    def compute_score(
        self,
        source1: Source,
        source2: Source,
        separation_arcsec: float,
        runner_up_separation_arcsec: Optional[float] = None
    ) -> MatchScore:
        """
        Compute confidence score for a potential match.
        
        Args:
            source1: First source
            source2: Second source
            separation_arcsec: Angular separation in arcseconds
            runner_up_separation_arcsec: Distance to next-best candidate (if known)
            
        Returns:
            MatchScore with confidence and explanation
        """
        # If separation exceeds max, confidence is near zero
        if separation_arcsec > self.max_separation_arcsec:
            explanation = (
                f"Separation ({separation_arcsec:.1f} arcsec) exceeds maximum threshold "
                f"({self.max_separation_arcsec} arcsec). Match rejected."
            )
            return MatchScore(confidence=0.02, explanation=explanation)
        
        # Compute astrometric confidence
        astrometric_score = self._score_astrometric(source1, source2, separation_arcsec)
        
        # Compute photometric confidence
        photometric_score = self._score_photometric(source1, source2)
        has_photometric_signal = photometric_score is not None
        
        # Apply distance ratio bonus if runner-up available
        distance_ratio = 1.0
        if runner_up_separation_arcsec is not None and runner_up_separation_arcsec > 0:
            distance_ratio = runner_up_separation_arcsec / (separation_arcsec + 1e-6)
            # Cap ratio bonus at 1.5x
            distance_ratio = min(distance_ratio, 1.5)
        
        # Weighted combination with adaptive weights when photometry is unavailable.
        if has_photometric_signal and photometric_score is not None:
            combined_score = (
                self.astrometric_weight * astrometric_score +
                self.photometric_weight * photometric_score
            ) * distance_ratio
            # Penalize matches when photometry strongly disagrees even if positions are close.
            photometric_penalty = 0.4 + 0.6 * photometric_score
            combined_score *= photometric_penalty
        else:
            combined_score = astrometric_score * distance_ratio
        
        # Clamp to [0, 1]
        final_confidence = min(1.0, max(0.0, combined_score))
        
        # Build explanation
        explanation = self._build_explanation(
            separation_arcsec,
            source1,
            source2,
            astrometric_score,
            photometric_score,
            has_photometric_signal,
            distance_ratio,
            final_confidence
        )
        
        return MatchScore(confidence=final_confidence, explanation=explanation)
    
    def _score_astrometric(self, source1: Source, source2: Source, separation_arcsec: float) -> float:
        """
        Score based on positional agreement and uncertainties.
        
        Args:
            source1: First source
            source2: Second source
            separation_arcsec: Separation in arcseconds
            
        Returns:
            Astrometric score (0-1)
        """
        # Combined uncertainty (quadrature sum)
        ra_err = source1.uncertainty.ra_error
        dec_err = source1.uncertainty.dec_error
        combined_uncertainty = (ra_err ** 2 + dec_err ** 2) ** 0.5
        
        # Also account for target uncertainty
        target_ra_err = source2.uncertainty.ra_error
        target_dec_err = source2.uncertainty.dec_error
        target_uncertainty = (target_ra_err ** 2 + target_dec_err ** 2) ** 0.5
        
        # Total expected uncertainty
        total_uncertainty = (combined_uncertainty ** 2 + target_uncertainty ** 2) ** 0.5
        
        # Use an uncertainty-aware scale, but keep a realistic floor for cross-catalog matching.
        # This keeps moderate separations plausible while strongly penalizing very large offsets.
        effective_scale_arcsec = max(60.0, total_uncertainty * 300.0)
        ratio = separation_arcsec / (effective_scale_arcsec + 1e-6)
        astrometric_score = max(0.0, 1.0 - ratio ** 1.25)
        
        return float(astrometric_score)
    
    def _score_photometric(self, source1: Source, source2: Source) -> Optional[float]:
        """
        Score based on photometric agreement.
        
        Args:
            source1: First source
            source2: Second source
            
        Returns:
            Photometric score (0-1)
        """
        # If either source has no photometry, return None and let caller adapt weights.
        if not source1.photometry or not source2.photometry:
            return None
        
        # Find common bands
        bands1 = {p.band: p.magnitude for p in source1.photometry}
        bands2 = {p.band: p.magnitude for p in source2.photometry}
        common_bands = set(bands1.keys()) & set(bands2.keys())
        
        # If no common bands, can't score photometry.
        if not common_bands:
            return None
        
        # Compute magnitude differences in common bands
        mag_diffs = []
        for band in common_bands:
            mag_diff = abs(bands1[band] - bands2[band])
            mag_diffs.append(mag_diff)
        
        # Defensive check: mag_diffs should never be empty if common_bands is non-empty
        if not mag_diffs:
            logger.warning(
                "Photometric scoring: common_bands non-empty but mag_diffs empty. "
                "This should not happen. Returning None."
            )
            return None
        
        mean_mag_diff = sum(mag_diffs) / len(mag_diffs)
        
        # Keep scoring consistent with BayesianMatcher photometric likelihood.
        tolerance = 0.5
        photometric_score = float(np.exp(-(mean_mag_diff ** 2) / (2 * tolerance ** 2)))
        
        return photometric_score
    
    def _build_explanation(
        self,
        separation_arcsec: float,
        source1: Source,
        source2: Source,
        astrometric_score: float,
        photometric_score: Optional[float],
        has_photometric_signal: bool,
        distance_ratio: float,
        final_confidence: float
    ) -> str:
        """Build human-readable explanation of score."""
        parts = []
        
        # Confidence level
        if final_confidence > 0.85:
            level = "EXCELLENT"
        elif final_confidence > 0.7:
            level = "GOOD"
        elif final_confidence > 0.5:
            level = "MODERATE"
        elif final_confidence > 0.25:
            level = "POOR"
        else:
            level = "VERY POOR"
        
        parts.append(f"Match Confidence: {level} ({final_confidence:.2f})")
        
        # Astrometric
        separation_label = "low" if separation_arcsec <= 5.0 else "moderate" if separation_arcsec <= 120.0 else "large"
        parts.append(
            f"Astrometric: {astrometric_score:.2f} "
            f"({separation_label} separation: {separation_arcsec:.1f} arcsec)"
        )
        
        # Photometric
        if has_photometric_signal and photometric_score is not None:
            parts.append(f"Photometric: {photometric_score:.2f}")
        else:
            parts.append("Photometric: unavailable (astrometric-only confidence)")

        parts.append(
            f"Weighting: {self.weighting_profile} "
            f"(A={self.astrometric_weight:.2f}, P={self.photometric_weight:.2f})"
        )
        
        # Distance ratio
        if distance_ratio > 1.0:
            parts.append(f"Distance ratio bonus applied: {distance_ratio:.2f}x")
        
        # Sources
        parts.append(f"Sources: {source1.name} <-> {source2.name}")
        parts.append(f"Catalogs: {source1.provenance.catalog_name} <-> {source2.provenance.catalog_name}")
        
        return " | ".join(parts)
