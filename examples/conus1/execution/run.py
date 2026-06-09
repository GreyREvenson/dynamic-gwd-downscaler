import os
import sys
import argparse

def main():
    parser = argparse.ArgumentParser(description="Run the twt workflow for a single namelist.")
    parser.add_argument("namelist", help="Path to namelist.yaml")
    parser.add_argument("--src", help="Optional path to add to sys.path before importing twt modules (e.g., ../src)")
    args = parser.parse_args()

    if args.src:
        sys.path.append(os.path.abspath(args.src))

    if not os.path.isfile(args.namelist):
        raise SystemExit(f"ERROR: namelist not found: {args.namelist}")

    try:
        import twtmain
    except ImportError:
        print("ERROR: Could not import twtmain. Use --src to add the source path if needed.")
        raise

    twtmain.calculate_async_wrapper(args.namelist)

if __name__ == "__main__":
    main()