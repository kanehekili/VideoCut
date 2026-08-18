#!/usr/bin/env python3
"""
Build a Debian source package (.dsc + orig tarball + debian.tar.xz) for
videocut, for eventual upload to mentors.debian.net / an ITP sponsor.

This is deliberately separate from build.xml's PPA/AUR flow: Debian wants
a source-only, network-free build against a "3.0 (quilt)" package format,
installed under /usr/lib/videocut (not /opt), with no pre-built binaries
committed to the tree - all of which differ from the Ubuntu PPA packaging
in build/DEB-template.

Usage:
    python3 make_debian_source.py [--keep-work] [--no-build]

Requires dpkg-dev (dpkg-source) to produce the final .dsc; without it the
script still assembles the source tree under build/stage-debian/ and stops
after building the orig tarball so the tree can be inspected or handed to
dpkg-source manually on a Debian/Ubuntu box.
"""
import argparse
import email.utils
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

BUILD_DIR = Path(__file__).resolve().parent
SRC_DIR = BUILD_DIR.parent / "src"
TEMPLATE_DIR = BUILD_DIR / "DEB-template-debian"
STAGE_DIR = BUILD_DIR / "stage-debian"
OUT_DIR = BUILD_DIR / "DEB-DEBIAN"

TOKEN_FILES = ["debian/control", "debian/changelog"]


def read_properties(path):
    props = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        props[key.strip()] = value.strip()
    return props


def substitute_tokens(text, tokens):
    for token, value in tokens.items():
        text = text.replace(f"@{token}@", value)
    return text


def copy_payload(pkg_dir, version):
    src_dir = pkg_dir / "src"
    (src_dir / "icons").parent.mkdir(parents=True, exist_ok=True)

    for py_file in sorted(SRC_DIR.glob("*.py")):
        text = py_file.read_text()
        text = substitute_tokens(text, {"xxx": version})
        (src_dir / py_file.name).write_text(text)

    shutil.copytree(SRC_DIR / "icons", src_dir / "icons")

    (src_dir / "data").mkdir(parents=True, exist_ok=True)
    shutil.copy2(SRC_DIR / "data" / "countryIso639.json", src_dir / "data")

    ffmpeg_src = src_dir / "ffmpeg" / "src"
    ffmpeg_src.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SRC_DIR / "ffmpeg" / "src" / "remux5.c", ffmpeg_src)
    shutil.copy2(SRC_DIR / "ffmpeg" / "src" / "makefile", ffmpeg_src)

    lib_dir = src_dir / "lib"
    lib_dir.mkdir(parents=True, exist_ok=True)
    # Intentionally NOT running updateMPV.sh: Debian buildds have no network
    # access during a build, so the vendored copy already checked into git
    # is used as-is. Bump it manually (and re-run this script) when needed.
    shutil.copy2(SRC_DIR / "lib" / "mpv.py", lib_dir)

    addons_dir = pkg_dir / "addons"
    addons_dir.mkdir(parents=True, exist_ok=True)
    for desktop in (TEMPLATE_DIR / "addons").glob("*.desktop"):
        shutil.copy2(desktop, addons_dir)

    shutil.copy2(TEMPLATE_DIR / "makefile", pkg_dir / "makefile")


def make_orig_tarball(stage_dir, pkg_name, version):
    tarball = stage_dir / f"videocut_{version}.orig.tar.gz"
    with tarfile.open(tarball, "w:gz") as tar:
        tar.add(stage_dir / pkg_name, arcname=pkg_name)
    return tarball


def copy_debian_dir(pkg_dir, tokens):
    dest = pkg_dir / "debian"
    shutil.copytree(TEMPLATE_DIR / "debian", dest)
    for rel in TOKEN_FILES:
        f = pkg_dir / rel
        f.write_text(substitute_tokens(f.read_text(), tokens))
    (dest / "rules").chmod(0o755)


def run_dpkg_source(stage_dir, pkg_name, out_dir):
    if shutil.which("dpkg-source") is None:
        print(
            "\ndpkg-source not found on this machine - skipping the final "
            ".dsc build.\nInstall `dpkg-dev` on a Debian/Ubuntu box, then run:\n"
            f"    cd {stage_dir} && dpkg-source -b {pkg_name}\n"
            "The prepared source tree (with orig tarball and debian/ already "
            "in place) is left in place for that."
        )
        return False

    out_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["dpkg-source", "-b", pkg_name],
        cwd=stage_dir,
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    print(result.stderr, file=sys.stderr)
    if result.returncode != 0:
        print("dpkg-source failed - see output above.", file=sys.stderr)
        return False

    for artifact in stage_dir.glob("videocut_*"):
        if artifact.is_file():
            shutil.copy2(artifact, out_dir)

    if shutil.which("lintian"):
        dsc = next(out_dir.glob("videocut_*.dsc"), None)
        if dsc:
            print(f"\nRunning lintian on {dsc.name}:")
            subprocess.run(["lintian", "-I", "--pedantic", str(dsc)])
    else:
        print("\n(lintian not installed - install it to pre-check for policy issues)")

    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep-work", action="store_true",
                         help="keep build/stage-debian/ around after a successful build")
    parser.add_argument("--no-build", action="store_true",
                         help="only assemble the source tree, skip dpkg-source")
    args = parser.parse_args()

    props = read_properties(BUILD_DIR / "build.properties")
    version = props["version"]
    pkgrelease = props["pkgrelease"]
    deps = props.get("debian-lib", "")

    tokens = {
        "xxx": version,
        "xpkgrelx": pkgrelease,
        "xtsx": email.utils.format_datetime(__import__("datetime").datetime.now().astimezone()),
        "xlibsx": deps,
    }

    pkg_name = f"videocut-{version}"
    pkg_dir = STAGE_DIR / pkg_name

    if STAGE_DIR.exists():
        shutil.rmtree(STAGE_DIR)
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    pkg_dir.mkdir(parents=True)

    print(f"Staging upstream payload for videocut {version} ...")
    copy_payload(pkg_dir, version)

    print("Building orig tarball (upstream content only, no debian/) ...")
    make_orig_tarball(STAGE_DIR, pkg_name, version)

    print("Adding debian/ packaging overlay ...")
    copy_debian_dir(pkg_dir, tokens)

    built = False
    if not args.no_build:
        print("Running dpkg-source -b ...")
        built = run_dpkg_source(STAGE_DIR, pkg_name, OUT_DIR)

    if built:
        print(f"\nDone. Source package artifacts are in {OUT_DIR}/")
        print("Next steps:")
        print("  1. lintian -I --pedantic on the .dsc (see above) and fix findings")
        print("  2. File an ITP bug (reportbug wnpp) referencing this package")
        print("  3. Upload to mentors.debian.net for review / sponsorship")
        if not args.keep_work:
            shutil.rmtree(STAGE_DIR)
    else:
        print(f"\nSource tree prepared at {pkg_dir}/ - inspect it or finish the "
              "dpkg-source build there manually.")

    print(
        "\nREMINDER: debian/copyright flags src/icons/* as UNVERIFIED licensing "
        "(see the Comment there). That needs resolving before this can go to "
        "mentors.debian.net - Debian will reject on this alone."
    )


if __name__ == "__main__":
    main()
