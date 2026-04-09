#!/usr/bin/env python3
"""
AstroBridge Interactive Live Demo

Demonstrates all capabilities with live user input:
- Query by object name
- Query by coordinates (cone search)
- Natural language queries
- Object identification
- Cross-matching and confidence scoring
- Analytics and benchmarking

Run: python interactive_demo.py
"""

import asyncio
import sys
from typing import Optional

from astrobridge.api import AstroBridgeOrchestrator, QueryRequest
from astrobridge.api.schemas import CoordinateRequest
from astrobridge.analytics import AnalyticsEvent, AnalyticsStore
from astrobridge.benchmarking import BenchmarkConfig, BenchmarkRunner
from astrobridge.connectors import NEDConnector, SimbadConnector
from astrobridge.identify import format_identification, identify_object
from astrobridge.matching import BayesianMatcher
from astrobridge.models import Source
from astrobridge.routing import NLPQueryRouter


def print_header(text: str) -> None:
    """Print a formatted header."""
    print(f"\n{'='*70}")
    print(f"  {text}")
    print(f"{'='*70}\n")


def print_section(text: str) -> None:
    """Print a formatted section."""
    print(f"\n{text}")
    print("-" * len(text))


async def demo_name_query(orchestrator: AstroBridgeOrchestrator) -> None:
    """Demo: Query by object name."""
    print_header("QUERY BY OBJECT NAME")
    
    name = input("Enter object name (e.g., 'Proxima Centauri', 'M31', 'Sirius'): ").strip()
    if not name:
        print("Skipped.")
        return
    
    print(f"\nQuerying for: {name}")
    
    request = QueryRequest(
        query_type="name",
        name=name,
        auto_route=True,
    )
    
    response = await orchestrator.execute_query(request)
    
    print_section("Results")
    print(f"Status: {response.status}")
    print(f"Execution time: {response.execution_time_ms:.2f}ms")
    print(f"Catalogs queried: {', '.join(response.catalogs_queried)}")
    print(f"Sources found: {len(response.sources)}")
    print(f"Matches found: {len(response.matches)}")
    
    if response.sources:
        print_section("Sources")
        for i, source in enumerate(response.sources[:5], 1):  # Show top 5
            print(f"\n{i}. {source.name}")
            print(f"   Position: RA={source.coordinate.ra:.4f}°, Dec={source.coordinate.dec:.4f}°")
            if source.photometry:
                mags = [f"{p.band}={p.magnitude:.2f}" for p in source.photometry[:3]]
                print(f"   Magnitudes: {', '.join(mags)}")
            print(f"   Source: {source.provenance.catalog_name}")
    
    if response.matches:
        print_section("Cross-Matches")
        for i, match in enumerate(response.matches[:5], 1):  # Show top 5
            print(f"\n{i}. {match.source1_id} ↔ {match.source2_id}")
            print(f"   Probability: {match.match_probability:.4f}")
            print(f"   Separation: {match.separation_arcsec:.2f}″")
            print(f"   Confidence: {match.confidence:.4f}")
    
    if response.errors:
        print_section("Errors")
        for error in response.errors:
            print(f"  ⚠ {error}")


async def demo_coordinate_query(orchestrator: AstroBridgeOrchestrator) -> None:
    """Demo: Query by coordinates."""
    print_header("QUERY BY COORDINATES")
    
    print("Enter celestial coordinates for cone search:")
    try:
        ra = float(input("  RA (degrees, 0-360): "))
        dec = float(input("  Dec (degrees, -90 to 90): "))
        radius = float(input("  Search radius (arcseconds, default 60): ") or "60")
        
        if not (0 <= ra <= 360):
            print("Invalid RA. Must be 0-360.")
            return
        if not (-90 <= dec <= 90):
            print("Invalid Dec. Must be -90 to 90.")
            return
    except ValueError:
        print("Invalid input.")
        return
    
    print(f"\nQuerying cone: RA={ra}°, Dec={dec}°, Radius={radius}″")
    
    request = QueryRequest(
        query_type="coordinates",
        coordinates=CoordinateRequest(ra=ra, dec=dec, radius_arcsec=radius),
        auto_route=False,
        catalogs=["simbad", "ned"],
    )
    
    response = await orchestrator.execute_query(request)
    
    print_section("Results")
    print(f"Status: {response.status}")
    print(f"Execution time: {response.execution_time_ms:.2f}ms")
    print(f"Sources found: {len(response.sources)}")
    print(f"Matches found: {len(response.matches)}")
    
    if response.sources:
        print_section("Sources in cone")
        for i, source in enumerate(response.sources[:10], 1):
            print(f"\n{i}. {source.name}")
            sep = ((source.coordinate.ra - ra) ** 2 + (source.coordinate.dec - dec) ** 2) ** 0.5 * 3600
            print(f"   Position: RA={source.coordinate.ra:.4f}°, Dec={source.coordinate.dec:.4f}°")
            print(f"   Separation from query: {sep:.2f}″")
            print(f"   Source: {source.provenance.catalog_name}")


