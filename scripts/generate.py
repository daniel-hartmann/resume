#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "jinja2>=3.1",
#     "pyyaml>=6.0",
# ]
# ///
"""Generate resume.html, resume.md, and resume.pdf from resume.yaml + templates/resume.html.j2."""

import os
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parent.parent

# Common install locations/binary names for a Chrome-family browser, checked in order.
# CI sets RESUME_CHROME_PATH explicitly (see .github/workflows/deploy.yml) and skips this list.
BROWSER_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
    "microsoft-edge",
]


def render_html(data: dict, *, full_contact: bool) -> str:
    env = Environment(
        loader=FileSystemLoader(ROOT / "templates"),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    return env.get_template("resume.html.j2").render(**data, full_contact=full_contact)


def render_markdown(data: dict) -> str:
    # Public output: no email/phone (scraper-resistant by omission, not obfuscation).
    # Location + LinkedIn only — LinkedIn gates messaging on its own platform.
    lines: list[str] = []

    lines += [f"# {data['name']}", "", f"**{data['title']}**", "", data["summary"].strip(), ""]

    c = data["contact"]
    lines += [
        f"{c['location']} · [{c['linkedin']['label']}]({c['linkedin']['url']})",
        "",
        "## Skills",
        "",
        ", ".join(data["skills"]),
        "",
        "## Education",
        "",
    ]

    for edu in data["education"]:
        lines += [f"**{edu['degree']}**", "", f"{edu['institution']} · {edu['location']} · {edu['period']}"]
        if edu.get("description"):
            lines += ["", edu["description"].strip()]
        if edu.get("bullets"):
            lines += [""] + [f"- {b}" for b in edu["bullets"]]
        lines.append("")

    langs = ", ".join(f"{l['language']} ({l['level']})" for l in data["languages"])
    lines += [f"**Languages:** {langs}", "", "## Links", ""]
    lines += [f"- [{link['label']}]({link['url']})" for link in data["links"]]
    lines += ["", "## Interests", "", ", ".join(data["interests"]), "", "## Work Experience", ""]

    for job in data["experience"]:
        header = f"### {job['role']} · {job['company']}"
        if job.get("location"):
            header += f", {job['location']}"
        lines += [header, "", f"*{job['period']}*"]
        if job.get("description"):
            lines += ["", job["description"].strip()]
        if job.get("bullets"):
            lines += [""] + [f"- {b}" for b in job["bullets"]]
        if job.get("tags"):
            lines += [""] + [" ".join(f"`{t}`" for t in job["tags"])]
        lines.append("")

    lines += ["---", "", data["footer"], ""]
    return "\n".join(lines)


def find_browser() -> str | None:
    env_path = os.environ.get("RESUME_CHROME_PATH")
    if env_path and Path(env_path).exists():
        return env_path
    for candidate in BROWSER_CANDIDATES:
        if candidate.startswith("/"):
            if Path(candidate).exists():
                return candidate
        elif found := shutil.which(candidate):
            return found
    return None


def render_pdf(html_path: Path, pdf_path: Path) -> bool:
    browser = find_browser()
    if not browser:
        print(
            "warning: no local Chrome/Chromium/Edge found — skipping resume.pdf "
            "(set RESUME_CHROME_PATH, or rely on CI to generate it on push)",
            file=sys.stderr,
        )
        return False
    subprocess.run(
        [
            browser,
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
            f"--print-to-pdf={pdf_path}",
            "--no-pdf-header-footer",
            str(html_path),
        ],
        check=True,
        capture_output=True,
    )
    return True


def main() -> None:
    data = yaml.safe_load((ROOT / "resume.yaml").read_text())
    data["footer"] = date.today().strftime("%B %Y")

    # Public artifacts: published to GitHub Pages, crawlable by anyone/anything.
    # No email or phone in any of these — see render_markdown() and the
    # full_contact flag on render_html(). Contact is location + LinkedIn only.
    html_path = ROOT / "resume.html"
    html_path.write_text(render_html(data, full_contact=False))
    print("wrote resume.html (public — no email/phone)")

    (ROOT / "resume.md").write_text(render_markdown(data))
    print("wrote resume.md (public — no email/phone)")

    if render_pdf(html_path, ROOT / "resume.pdf"):
        print("wrote resume.pdf (public — no email/phone)")

    # Full-contact artifacts: for your own direct use (attach to an application,
    # send straight to a recruiter). Never published — not in _site/, gitignored.
    full_html_path = ROOT / "resume-full.html"
    full_html_path.write_text(render_html(data, full_contact=True))
    if render_pdf(full_html_path, ROOT / "resume-full.pdf"):
        print("wrote resume-full.pdf (private — real email/phone, not published)")


if __name__ == "__main__":
    main()
