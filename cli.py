import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def parse(argv):
    p = argparse.ArgumentParser(
        prog="docker compose run --rm eval",
        description="Run the L03 set against the PayPilot stand.")
    p.add_argument("--profile", metavar="NAME",
                   help="switch the stand to this profile before the run")
    p.add_argument("--settings", metavar="JSON",
                   help="X-Stand-Settings for every /chat request, "
                        "e.g. '{\"model\": \"google/gemini-2.5-flash\"}'")
    p.add_argument("--only", metavar="IDS",
                   help="run only these cases, comma-separated")
    p.add_argument("--set", dest="set_name", metavar="NAME",
                   help="read sets/<NAME>.jsonl")
    p.add_argument("--gate", choices=["daily", "release", "all"],
                   help="which gate's cases to run, daily by default")
    p.add_argument("--brief", action="store_true",
                   help="one line per case, without the case details")
    p.add_argument("--dry-run", action="store_true",
                   help="print the set hash and coverage, call nothing")
    return p.parse_args(argv)


def main(argv):
    if argv and not argv[0].startswith("-"):
        program = sys.executable if argv[0] == "python" else argv[0]
        return subprocess.call([program, *argv[1:]])

    args = parse(argv)
    if args.settings is not None:
        try:
            parsed = json.loads(args.settings)
        except json.JSONDecodeError as e:
            print(f"--settings is not valid JSON: {e.msg}")
            return 2
        if not isinstance(parsed, dict):
            print("--settings must be a JSON object")
            return 2
        os.environ["STAND_SETTINGS"] = json.dumps(parsed)
    if args.only is not None:
        os.environ["CASE"] = args.only
    if args.set_name is not None:
        os.environ["SET"] = args.set_name
    if args.gate is not None:
        os.environ["GATE"] = "" if args.gate == "all" else args.gate

    if args.brief:
        os.environ["BRIEF"] = "1"

    if args.dry_run:
        return subprocess.call([sys.executable, str(HERE / "validate.py")])

    import stand

    if args.profile is not None:
        try:
            stand.wait_until_ready()
            stand.set_profile(args.profile)
        except stand.StandError as e:
            print(e)
            return 2

    import runner

    return runner.main()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