async def demo_natural_language_query(orchestrator: AstroBridgeOrchestrator) -> None:
    """Demo: Natural language query."""
    print_header("NATURAL LANGUAGE QUERY")
    
    query = input("Describe what you're looking for (e.g., 'Find nearby red dwarf stars'): ").strip()
    if not query:
        print("Skipped.")
        return
    
    print(f"\nQuery: {query}")
    
    request = QueryRequest(
        query_type="natural_language",
        description=query,
        auto_route=True,
    )
    
    response = await orchestrator.execute_query(request)
    
    print_section("Routing Analysis")
    print(f"Routing reasoning:\n{response.routing_reasoning}")
    print(f"\nCatalogs selected: {', '.join(response.catalogs_queried)}")
    
    print_section("Results")
    print(f"Status: {response.status}")
    print(f"Execution time: {response.execution_time_ms:.2f}ms")
    print(f"Sources found: {len(response.sources)}")
    print(f"Matches found: {len(response.matches)}")
    
    if response.sources:
        print_section("Sample sources")
        for i, source in enumerate(response.sources[:5], 1):
            print(f"\n{i}. {source.name}")
            print(f"   RA={source.coordinate.ra:.4f}°, Dec={source.coordinate.dec:.4f}°")
            print(f"   From: {source.provenance.catalog_name}")


async def demo_object_identification() -> None:
    """Demo: Object identification."""
    print_header("OBJECT IDENTIFICATION")
    
    target = input("Enter an object name or description (e.g., 'M31', 'a red dwarf'): ").strip()
    if not target:
        print("Skipped.")
        return
    
    print(f"\nIdentifying: {target}")
    
    result = identify_object(target)
    
    print_section("Identification Result")
    print(format_identification(result))


async def demo_benchmarking(orchestrator: AstroBridgeOrchestrator) -> None:
    """Demo: Benchmarking."""
    print_header("PERFORMANCE BENCHMARKING")
    
    print("This will run multiple queries and measure latency.")
    try:
        iterations = int(input("Number of iterations (default 3): ") or "3")
    except ValueError:
        iterations = 3
    
    print(f"\nRunning benchmark with {iterations} iterations...")
    
    config = BenchmarkConfig(iterations=iterations)
    runner = BenchmarkRunner(orchestrator, config)
    
    results = await runner.run()
    
    print_section("Benchmark Results")
    print(f"Total queries: {results.total_queries}")
    print(f"Successful: {results.successful_count}")
    print(f"Failed: {results.failed_count}")
    print(f"\nLatency Statistics:")
    print(f"  Mean: {results.mean_latency_ms:.2f}ms")
    print(f"  Median (P50): {results.p50_latency_ms:.2f}ms")
    print(f"  P95: {results.p95_latency_ms:.2f}ms")
    print(f"  Max: {results.max_latency_ms:.2f}ms")


async def demo_matcher_controls(orchestrator: AstroBridgeOrchestrator) -> None:
    """Demo: Advanced matcher controls."""
    print_header("ADVANCED MATCHER CONTROLS")
    
    name = input("Enter object name for cross-match testing: ").strip()
    if not name:
        print("Skipped.")
        return
    
    print(f"\nQuery: {name}")
    print("\nTesting different weighting profiles:")
    
    profiles = ["balanced", "position_first", "photometry_first"]
    
    for profile in profiles:
        request = QueryRequest(
            query_type="name",
            name=name,
            auto_route=True,
            weighting_profile=profile,
        )
        
        response = await orchestrator.execute_query(request)
        
        print(f"\n{profile.upper()}:")
        print(f"  Matches found: {len(response.matches)}")
        if response.matches:
            match = response.matches[0]
            print(f"  Top match confidence: {match.confidence:.4f}")


async def main() -> None:
    """Main interactive demo loop."""
    print_header("AstroBridge Interactive Live Demo v0.3.0")
    
    print("Initializing orchestrator...")
    
    # Create orchestrator
    orchestrator = AstroBridgeOrchestrator()
    
    # Add connectors (local + optional live)
    try:
        from astrobridge.connectors import NedTapAdapter, SimbadTapAdapter
        print("✓ Live TAP adapters available")
        orchestrator.add_connector("simbad", SimbadTapAdapter())
        orchestrator.add_connector("ned", NedTapAdapter())
    except (ImportError, Exception):
        print("⚠ Live TAP adapters not available (install [live])")
        print("  Using local synthetic connectors...")
        orchestrator.add_connector("simbad", SimbadConnector())
        orchestrator.add_connector("ned", NEDConnector())
    
    # Set router and matcher
    orchestrator.set_router(NLPQueryRouter())
    orchestrator.set_matcher(BayesianMatcher(proper_motion_aware=True))
    
    print("✓ Orchestrator ready\n")
    
    # Main menu loop
    while True:
        print("\n" + "="*70)
        print("  MAIN MENU")
        print("="*70)
        print("""
1. Query by object name
2. Query by coordinates (cone search)
3. Natural language query
4. Object identification
5. Advanced matcher controls
6. Performance benchmarking
7. Exit
        """)
        
        choice = input("Select option (1-7): ").strip()
        
        try:
            if choice == "1":
                await demo_name_query(orchestrator)
            elif choice == "2":
                await demo_coordinate_query(orchestrator)
            elif choice == "3":
                await demo_natural_language_query(orchestrator)
            elif choice == "4":
                await demo_object_identification()
            elif choice == "5":
                await demo_matcher_controls(orchestrator)
            elif choice == "6":
                await demo_benchmarking(orchestrator)
            elif choice == "7":
                print("\n✓ Thanks for using AstroBridge!")
                sys.exit(0)
            else:
                print("Invalid choice. Please try again.")
        except KeyboardInterrupt:
            print("\n\n✓ Demo interrupted by user.")
            sys.exit(0)
        except Exception as e:
            print(f"\n⚠ Error: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    print("\n🔭 AstroBridge Interactive Demo")
    print("Starting live demo...\n")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n✓ Goodbye!")
        sys.exit(0)
