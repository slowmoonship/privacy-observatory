#!/usr/bin/env python3
"""Check paths reachable from the V0.2 public history boundary."""
import argparse
import subprocess

from prepare_public_site import CATALOG, ROOT

LEGACY_BASE = "3ffd1e31066e4249d8b4b50727bd2b9c5d131e06"
RETIRED = {f"public/data/{name}.json" for name in ("activity", "market", "pools")}
APPROVED_CODE = {
    ".github/workflows/update.yml", "README.md", "docs/v0.2-release.md",
    "package.json", "package-lock.json", "tests/test_update_data.py", "vite.config.ts", "src/main.tsx", "src/datasets.tsx", "src/style.css",
    "scripts/prepare_public_site.py", "scripts/export_public_inputs.py", "scripts/requirements-datasets.txt",
    "scripts/refresh_datasets.py", "scripts/check_public_git.py", "tests/pages-datasets.cjs",
    "tests/phase3_public.py", "tests/phase4_refresh.py",
}
DATA_PATHS = {
    f"datasets/{name}/{filename}"
    for name, policy in CATALOG.items()
    for filename in ("manifest.json",) + (
        ("schema.json", f"{name}.csv", f"{name}.parquet") if policy["status"] != "Blocked" else ())
}


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).splitlines()


def check(base, tip):
    subprocess.run(["git", "merge-base", "--is-ancestor", base, tip], cwd=ROOT, check=True)
    names = set(git("ls-tree", "-r", "--name-only", tip))
    if names & RETIRED or {p for p in names if p.startswith("datasets/")} != DATA_PATHS:
        raise ValueError("Unexpected dataset files in the public commit tree")
    for line in git("rev-list", "--objects", tip, "^" + base):
        _, separator, path = line.partition(" ")
        if not separator or not path:
            continue
        allowed = APPROVED_CODE | DATA_PATHS
        if path not in allowed and not any(p.startswith(path + "/") for p in allowed):
            raise ValueError(f"Unapproved newly reachable Git path: {path}")
    for sha in git("rev-list", f"{base}..{tip}"):
        touched = {p for p in git("diff-tree", "--no-renames", "--no-commit-id", "--name-only", "-r", "-m", sha) if p}
        rejected = touched - APPROVED_CODE - DATA_PATHS - RETIRED
        if rejected:
            raise ValueError(f"Unapproved path in {sha}: {sorted(rejected)}")
    print(f"Public history gate passed: {base}..{tip}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default=LEGACY_BASE)
    parser.add_argument("--tip", default="HEAD")
    args = parser.parse_args()
    check(args.base, args.tip)
