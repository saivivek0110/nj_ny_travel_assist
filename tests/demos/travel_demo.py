#!/usr/bin/env python3
"""
Demo script for Week Trip Scout
Shows how to analyze a work week and get recommended travel days
"""

import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agents.week_trip_scout import analyze_travel_week


def main():
    """Run a demo travel week analysis"""
    print("\n" + "=" * 80)
    print("🎬 WEEK TRIP SCOUT DEMO")
    print("=" * 80)
    print("\nThis demo will analyze a specific work week and recommend the best 3 days")
    print("to travel to a city based on weather, disruptions, and travel conditions.\n")

    try:
        # Calculate next Monday
        today = datetime.now()
        days_ahead = 0 - today.weekday()  # 0 = Monday
        if days_ahead <= 0:  # Target day already happened this week
            days_ahead += 7
        next_monday = today + timedelta(days=days_ahead)
        week_date = next_monday.strftime('%Y-%m-%d')

        print(f"📅 Analyzing week of: {week_date}\n")

        # Run demo analysis
        analyze_travel_week(
            source_city="New York",
            destination_city="San Francisco",
            week_start_date=week_date,
            recipient_email="demo@example.com",
            verbose=True
        )

        print("\n✅ Demo completed successfully!")
        print("\n📝 Next steps:")
        print("1. Check your email for the weekly travel analysis")
        print("2. Review the recommended 3 best days (Mon-Fri)")
        print("3. Try your own route and dates:")
        print("   - python agents/week_trip_scout.py -s 'Boston' -d 'New York' --week '2026-03-18'")
        print("4. Run: python agents/week_trip_scout.py --help for all options\n")

    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        print("\n💡 Tips:")
        print("1. Ensure .env file is properly configured")
        print("2. Run 'python utils/setup_auth.py' for Gmail setup")
        print("3. Check API keys are valid (ANTHROPIC_API_KEY, TAVILY_API_KEY)")
        print("4. Use --verbose flag for debugging\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
