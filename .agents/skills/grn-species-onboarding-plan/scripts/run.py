#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
import common


def main():
    parser = argparse.ArgumentParser(description="Species onboarding plan")
    common.add_common_args(parser)
    parser.add_argument("--species-name", required=True)
    parser.add_argument("--intended-capabilities", default=None)
    args = parser.parse_args()
    payload = {
        "species_name": args.species_name,
        "intended_capabilities": [c.strip() for c in args.intended_capabilities.split(",") if c.strip()] if args.intended_capabilities else [],
    }
    if args.http:
        data = common.http_post(args.http, "/api/v1/species/onboarding-plan", payload)
    else:
        sys.path.insert(0, str(common.BACKEND_DIR))
        import main as backend
        data = common.run_async(backend.species_onboarding_plan(backend.SpeciesOnboardingPlanRequest(**payload)))
    common.output(data)


if __name__ == "__main__":
    main()
