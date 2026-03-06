#!/usr/bin/env python3
"""
Demo script for Travel Agent for Work
Demonstrates how to use the Travel Agent with a simple example
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agents.week_trip_scout import analyze_travel_week


def main():
    """Run a demo travel analysis"""
    print("\n🎬 WEEK TRIP SCOUT DEMO")
    print("=" * 70)
    print("\nThis demo will run a travel analysis for San Francisco")
    print("and send recommendations to the configured email address.\n")

    try:
        # Run demo analysis
        analyze_travel_week(
            source_city="New York",
            destination_city="San Francisco",
            week_start_date="2026-03-16", # Example week
            recipient_email="demo@example.com",
            verbose=True
        )

        print("\n✅ Demo completed successfully!")
        print("\n📝 Next steps:")
        print("1. Check your email for the travel recommendations")
        print("2. Modify the city, email, or other parameters as needed")
        print("3. Run: python agents/week_trip_scout.py --help for more options\n")

    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        print("\n💡 Tips:")
        print("1. Ensure .env file is properly configured")
        print("2. Run 'python utils/setup_auth.py' for Gmail setup")
        print("3. Check API keys are valid")
        print("4. Use --verbose flag for debugging\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
