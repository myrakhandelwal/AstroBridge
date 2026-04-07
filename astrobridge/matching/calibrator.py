"""Calibration utilities for matcher tuning."""
import logging
import numpy as np
from typing import List, Tuple, Dict, Any
from astrobridge.models import Source, MatchResult

logger = logging.getLogger(__name__)


class MatcherCalibrator:
    """Utility for calibrating matcher parameters against labeled test set."""
    
    @staticmethod
    def evaluate_matches(
        matches: List[MatchResult],
        ground_truth_pairs: List[Tuple[str, str]]
    ) -> Dict[str, float]:
        """
        Evaluate matching results against ground truth.
        
        Args:
            matches: List of MatchResult objects from matcher
            ground_truth_pairs: List of (ref_id, cand_id) true match pairs
            
        Returns:
            Dictionary with accuracy, precision, recall metrics
        """
        # Convert ground truth to set for fast lookup
        truth_set = set(ground_truth_pairs)
        
        # Extract predicted matches
        predicted_set = set(
            (m.source_ref, m.source_match) for m in matches
        )
        
        # Compute metrics
        true_positives = len(predicted_set & truth_set)
        false_positives = len(predicted_set - truth_set)
        false_negatives = len(truth_set - predicted_set)
        
        accuracy = true_positives / len(truth_set) if truth_set else 0.0
        precision = true_positives / len(predicted_set) if predicted_set else 0.0
        recall = true_positives / len(truth_set) if truth_set else 0.0
        
        # F1 score
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        
        metrics = {
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
            "true_positives": true_positives,
            "false_positives": false_positives,
            "false_negatives": false_negatives
        }
        
        logger.info(f"Calibration metrics: acc={accuracy:.3f}, prec={precision:.3f}, recall={recall:.3f}, f1={f1:.3f}")
        
        return metrics
    
    @staticmethod
    def compute_distance_distribution(
        matches: List[MatchResult]
    ) -> Dict[str, float]:
        """
        Compute statistics on match position significances.
        
        Args:
            matches: List of MatchResult objects
            
        Returns:
            Statistics dictionary (mean, std, min, max, median)
        """
        if not matches:
            return {}
        
        significances = [m.position_significance for m in matches]
        probabilities = [m.match_probability for m in matches]
        
        return {
            "position_sig_mean": float(np.mean(significances)),
            "position_sig_std": float(np.std(significances)),
            "position_sig_min": float(np.min(significances)),
            "position_sig_max": float(np.max(significances)),
            "match_prob_mean": float(np.mean(probabilities)),
            "match_prob_std": float(np.std(probabilities))
        }
