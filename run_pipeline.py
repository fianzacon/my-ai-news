"""
Simple runner script for the AI News Intelligence Pipeline.

Usage:
    python run_pipeline.py
"""
import sys
import os

# Fix Windows console encoding for Unicode characters
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass  # Python < 3.7 doesn't have reconfigure

# Add parent directory to path to import pipeline
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipeline import main

if __name__ == "__main__":
    print("=" * 60)
    print("AI NEWS INTELLIGENCE PIPELINE FOR LOTTE MEMBERS")
    print("=" * 60)
    print()
    
    # Run the pipeline
    stats = main()
    
    if stats:
        print("\n" + "=" * 60)
        print("[SUCCESS] PIPELINE EXECUTION COMPLETED")
        print("=" * 60)
        print(f"Final output: {stats.final_output_count} Webex messages generated")
        print()
        
        # Check for warnings
        if stats.regulatory_articles_found > stats.regulatory_articles_retained:
            print("[WARNING] Some regulatory articles may have been dropped!")
            print(f"   Found: {stats.regulatory_articles_found}")
            print(f"   Retained: {stats.regulatory_articles_retained}")
            sys.exit(1)
        
        if stats.final_output_count == 0:
            print("[WARNING] No output generated")
            sys.exit(1)
    else:
        print("\n[ERROR] PIPELINE FAILED - Check logs for details")
        sys.exit(1)
