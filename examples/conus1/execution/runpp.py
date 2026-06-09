import os
import sys
import argparse
import multiprocessing

def main():
    parser = argparse.ArgumentParser(description="Run twtmain over multiple subdomains in parallel.")
    parser.add_argument("dir_subdomains", help="Directory containing subdirectories with namelist.yaml")
    parser.add_argument("--n-cores", type=int, default=os.cpu_count(), help="Number of processes to use (default: os.cpu_count())")
    parser.add_argument("--src", help="Optional path to add to sys.path before importing twtmain (e.g., ../src)")
    args = parser.parse_args()

    if args.src:
        sys.path.append(os.path.abspath(args.src))

    try:
        import twtmain
    except ImportError as ex:
        print("ERROR: Could not import twtmain. Use --src to add the source path if needed.")
        raise

    if not os.path.isdir(args.dir_subdomains):
        raise SystemExit(f"ERROR: Directory not found: {args.dir_subdomains}")

    tasks = []
    for sub in sorted(os.listdir(args.dir_subdomains)):
        subdir_full = os.path.join(args.dir_subdomains, sub)
        if os.path.isdir(subdir_full):
            fname_namelist = os.path.join(subdir_full, "namelist.yaml")
            if os.path.isfile(fname_namelist):
                tasks.append({"fname_namelist": fname_namelist})
            else:
                print(f"Skipping {subdir_full}: namelist.yaml not found")

    if not tasks:
        raise SystemExit("No namelist.yaml files found under the provided directory.")

    with multiprocessing.Pool(processes=args.n_cores) as pool:
        results_async = [pool.apply_async(twtmain.calculate_async_wrapper, kwds=kwargs) for kwargs in tasks]
        _ = [res.get() for res in results_async]

if __name__ == "__main__":
    main()