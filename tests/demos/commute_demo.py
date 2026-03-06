#!/usr/bin/env python3
"""
Demo script for Route Scout
Shows how to use the NJ-NYC commute analyzer
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agents.route_scout import analyze_commute
from datetime import datetime


def main():
    """Run a demo commute analysis"""
    print("\n" + "=" * 80)
    print("🎬 ROUTE SCOUT DEMO")
    print("=" * 80)
    print("\nThis demo will analyze commute options from New Brunswick, NJ to Penn Station, NYC")
    print("and send recommendations to the configured email address.\n")

    try:
        # Run demo analysis
        today = datetime.now().strftime('%Y-%m-%d')
        analyze_commute(
            recipient_email="demo@example.com",
            analyze_for_date=today,
            verbose=True,
            preferred_mode="nj_transit"
        )

        print("\n✅ Demo completed successfully!")
        print("\n📝 Next steps:")
        print("1. Check your email for the commute analysis and recommendations")
        print("2. Review the ranked options (BEST to WORST)")
        print("3. Try different dates with: python agents/route_scout.py --date 'YYYY-MM-DD'")
        print("4. Try different preferences: python agents/route_scout.py --prefer 'path'")
        print("5. Run: python agents/route_scout.py --help for all options\n")

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
