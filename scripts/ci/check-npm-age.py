"""Supply-chain cooldown check for npm lockfiles (ADR-004).

Fails if any package version in package-lock.json was published less than MIN_AGE_DAYS ago, giving the
community time to detect and yank compromised releases. Packages whose registry metadata has no publish time
are reported as warnings (cannot be verified) but do not fail the check.

Usage: python scripts/ci/check-npm-age.py apps/flashcart-web/package-lock.json [--days 14]
"""

import argparse
import concurrent.futures
import datetime as dt
import json
import sys
import urllib.parse
import urllib.request

REGISTRY = "https://registry.npmjs.org/"


def publish_times(name: str) -> dict:
    url = REGISTRY + urllib.parse.quote(name, safe="@")
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 - fixed https registry URL
        return json.load(resp).get("time", {})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("lockfile")
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--exceptions", default="scripts/ci/npm-age-exceptions.txt",
                        help="documented security-fix versions allowed to be newer than the cooldown")
    args = parser.parse_args()
    try:
        with open(args.exceptions, encoding="utf-8") as fh:
            allowed = {line.split("#")[0].strip() for line in fh if line.split("#")[0].strip()}
    except FileNotFoundError:
        allowed = set()

    lock = json.load(open(args.lockfile, encoding="utf-8"))
    pkgs: dict[str, set[str]] = {}
    for path, meta in lock.get("packages", {}).items():
        if not path or meta.get("link"):
            continue
        name = meta.get("name") or path.split("node_modules/")[-1]
        pkgs.setdefault(name, set()).add(meta["version"])

    cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(days=args.days)
    too_new, unknown = [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        for name, times in zip(pkgs, pool.map(publish_times, pkgs), strict=True):
            for version in sorted(pkgs[name]):
                stamp = times.get(version)
                if not stamp:
                    unknown.append(f"{name}@{version}")
                elif dt.datetime.fromisoformat(stamp.replace("Z", "+00:00")) > cutoff:
                    if f"{name}@{version}" in allowed:
                        print(f"ALLOW security-fix exception: {name}@{version} (published {stamp[:10]})")
                        continue
                    too_new.append(f"{name}@{version} (published {stamp[:10]})")

    print(f"checked {sum(len(v) for v in pkgs.values())} package versions; cooldown {args.days} days")
    for item in unknown:
        print(f"WARN no publish time in registry metadata: {item}")
    for item in too_new:
        print(f"FAIL too new: {item}")
    return 1 if too_new else 0


if __name__ == "__main__":
    sys.exit(main())
