# AstroBridge: Bayesian Cross-Matching Algorithm & Scientific Foundations

## Table of Contents

1. [Overview](#overview)
2. [Bayesian Framework](#bayesian-framework)
3. [Positional Likelihood](#positional-likelihood)
4. [Photometric Likelihood](#photometric-likelihood)
5. [Confidence Scoring](#confidence-scoring)
6. [Weighting Profiles](#weighting-profiles)
7. [Proper Motion & Epoch Transformations](#proper-motion--epoch-transformations)
8. [Ambiguity Resolution](#ambiguity-resolution)
9. [Practical Examples](#practical-examples)
10. [Known Limitations & Future Work](#known-limitations--future-work)

---

## Overview

AstroBridge uses **Bayesian probabilistic cross-matching** to identify astronomical sources across multiple catalogs. Rather than using simple positional or photometric cuts, the framework computes the **posterior probability** that two sources are the same object, combining positional and photometric evidence with prior assumptions about stellar populations.

### Why Bayesian?

- **Principled uncertainty handling**: Astrometric and photometric uncertainties are naturally incorporated through likelihood functions
- **Multi-evidence fusion**: Position, magnitude, color, and other properties are combined optimally
- **Interpretability**: Each match has an explicit probability that can be understood and debugged
- **Flexibility**: Weighting profiles allow tuning for different scientific contexts (e.g., stellar vs. extragalactic)

---

## Bayesian Framework

### Core Formula

The posterior probability that two sources match is computed via Bayes' theorem:

$$P(\text{match} \mid \text{data}) = \frac{P(\text{data} \mid \text{match}) \cdot P(\text{match})}{P(\text{data})}$$

Where:
- **$P(\text{match} \mid \text{data})$**: Posterior probability two sources are the same object (what we compute)
- **$P(\text{data} \mid \text{match})$**: Likelihood—probability of observing the measured positions, magnitudes if sources are identical
- **$P(\text{match})$**: Prior probability that a random pair matches (typically 0.7 in AstroBridge)
- **$P(\text{data})$**: Marginal likelihood (normalization constant)

### Implementation in AstroBridge

```python
posterior = likelihood_position * likelihood_photometry * prior_match_prob
```

The implementation simplifies $P(\text{data})$ by assuming it's constant across all candidate matches (it cancels in the comparison), so we compute a **relative posterior** sufficient for ranking candidates.

### Prior Probability

AstroBridge uses **$P(\text{match}) = 0.7$** as default, representing that:
- Most stellar fields have high source densities
- A reasonable fraction of cross-catalog pairs are genuine matches
- This prior is domain-dependent: denser stellar fields may justify higher priors; rare object searches lower priors

**User Control**: The prior is customizable via `prior_match_prob` parameter when initializing the `BayesianMatcher`.

---

## Positional Likelihood

### Gaussian Model for Astrometry

The positional likelihood assumes **Gaussian distributed astrometric uncertainties**:

$$P(\text{position data} \mid \text{match}) = \exp\left(-\frac{d^2_{\text{RA}}}{2\sigma_{\text{RA}}^2}\right) \cdot \exp\left(-\frac{d^2_{\text{Dec}}}{2\sigma_{\text{Dec}}^2}\right)$$

Where:
- **$d_{\text{RA}}$**: Difference in right ascension
- **$d_{\text{Dec}}$**: Difference in declination
- **$\sigma_{\text{RA}}, \sigma_{\text{Dec}}$**: Combined uncertainty (quadrature sum of catalog errors)

### Combined Uncertainty

Catalogs typically provide magnitude-dependent uncertainties. AstroBridge combines them as:

$$\sigma^2_{\text{total}} = \sigma_{\text{ref}}^2 + \sigma_{\text{candidate}}^2$$

This accounts for independent measurement errors from both catalogs.

### Sigma Thresholding

The `positional_sigma_threshold` parameter (default: 3.0 sigma) acts as a strong prior cut:

- Matches beyond 3σ are rejected before Bayesian computation
- This prevents costly likelihood evaluation for obviously mismatched pairs
- In practice, this threshold captures ~99.7% of true matches (3σ of normal distribution)

### Angular Distance Calculation

AstroBridge uses the **Haversine formula** for accurate great-circle distances on the celestial sphere:

$$d = 2 \arcsin\left(\sqrt{\sin^2\left(\frac{\Delta \delta}{2}\right) + \cos(\delta_1)\cos(\delta_2)\sin^2\left(\frac{\Delta \alpha}{2}\right)}\right)$$

Where:
- $\Delta \alpha = \alpha_2 - \alpha_1$ (RA difference)
- $\Delta \delta = \delta_2 - \delta_1$ (Dec difference)
- $\delta_1, \delta_2$ are declinations

This is essential for high-precision astrometry where small-angle approximations fail, especially near poles.

### Realistic Astrometric Errors

Common uncertainties:
- Gaia DR3: 0.05–0.3 arcsec (magnitude-dependent, excellent for bright stars)
- 2MASS: 0.1–0.2 arcsec (infrared, less precise for faint sources)
- SIMBAD: 0.5–5 arcsec (heterogeneous, compilation of many surveys)
- VHS: 0.1–0.2 arcsec (visible HST data, excellent precision)

**Search Radius**: Default 60 arcsec balances:
- Coverage: Most true matches within 1–10 arcsec separation
- Efficiency: Avoids quadratic comparisons of all pairs
- Safety margin: Captures outliers from proper-motion-induced shifts

---

## Photometric Likelihood

### Magnitude Matching

Photometric data provides an **independent evidence stream** for matches:

$$P(\text{mag data} \mid \text{match}) = \exp\left(-\frac{(\Delta m)^2}{2\sigma_m^2}\right)$$

Where:
- **$\Delta m = m_1 - m_2$**: Magnitude difference between sources
- **$\sigma_m$**: Combined photometric uncertainty

### Color Matching (Future Enhancement)

For multi-band photometry, colors provide robust matches across epochs:

$$\Delta \text{color} = (m_{\text{B}} - m_{\text{R}})_1 - (m_{\text{B}} - m_{\text{R}})_2$$

Colors are less affected by variability or extinction than individual magnitudes.

### Why Photometric Matching Matters

1. **Breaks degeneracies**: When multiple sources cluster positionally, photometry disambiguates
2. **Detects errors**: A positionally perfect match with wildly different magnitude flags mismatch
3. **Variable star handling**: RR Lyrae or eclipsing binaries vary in magnitude; photometry tags these
4. **Evolutionary state**: Main-sequence stars have tight color-magnitude correlations; red giants do not

### Photometric Weight Tuning

The weighting between astrometry and photometry is adjustable:
- **Balanced (0.7/0.3)**: Default; position is 2× as important as photometry (standard for stellar matching)
- **Position-first (0.9/0.1)**: For precise astrometry surveys where position is highly reliable
- **Photometry-first (0.4/0.6)**: For variability studies or when measuring properties changes are critical

---

## Confidence Scoring

### Integrated Score Computation

After Bayesian match probability is computed, the confidence score incorporates additional evidences:

$$\text{Confidence} = \text{Astrometric Score} \times \text{Distance Ratio Bonus} \times \text{Photometric Penalty}$$

#### 1. Astrometric Score

Based on separation in combined uncertainty units:

```
If separation > σ_threshold:
    score = 0
Elif separation < 0.5 σ:
    score = 0.99 (nearly perfect match)
Else:
    score = exp(-(separation / σ)²)
```

Exponential decay naturally captures the Gaussian model: tight matches (sub-arcsec) score high; loose matches (multiple-sigma) score low.

#### 2. Distance Ratio Bonus

Considers the separation to the **runner-up candidate** (next-best match):

$$\text{Ratio Bonus} = \min\left(1.5, \frac{d_{\text{runner-up}}}{d_{\text{best}}}\right)$$

**Intuition**: If the best match is 5× closer than the second-best, we're confident. If distances are comparable, ambiguity is high.

**Cap at 1.5×**: Prevents over-weighting when the search space is sparse.

#### 3. Photometric Penalty

Applies a penalty when photometry disagrees:

$$\text{Photometric Penalty} = 0.4 + 0.6 \times \text{Photometric Score}$$

- Perfect photometric match (score = 1.0): penalty = 1.0 (no reduction)
- Moderate disagreement (score = 0.5): penalty = 0.7 (30% reduction)
- Complete disagreement (score = 0.0): penalty = 0.4 (60% reduction)

This prevents photometrically-mismatched pairs from accidentally scoring high due to tight positions.

---

## Weighting Profiles

AstroBridge provides three pre-configured weighting profiles to match different scientific scenarios:

### 1. Balanced (Default)

```
Astrometric weight: 0.7 (70%)
Photometric weight: 0.3 (30%)
```

**Best for**: General stellar cross-matching where both position and brightness are reliable.

**Example**: Gaia ↔ 2MASS matching. Gaia positions are excellent; 2MASS magnitudes probe the infrared. Both are valuable.

### 2. Position-First

```
Astrometric weight: 0.9 (90%)
Photometric weight: 0.1 (10%)
```

**Best for**: High-precision astrometry surveys or when photometry is poorly calibrated.

**Example**: Gaia ↔ Gaia (multi-epoch). Positions are incredibly precise (<1 mas); photometry is secondary.

### 3. Photometry-First

```
Astrometric weight: 0.4 (40%)
Photometric weight: 0.6 (60%)
```

**Best for**: Variability studies, photometric surveys, or when positions are degraded (e.g., wide-field imaging).

**Example**: ZTF ↔ Pan-STARRS. Both are photometric surveys with moderate astrometry; brightness changes are the science.

### Creating Custom Profiles

Users can create custom weighted combinations:

```python
scorer = ConfidenceScorer(
    astrometric_weight=0.8,
    photometric_weight=0.2,
    weighting_profile="custom"
)
```

Weights are automatically normalized internally: `w_ast += w_phot = 1.0`.

---

## Proper Motion & Epoch Transformations

### The Problem: Stellar Kinematics

Stars move! The proper motion of a star (its projected velocity on the sky) can shift its position by **1–10 arcsec per year** for nearby, fast-moving objects.

Example: **Barnard's Star** (v ≈ 10.3 arcsec/yr, one of the fastest-moving stars):
- Position in 2010: RA = 269.454°
- Position in 2020: RA ≈ 269.555° (difference ≈ 0.1°, a shift of ~360 arcsec!)

### Coordinate Transformation

To match sources across epochs, AstroBridge computes positions at a common epoch:

$$\alpha(t) = \alpha_0 + \frac{\mu_\alpha \cos(\delta_0)}{3600} (t - t_0)$$

$$\delta(t) = \delta_0 + \frac{\mu_\delta}{3600} (t - t_0)$$

Where:
- **$\alpha_0, \delta_0$**: Reference epoch position (J2000 standard)
- **$\mu_\alpha, \mu_\delta$**: Proper motion components (arcsec/year, typically from Gaia)
- **$t, t_0$**: Match and reference epochs (in years)
- Division by 3600: Converts arcsec to degrees

### When Proper Motion Matters

**Enable proper-motion-aware matching when**:
1. Matching across large time baselines (>5 years)
2. Matching nearby, high-velocity stars (> 0.1 arcsec/yr)
3. Matching against ancient catalogs (e.g., FK5 from 1991)

**Can safely disable when**:
1. Matching modern surveys (all within ~2020)
2. Matching distant/faint objects (proper motions < 0.01 arcsec/yr)
3. Matching galaxies or QSOs (proper motions ≈ 0)

### Benchmark: Gaia Proper Motions

Gaia DR3 provides proper motions for ~1.8 billion stars with median uncertainties:
- Nearby stars (< 100 pc): ~0.01 mas/yr
- Distant stars (> 10 kpc): ~0.1–1 mas/yr (still measurable!)

This enables cross-matching across the entire observational timeline of astronomy.

---

## Ambiguity Resolution

### The Problem: Crowded Fields

In dense stellar regions (globular clusters, Milky Way plane), a single reference source may have multiple candidate matches within the search radius. Classic approaches:

1. **Closest match only**: Ignores information about second-best candidate
2. **Greedy assignment**: Risk of misallocation in symmetric scenarios
3. **Bayesian**: Compute posterior for each candidate; pick highest-probability

### Runner-Up Separation

AstroBridge computes the separation to the **next-best candidate** (runner-up) and uses it to inform confidence:

$$\text{Ambiguity Index} = \frac{\text{Sep}_{\text{best}}}{\text{Sep}_{\text{runner-up}}}$$

**Interpretation**:
- **Index < 0.5**: Best match is 2× closer than runner-up → high confidence
- **Index ~ 1.0**: Best and runner-up are equally close → ambiguous, lower confidence
- **Index > 2.0**: Runner-up is distance → best match likely correct despite ambiguity

### Many-to-One Prevention

AstroBridge prevents **many-to-one matches** (multiple sources mapping to the same catalog match) through:
1. Iterating over reference sources in a fixed order
2. Computing the best match for each
3. No backtracking or greedy reassignment (simpler, but see future work)

---

## Practical Examples

### Example 1: A Straightforward Match

**Reference Source** (Gaia):
- RA = 269.447°, Dec = -62.679°
- Uncertainties: σ_RA ≈ 0.1 arcsec, σ_Dec ≈ 0.1 arcsec
- Magnitude: G = 9.5

**Candidate Source** (2MASS):
- RA = 269.448°, Dec = -62.680°
- Uncertainties: σ_RA ≈ 0.2 arcsec, σ_Dec ≈ 0.2 arcsec
- Magnitude: J = 8.2

**Calculation**:

1. **Angular separation**:
   - $\Delta RA = -0.001°$ ≈ 3.6 arcsec
   - Combined σ = $\sqrt{0.1^2 + 0.2^2} ≈ 0.22$ arcsec
   - Actually: $\Delta RA \approx 0.001° \times 3600'' = 3.6''$
   - **Sep ≈ 3.6 arcsec = 16.4 σ** ✗ (exceeds 3σ threshold!)

Actually, let me recalculate with realistic numbers:

**Corrected Example 1**:

- $\Delta RA ≈ 0.0001°$ = 0.36 arcsec
- $\Delta Dec ≈ 0.0001°$ = 0.36 arcsec
- Combined σ ≈ $\sqrt{0.1^2 + 0.2^2} ≈ 0.22$ arcsec
- **Sep ≈ 0.51 arcsec ≈ 2.3 σ** ✓

2. **Positional likelihood**:
   $$L_{pos} = \exp\left(-\frac{0.51^2}{2 \times 0.22^2}\right) ≈ 0.97$$

3. **Photometric likelihood** (assuming magnitude difference of 1.3 mag, σ_m ≈ 0.2 mag):
   $$L_{phot} = \exp\left(-\frac{1.3^2}{2 \times 0.2^2}\right) ≈ 2 \times 10^{-20}$$ ✗ (Terrible!)

**Interpretation**: Position is excellent, but magnitudes differ by 6.5σ. This could indicate:
1. Misidentification of the source (different object entirely)
2. Measurement error in one catalog
3. Variability (transient event, stellar flare)
4. Blending (Gaia sees a blend; 2MASS only the bright component)

**Action**: Even with perfect positional match, photometric disagreement would lower confidence. Final score ≈ 0.2–0.4 (low confidence, likely mismatch).

### Example 2: Ambiguous Pair in Crowded Field

**Reference**: Star A at RA = 10.000°, Dec = 0.000°, uncertainty 0.5 arcsec

**Candidates**:
1. Candidate 1: RA = 10.001°, Dec = 0.000°, sep = 3.6 arcsec
2. Candidate 2: RA = 10.0005°, Dec = 0.00075°, sep = 3.2 arcsec (runner-up)

**Scoring**:
- Both exceed σ threshold marginally (if σ_combined ≈ 1 arcsec)
- Candidate 1 is slightly closer
- Distance ratio: $3.2 / 3.6 ≈ 0.89$ → ambiguity bonus = 1.0 (no bonus, equally close)
- Final confidence for Candidate 1: ~0.6 (moderate, due to ambiguity)

**User interpretation**: "This source is likely Candidate 1, but Candidate 2 is plausible. Manual review recommended."

---

## Known Limitations & Future Work

### Current Limitations

1. **No proper-motion uncertainty**: We propagate position, but not the uncertainty on proper motion. This can underestimate positional uncertainty for old proper-motion catalogs.

2. **Magnitude-only photometry**: Colors are not used. Color-magnitude diagrams are powerful for stellar classification but require multi-band data for all sources.

3. **No parallax weighting**: Nearby stars are more likely to be true matches (higher probability density in space). Parallax-weighted matching would improve confidence.

4. **Symmetric uncertainty assumption**: We assume σ_RA = σ_Dec and isotropic uncertainties. Real catalogs have anisotropic errors (especially near poles).

5. **Fixed search radius**: 60 arcsec is a compromise. Adaptive radii (based on catalog uncertainty) would be more principled.

6. **No outlier detection**: If one catalog has a blunder (0.1° error), our algorithm will fail. Robust statistics (e.g., Tukey biweight) could help.

7. **Many-to-one matches**: Currently prevented by iteration order, not optimized assignment. Hungarian algorithm or min-cost matching would be better.

### Future Extensions

1. **Machine Learning**: Train a neural network on labeled cross-matches to learn the true likelihood functions.

2. **Hierarchical Bayesian Model**: Treat population parameters (luminosity function, velocity dispersion) as hyperpriors.

3. **Catalog Combination**: When matching A→B→C, propagate uncertainty through the chain.

4. **Transient Handling**: Special logic for moving targets, variable stars, and nearby objects.

5. **GPU Acceleration**: Large-scale matching could leverage GPU parallelization.

6. **Ensemble Methods**: Combine multiple matching algorithms (voting, confidence weighting) for robustness.

### Validation & Calibration

AstroBridge includes **calibration metrics** (accuracy, precision, recall) computed on labeled test sets:
- Helps identify which thresholds perform best empirically
- Can be saved and used to normalize confidence scores
- Enables offline benchmarking on reference catalogs

---

## References

### Academic Background

- **Bayesian Inference**: Gelman et al., *Bayesian Data Analysis*, 3rd ed. (Chapman & Hall, 2013)
- **Astrometric Matching**: Budavári et al., *Astrophysical Journal* 679, 301 (2008) — foundational cross-match paper
- **Gaia Astrometry**: Gaia Collaboration, Vallenari et al., *Astronomy & Astrophysics* 674, A1 (2023)

### Astronomical Catalogs

- **Gaia**: https://www.cosmos.esa.int/gaia
- **2MASS**: https://www.ipac.caltech.edu/2mass/
- **SIMBAD**: https://simbad.u-strasbg.fr/
- **VHS**: http://vsa.roe.ac.uk/vhs/

### AstroBridge Code

- `astrobridge/matching/probabilistic.py`: Bayesian matcher implementation
- `astrobridge/matching/confidence.py`: Confidence scoring logic
- `astrobridge/matching/spatial.py`: Spatial indexing for efficiency
- `tests/test_matcher.py`: Test cases with expected behaviors

---

## Questions & Debugging

### "Why did this match fail?"

1. Check positional separation: `astrobridge-identify "<source>" --verbose`
2. Review magnitude difference: Large Δm often causes rejection
3. Verify proper-motion correction: Old catalogs may need epoch transformation
4. Check confidence threshold: Lower thresholds are more permissive

### "How do I tune for my use case?"

1. **Stellar photometry**: Use balanced or position-first profile
2. **Variable stars**: Use photometry-first profile; monitor magnitude changes
3. **Fast movers**: Enable proper-motion-aware matching; use old catalog epochs
4. **Crowded fields**: Lower positional threshold; inspect runner-up separations

### "Can I use this for galaxies?"

Yes! Disable proper-motion-aware matching (galaxies don't move), and rely primarily on astrometric matching. Photometric matching is less reliable for extended sources.

---

**Last Updated**: April 2026

For current algorithm details, see source code and run:
```bash
astrobridge-demo  # Walk through all 9 phases
astrobridge-identify "M31"  # See real-world matching in action
```
