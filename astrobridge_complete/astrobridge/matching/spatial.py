"""Spatial indexing for efficient candidate generation."""

import numpy as np

from astrobridge.geometry import angular_distance_deg
from astrobridge.models import Source


class SpatialIndex:
    """Simple spatial index for fast nearest neighbor queries."""
    
    def __init__(self, sources: list[Source], partition_size: int = 100):
        """
        Initialize spatial index.
        
        Args:
            sources: List of sources to index
            partition_size: Number of partitions per axis
        """
        self.sources = sources
        self.partition_size = partition_size
        self.grid: dict[tuple[int, int], list[int]] = {}
        self._build_index()
    
    def _build_index(self) -> None:
        """Build spatial index grid."""
        if not self.sources:
            self.grid = {}
            return
        
        # Extract coordinates
        np.array([
            (s.coordinate.ra, s.coordinate.dec) 
            for s in self.sources
        ])
        
        # Compute grid cells
        self.ra_min, self.ra_max = 0, 360
        self.dec_min, self.dec_max = -90, 90
        
        self.ra_cell_size = (self.ra_max - self.ra_min) / self.partition_size
        self.dec_cell_size = (self.dec_max - self.dec_min) / self.partition_size
        
        self.grid = {}
        for i, source in enumerate(self.sources):
            cell = self._get_cell(source.coordinate.ra, source.coordinate.dec)
            if cell not in self.grid:
                self.grid[cell] = []
            self.grid[cell].append(i)
    
    def _get_cell(self, ra: float, dec: float) -> tuple[int, int]:
        """Get grid cell for coordinates."""
        ra_cell = int((ra - self.ra_min) / self.ra_cell_size)
        dec_cell = int((dec - self.dec_min) / self.dec_cell_size)
        
        ra_cell = max(0, min(ra_cell, self.partition_size - 1))
        dec_cell = max(0, min(dec_cell, self.partition_size - 1))
        
        return (ra_cell, dec_cell)
    
    def query_radius(self, ra: float, dec: float, radius_arcsec: float) -> list[int]:
        """
        Find sources within radius of given coordinates.
        
        Args:
            ra: Query RA in degrees
            dec: Query Dec in degrees
            radius_arcsec: Search radius in arcseconds
            
        Returns:
            List of source indices within radius
        """
        radius_deg = radius_arcsec / 3600.0
        
        cell = self._get_cell(ra, dec)
        candidates = []
        
        # Check neighboring cells
        for dra in [-1, 0, 1]:
            for ddec in [-1, 0, 1]:
                neighbor = (cell[0] + dra, cell[1] + ddec)
                if neighbor in self.grid:
                    candidates.extend(self.grid[neighbor])
        
        # Filter by actual distance
        results = []
        for idx in candidates:
            source = self.sources[idx]
            distance = self._angular_distance(ra, dec, source.coordinate.ra, source.coordinate.dec)
            if distance <= radius_deg:
                results.append(idx)
        
        return results
    
    @staticmethod
    def _angular_distance(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
        """Compute angular distance in degrees (naive, not Haversine)."""
        return angular_distance_deg(ra1, dec1, ra2, dec2)
