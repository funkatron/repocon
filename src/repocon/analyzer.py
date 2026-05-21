from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import tomllib


DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "qwen2.5:7b-instruct"
MARKED_PREVIEW_STYLE = "GitHub"
MARKED_PROCESSOR = "commonmark"
INDEX_NOTE_TITLE = "Project Briefs"
LINK_STYLE_BEAR = "bear"
LINK_STYLE_MARKED = "marked"
DEFAULT_LINK_STYLE = LINK_STYLE_BEAR

NOISE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "vendor",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".cache",
    "dist",
    "build",
    "target",
    "coverage",
    ".next",
    ".vite",
    ".tox",
    ".nox",
    "htmlcov",
    "site-packages",
}
ARTIFACT_DIR_NAMES = frozenset(
    {
        "reports",
        "output",
        "out",
        "tmp",
        "temp",
    }
)
ARTIFACT_DIR_PREFIXES = ("reports-", "report-", "reports_", "dist-", "build-")
FOLDER_ROLE_HINTS: dict[str, str] = {
    "src": "application source code",
    "app": "application code",
    "lib": "library code",
    "tests": "automated tests",
    "test": "automated tests",
    "spec": "automated tests",
    "scripts": "helper scripts and tooling",
    "docs": "documentation",
    "doc": "documentation",
    "routes": "HTTP routes or API handlers",
    "api": "API layer",
    "public": "static or public web assets",
    "web": "web frontend",
    "frontend": "web frontend",
    "backend": "server-side code",
    "cmd": "CLI entry commands (Go convention)",
    "bin": "executables or CLI wrappers",
    "pkg": "library packages (Go convention)",
    "internal": "internal implementation packages",
    "components": "UI components",
    "pages": "web pages or route views",
    "assets": "static assets",
    "resources": "static or template resources",
    "migrations": "database migrations",
    "config": "configuration",
    "infra": "infrastructure or deployment config",
    "docker": "container definitions",
    "tools": "developer tooling",
    "examples": "example usage",
    "fixtures": "test fixtures or sample data",
}
RUN_SCRIPT_KEYS = ("start", "dev", "serve", "run", "build")
README_NAMES = ("README.md", "README.rst", "README.txt", "readme.md")
KEYWORD_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "this",
    "that",
    "from",
    "your",
    "into",
    "over",
    "while",
    "uses",
    "using",
    "tool",
    "project",
    "repo",
    "repository",
    "code",
    "app",
    "service",
    "application",
    "system",
}
MONETIZATION_HINTS = {
    "creator": 1.0,
    "video": 1.0,
    "image": 1.0,
    "music": 1.0,
    "browser": 0.6,
    "obs": 0.9,
    "automation": 0.7,
    "wordpress": 0.8,
    "cms": 0.7,
    "analytics": 0.7,
    "workflow": 0.6,
    "api": 0.5,
    "dashboard": 0.7,
    "scheduling": 0.7,
    "calendar": 0.7,
    "export": 0.6,
    "desktop": 0.5,
}
TOP_FILE_EXTENSIONS = {
    ".py": "Python",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".php": "PHP",
    ".rs": "Rust",
    ".go": "Go",
    ".rb": "Ruby",
    ".java": "Java",
    ".kt": "Kotlin",
    ".swift": "Swift",
    ".c": "C",
    ".cpp": "C++",
    ".h": "C/C++ headers",
    ".css": "CSS",
    ".scss": "SCSS",
    ".html": "HTML",
    ".sh": "Shell",
}


@dataclass
class GitMoment:
    date: str
    summary: str
    reason: str


@dataclass
class GitSummary:
    tracked: bool
    first_commit_date: str | None = None
    first_commit_subject: str | None = None
    latest_commit_date: str | None = None
    latest_commit_subject: str | None = None
    commit_count: int = 0
    notable_moments: list[GitMoment] = field(default_factory=list)


@dataclass
class SimilarProject:
    name: str
    similarity: float
    shared_signals: list[str]


@dataclass
class StructureSignals:
    entrypoints: list[str] = field(default_factory=list)
    route_files: list[str] = field(default_factory=list)
    route_hints: list[str] = field(default_factory=list)
    component_hints: list[str] = field(default_factory=list)
    inferred_capabilities: list[str] = field(default_factory=list)
    folder_roles: list[str] = field(default_factory=list)
    test_signals: list[str] = field(default_factory=list)
    run_hints: list[str] = field(default_factory=list)


@dataclass
class LLMConfig:
    provider: str = "none"
    model: str | None = None
    max_projects: int | None = None
    temperature: float = 0.2
    base_url: str | None = None


@dataclass
class ProjectReport:
    name: str
    path: str
    stack: list[str]
    top_level_folders: list[str]
    one_liner: str
    plain_english_summary: str
    technical_summary: str
    initial_intent: str
    git: GitSummary
    current_state: str
    health_signals: list[str]
    risks: list[str]
    recommendations: list[str]
    priority_recommendation: str
    monetization_potential: str
    similarity_tokens: list[str]
    structure: StructureSignals
    similar_projects: list[SimilarProject] = field(default_factory=list)
    llm_provider: str = "none"


def is_ignored_dir(name: str) -> bool:
    if name in NOISE_DIRS or name.startswith("."):
        return True
    if name.endswith(".egg-info"):
        return True
    if name in ARTIFACT_DIR_NAMES:
        return True
    lowered = name.lower()
    return any(lowered.startswith(prefix) for prefix in ARTIFACT_DIR_PREFIXES)


def collect_top_level_folders(project_dir: Path) -> list[str]:
    return [
        child.name
        for child in sorted(project_dir.iterdir())
        if child.is_dir() and not is_ignored_dir(child.name)
    ][:12]


def describe_folder_role(name: str) -> str:
    role = FOLDER_ROLE_HINTS.get(name.lower())
    if role:
        return f"{name} — {role}"
    return name


def build_folder_roles(folder_names: list[str]) -> list[str]:
    return [describe_folder_role(name) for name in folder_names]


def detect_test_signals(project_dir: Path, manifests: dict[str, Any]) -> list[str]:
    signals: list[str] = []

    if (project_dir / "tests").is_dir():
        signals.append("Python-style test directory at tests/")
    if (project_dir / "test").is_dir():
        signals.append("Test directory at test/")
    if (project_dir / "__tests__").is_dir():
        signals.append("JavaScript-style test directory at __tests__/")
    if (project_dir / "conftest.py").exists():
        signals.append("pytest conftest.py at repo root")
    if (project_dir / "pytest.ini").exists():
        signals.append("pytest.ini")

    pyproject = manifests.get("pyproject", {})
    if isinstance(pyproject, dict):
        tool_section = pyproject.get("tool", {})
        if isinstance(tool_section, dict) and "pytest" in tool_section:
            signals.append("pytest configured in pyproject.toml")

    package = manifests.get("package.json", {})
    if isinstance(package, dict):
        scripts = package.get("scripts", {})
        if isinstance(scripts, dict) and scripts.get("test"):
            test_command = str(scripts["test"]).strip()
            if len(test_command) > 60:
                test_command = test_command[:57] + "..."
            signals.append(f"npm test script: {test_command}")

    for config_name in (
        "jest.config.js",
        "jest.config.ts",
        "jest.config.mjs",
        "jest.config.cjs",
        "vitest.config.ts",
        "vitest.config.js",
        "vitest.config.mjs",
    ):
        if (project_dir / config_name).exists():
            signals.append(config_name)

    for config_name in ("phpunit.xml", "phpunit.xml.dist"):
        if (project_dir / config_name).exists():
            signals.append(config_name)

    if has_go_test_files(project_dir):
        signals.append("Go test files (*_test.go)")

    if "cargo" in manifests and (project_dir / "tests").is_dir():
        signals.append("Rust tests/ directory")

    makefile = project_dir / "Makefile"
    if makefile.exists():
        makefile_text = safe_read_text(makefile, 4000)
        if re.search(r"^test\s*:", makefile_text, flags=re.M):
            signals.append("Makefile test target")

    return dedupe_keep_order(signals)


def has_go_test_files(project_dir: Path) -> bool:
    for root, dirs, files in os.walk(project_dir):
        dirs[:] = [name for name in dirs if not is_ignored_dir(name)]
        try:
            depth = len(Path(root).relative_to(project_dir).parts)
        except ValueError:
            depth = 0
        if depth > 3:
            dirs.clear()
            continue
        if any(file_name.endswith("_test.go") for file_name in files):
            return True
    return False


def collect_run_hints(project_dir: Path, manifests: dict[str, Any]) -> list[str]:
    hints: list[str] = []

    package = manifests.get("package.json", {})
    if isinstance(package, dict):
        scripts = package.get("scripts", {})
        if isinstance(scripts, dict):
            for key in RUN_SCRIPT_KEYS:
                if key in scripts:
                    hints.append(f"npm run {key}")

    pyproject = manifests.get("pyproject", {})
    if isinstance(pyproject, dict):
        project_section = pyproject.get("project", {})
        if isinstance(project_section, dict):
            script_table = project_section.get("scripts", {})
            if isinstance(script_table, dict):
                for script_name in list(script_table)[:4]:
                    hints.append(f"{script_name} (pyproject script)")

    makefile = project_dir / "Makefile"
    if makefile.exists():
        makefile_text = safe_read_text(makefile, 4000)
        for target in RUN_SCRIPT_KEYS:
            if re.search(rf"^{target}\s*:", makefile_text, flags=re.M):
                hints.append(f"make {target}")

    if (project_dir / "Cargo.toml").exists():
        hints.append("cargo run")

    if (project_dir / "go.mod").exists():
        cmd_root = project_dir / "cmd"
        if cmd_root.is_dir():
            cmd_names = sorted(path.name for path in cmd_root.iterdir() if path.is_dir())
            if cmd_names:
                hints.append(f"go run ./cmd/{cmd_names[0]}")
        elif (project_dir / "main.go").exists():
            hints.append("go run .")

    return dedupe_keep_order(hints)[:6]


def build_argument_parser() -> argparse.ArgumentParser:
    formatter = argparse.RawDescriptionHelpFormatter
    parser = argparse.ArgumentParser(
        prog="repocon",
        formatter_class=formatter,
        description=(
            "Write a brief for each project folder on disk.\n\n"
            "Pass a directory that contains your repos as subfolders — repocon\n"
            "reads README, manifests, git history, and layout, then writes\n"
            "index.md, projects/*.md, and JSON under --output.\n\n"
            "LLM enrichment is off unless you pass --llm-provider."
        ),
        epilog=(
            "Examples:\n"
            "  repocon ~/src\n"
            "      One brief per repo under ~/src; output in ./reports/.\n"
            "  repocon ~/src --project now-playing --output ./reports-one\n"
            "      Brief a single project.\n"
            "  repocon ~/src --llm-provider ollama\n"
            "      Scan first, then run LLM enrichment with Ollama.\n"
            "  export OLLAMA_BASE_URL=http://127.0.0.1:11435\n"
            "  repocon ~/src --llm-provider ollama --llm-limit 3\n"
            "      Try LLM enrichment on 3 projects before running the full set.\n"
            "  ./scripts/repocon-ollama.sh --project repocon\n"
            "      Ollama on nakedsnake via SSH tunnel.\n\n"
            "After a run, repocon can open reports/index.md in Marked (mk) when available.\n"
            "Install: brew tap ttscoff/thelab && brew install ttscoff/thelab/mk\n"
            "Docs: https://markedapp.com/help/Command_Line_Utility.html\n\n"
            "Environment (LLM enrichment):\n"
            "  OLLAMA_BASE_URL, OLLAMA_HOST   Ollama server (--llm-provider ollama)\n"
            "  OLLAMA_MODEL                   Default Ollama model\n"
            "  OPENAI_API_KEY                 Required for --llm-provider openai"
        ),
    )
    parser.add_argument(
        "source",
        help="Directory containing project repos (each top-level subfolder is one project).",
    )

    scan = parser.add_argument_group("scan")
    scan.add_argument(
        "--output",
        default="reports",
        help="Write index.md, projects/*.md, and JSON here (default: %(default)s).",
    )
    scan.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Scan only the first N top-level folders.",
    )
    scan.add_argument(
        "--project",
        action="append",
        default=[],
        metavar="NAME",
        help="Scan only these folder names. Repeat for multiple projects.",
    )
    scan.add_argument(
        "--link-style",
        choices=(LINK_STYLE_BEAR, LINK_STYLE_MARKED),
        default=DEFAULT_LINK_STYLE,
        help=(
            "Inter-note link format in Markdown output (default: %(default)s). "
            "bear uses [[Note Title]] links for Bear.app (same pattern as infomux store_bear). "
            "marked uses absolute file paths for Marked preview."
        ),
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open reports/index.md when finished (no prompt).",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Do not offer to open reports/index.md when finished.",
    )

    llm = parser.add_argument_group("LLM enrichment (optional)")
    llm.add_argument(
        "--llm-provider",
        choices=("none", "openai", "ollama"),
        default="none",
        help="Run LLM enrichment after the repo scan (default: %(default)s).",
    )
    llm.add_argument(
        "--llm-model",
        default=None,
        metavar="MODEL",
        help=(
            "Model name. OpenAI default: gpt-5-mini. "
            "Ollama: OLLAMA_MODEL env, else qwen2.5:7b-instruct."
        ),
    )
    llm.add_argument(
        "--llm-limit",
        type=int,
        metavar="N",
        default=None,
        help="Enrich only the first N scanned projects (for quick tests). Default: all.",
    )
    llm.add_argument(
        "--llm-temperature",
        type=float,
        default=0.2,
        help="Enrichment sampling temperature (default: %(default)s).",
    )
    llm.add_argument(
        "--llm-base-url",
        default=None,
        metavar="URL",
        help=(
            "API base URL. Ollama falls back to OLLAMA_BASE_URL, OLLAMA_HOST, "
            "then http://127.0.0.1:11434."
        ),
    )
    return parser


def open_path(path: Path) -> None:
    if sys.platform == "darwin":
        if shutil_which("mk"):
            subprocess.run(
                ["mk", "--raise", "--style", MARKED_PREVIEW_STYLE, str(path)],
                check=False,
            )
            return
        for marked_app in (
            Path("/Applications/Marked.app"),
            Path("/Applications/Setapp/Marked.app"),
        ):
            if marked_app.exists():
                subprocess.run(["open", "-a", str(marked_app), str(path)], check=False)
                return
        subprocess.run(["open", str(path)], check=False)
        return
    if sys.platform.startswith("linux"):
        if shutil_which("xdg-open"):
            subprocess.run(["xdg-open", str(path)], check=False)
            return
        print(f"Open manually: {path}")
        return
    print(f"Open manually: {path}")


def maybe_open_index(index_path: Path, *, open_now: bool, no_open: bool) -> None:
    if no_open or not index_path.is_file():
        return
    if open_now:
        open_path(index_path)
        return
    if not sys.stdin.isatty():
        return
    try:
        answer = input(f"Open {index_path}? [Enter to open, n to skip] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return
    if answer in ("", "y", "yes"):
        open_path(index_path)


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    source_dir = Path(args.source).expanduser().resolve()
    output_dir = Path(args.output).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    llm_config = resolve_llm_config(args)

    reports = analyze_projects(source_dir, limit=args.limit, include=args.project)
    enrich_similarity(reports)
    apply_llm_enrichment(reports, llm_config)
    write_reports(reports, source_dir, output_dir, link_style=args.link_style)

    print(f"Wrote {len(reports)} project briefs to {output_dir}")
    index_path = output_dir / "index.md"
    print(f"Summary: {index_path}")
    maybe_open_index(index_path, open_now=args.open, no_open=args.no_open)


def analyze_projects(source_dir: Path, limit: int | None, include: list[str]) -> list[ProjectReport]:
    project_paths = sorted(path for path in source_dir.iterdir() if path.is_dir())
    if include:
        allowed = set(include)
        project_paths = [path for path in project_paths if path.name in allowed]
    if limit is not None:
        project_paths = project_paths[:limit]

    reports: list[ProjectReport] = []
    for path in project_paths:
        reports.append(analyze_project(path))
    return reports


def analyze_project(project_dir: Path) -> ProjectReport:
    readme_text = read_readme(project_dir)
    manifests = load_manifests(project_dir)
    stack = infer_stack(project_dir, manifests)
    top_level_folders = collect_top_level_folders(project_dir)

    code_language_counts = infer_languages(project_dir)
    structure = scan_structure(project_dir, stack)
    structure.folder_roles = build_folder_roles(top_level_folders)
    structure.test_signals = detect_test_signals(project_dir, manifests)
    structure.run_hints = collect_run_hints(project_dir, manifests)
    git = summarize_git(project_dir)
    summary_source = pick_summary_source(project_dir, readme_text, manifests, stack, top_level_folders, structure)
    similarity_tokens = build_similarity_tokens(project_dir.name, readme_text, manifests, stack)

    one_liner = build_one_liner(project_dir.name, summary_source, stack)
    plain_english = build_plain_english_summary(project_dir.name, summary_source, stack, structure.folder_roles)
    technical = build_technical_summary(
        project_dir.name, manifests, stack, code_language_counts, structure
    )
    initial_intent = build_initial_intent(project_dir.name, summary_source, git)
    current_state, health_signals, risks = evaluate_current_state(
        project_dir, readme_text, manifests, git, structure.test_signals
    )
    recommendations = build_recommendations(project_dir.name, summary_source, stack, risks, health_signals)
    priority_recommendation = build_priority_recommendation(project_dir.name, stack, summary_source, health_signals, risks)
    monetization_potential = build_monetization_assessment(project_dir.name, summary_source, health_signals)

    return ProjectReport(
        name=project_dir.name,
        path=str(project_dir),
        stack=stack,
        top_level_folders=top_level_folders,
        one_liner=one_liner,
        plain_english_summary=plain_english,
        technical_summary=technical,
        initial_intent=initial_intent,
        git=git,
        current_state=current_state,
        health_signals=health_signals,
        risks=risks,
        recommendations=recommendations,
        priority_recommendation=priority_recommendation,
        monetization_potential=monetization_potential,
        similarity_tokens=similarity_tokens,
        structure=structure,
    )


def read_readme(project_dir: Path) -> str:
    for name in README_NAMES:
        candidate = project_dir / name
        if candidate.exists():
            return candidate.read_text(encoding="utf-8", errors="ignore")
    return ""


def load_manifests(project_dir: Path) -> dict[str, Any]:
    manifests: dict[str, Any] = {}

    pyproject = project_dir / "pyproject.toml"
    if pyproject.exists():
        try:
            manifests["pyproject"] = tomllib.loads(pyproject.read_text(encoding="utf-8", errors="ignore"))
        except tomllib.TOMLDecodeError:
            manifests["pyproject"] = {}

    package_json = project_dir / "package.json"
    if package_json.exists():
        try:
            manifests["package.json"] = json.loads(package_json.read_text(encoding="utf-8", errors="ignore"))
        except json.JSONDecodeError:
            manifests["package.json"] = {}

    cargo = project_dir / "Cargo.toml"
    if cargo.exists():
        try:
            manifests["cargo"] = tomllib.loads(cargo.read_text(encoding="utf-8", errors="ignore"))
        except tomllib.TOMLDecodeError:
            manifests["cargo"] = {}

    go_mod = project_dir / "go.mod"
    if go_mod.exists():
        manifests["go.mod"] = go_mod.read_text(encoding="utf-8", errors="ignore")

    composer = project_dir / "composer.json"
    if composer.exists():
        try:
            manifests["composer.json"] = json.loads(composer.read_text(encoding="utf-8", errors="ignore"))
        except json.JSONDecodeError:
            manifests["composer.json"] = {}

    return manifests


def infer_stack(project_dir: Path, manifests: dict[str, Any]) -> list[str]:
    stack: list[str] = []
    if "pyproject" in manifests:
        stack.append("Python")
    if "package.json" in manifests:
        stack.append("Node.js")
        package = manifests["package.json"]
        deps = {
            *package.get("dependencies", {}).keys(),
            *package.get("devDependencies", {}).keys(),
        }
        if "react" in deps:
            stack.append("React")
        if "vite" in deps:
            stack.append("Vite")
        if "laravel-vite-plugin" in deps or (project_dir / "artisan").exists():
            stack.append("Laravel")
    if "cargo" in manifests:
        stack.append("Rust")
    if "go.mod" in manifests:
        stack.append("Go")
    if (project_dir / "wp-content").exists():
        stack.append("WordPress")
    if (project_dir / "composer.json").exists() and "Laravel" not in stack:
        stack.append("PHP")
    if not stack:
        inferred = next(iter(infer_languages(project_dir).keys()), None)
        if inferred:
            stack.append(inferred)
    return stack or ["Unknown stack"]


def infer_languages(project_dir: Path) -> Counter[str]:
    counts: Counter[str] = Counter()
    for root, dirs, files in os.walk(project_dir):
        dirs[:] = [name for name in dirs if not is_ignored_dir(name)]
        if Path(root).parts[-1] in NOISE_DIRS or is_ignored_dir(Path(root).name):
            continue
        for file_name in files:
            extension = Path(file_name).suffix.lower()
            language = TOP_FILE_EXTENSIONS.get(extension)
            if language:
                counts[language] += 1
    return counts


def scan_structure(project_dir: Path, stack: list[str]) -> StructureSignals:
    signals = StructureSignals()
    candidates: list[Path] = []

    explicit_candidates = [
        project_dir,
        project_dir / "src",
        project_dir / "app",
        project_dir / "routes",
        project_dir / "scripts",
        project_dir / project_dir.name.replace("-", "_"),
    ]
    for candidate in explicit_candidates:
        if candidate.exists():
            candidates.append(candidate)

    for root in candidates:
        for path in iter_source_files(root):
            rel = path.relative_to(project_dir).as_posix()
            text = safe_read_text(path, max_chars=16000)
            if not text:
                continue
            lower_text = text.lower()

            if not is_test_or_fixture_path(rel):
                if is_entrypoint_file(path, text):
                    signals.entrypoints.append(rel)

            if looks_like_route_file(path, text):
                signals.route_files.append(rel)
                signals.route_hints.extend(extract_route_hints(text))

            signals.component_hints.extend(extract_component_hints(rel, text, stack))
            signals.inferred_capabilities.extend(extract_capability_hints(rel, lower_text))

    signals.entrypoints = dedupe_keep_order(signals.entrypoints)[:6]
    signals.route_files = dedupe_keep_order(signals.route_files)[:6]
    signals.route_hints = dedupe_keep_order(signals.route_hints)[:10]
    signals.component_hints = dedupe_keep_order(signals.component_hints)[:10]
    signals.inferred_capabilities = dedupe_keep_order(signals.inferred_capabilities)[:10]
    return signals


def summarize_git(project_dir: Path) -> GitSummary:
    if not (project_dir / ".git").exists():
        return GitSummary(tracked=False)

    log_output = run_command(
        ["git", "-C", str(project_dir), "log", "--reverse", "--format=%ct%x09%s"],
        timeout=20,
    )
    if not log_output:
        return GitSummary(tracked=True)

    commits: list[tuple[int, str]] = []
    for line in log_output.splitlines():
        if "\t" not in line:
            continue
        ts_raw, subject = line.split("\t", 1)
        if ts_raw.isdigit():
            commits.append((int(ts_raw), subject.strip()))

    if not commits:
        return GitSummary(tracked=True)

    first_ts, first_subject = commits[0]
    last_ts, last_subject = commits[-1]
    moments = detect_notable_moments(commits)
    return GitSummary(
        tracked=True,
        first_commit_date=format_date(first_ts),
        first_commit_subject=first_subject,
        latest_commit_date=format_date(last_ts),
        latest_commit_subject=last_subject,
        commit_count=len(commits),
        notable_moments=moments,
    )


def detect_notable_moments(commits: list[tuple[int, str]]) -> list[GitMoment]:
    notable: list[GitMoment] = []
    keyword_pattern = re.compile(r"\b(init|initial|feat|release|rewrite|migrate|launch|ship|test|docs|refactor)\b", re.I)

    if commits:
        ts, subject = commits[0]
        notable.append(GitMoment(date=format_date(ts), summary=subject, reason="starting point"))

    gaps: list[tuple[int, int, str]] = []
    for (previous_ts, _), (current_ts, subject) in zip(commits, commits[1:]):
        gaps.append((current_ts - previous_ts, current_ts, subject))
    if gaps:
        largest_gap = max(gaps, key=lambda item: item[0])
        if largest_gap[0] >= 60 * 60 * 24 * 45:
            notable.append(
                GitMoment(
                    date=format_date(largest_gap[1]),
                    summary=largest_gap[2],
                    reason=f"work resumed after a long gap of about {largest_gap[0] // (60 * 60 * 24)} days",
                )
            )

    weighted_subjects: list[tuple[int, int, str]] = []
    midpoint = len(commits) / 2
    for index, (ts, subject) in enumerate(commits):
        if keyword_pattern.search(subject):
            weight = 2
            if index > midpoint:
                weight += 1
            weighted_subjects.append((weight, ts, subject))
    for _, ts, subject in sorted(weighted_subjects, reverse=True)[:3]:
        if any(moment.summary == subject for moment in notable):
            continue
        notable.append(GitMoment(date=format_date(ts), summary=subject, reason="subject looks like a significant change"))

    last_ts, last_subject = commits[-1]
    if not any(moment.summary == last_subject for moment in notable):
        notable.append(GitMoment(date=format_date(last_ts), summary=last_subject, reason="latest visible change"))

    return notable[:5]


def pick_summary_source(
    project_dir: Path,
    readme_text: str,
    manifests: dict[str, Any],
    stack: list[str],
    top_level_folders: list[str],
    structure: StructureSignals,
) -> str:
    project_name = project_dir.name
    pyproject = manifests.get("pyproject", {})
    project_section = pyproject.get("project", {})
    if isinstance(project_section, dict):
        description = project_section.get("description")
        if description and not is_generic_summary(str(description), project_name):
            return clean_summary_text(str(description))

    package = manifests.get("package.json", {})
    if isinstance(package, dict) and package.get("description") and not is_generic_summary(str(package["description"]), project_name):
        return clean_summary_text(str(package["description"]))

    composer = manifests.get("composer.json", {})
    if isinstance(composer, dict) and composer.get("description") and not is_generic_summary(str(composer["description"]), project_name):
        return clean_summary_text(str(composer["description"]))

    for paragraph in extract_readme_paragraphs(readme_text):
        if is_good_intro_paragraph(paragraph):
            return clean_summary_text(paragraph)

    return derive_summary_from_signals(project_dir, manifests, stack, top_level_folders, readme_text, structure)


def build_one_liner(project_name: str, summary_source: str, stack: list[str]) -> str:
    cleaned = summary_source.rstrip(".") or "Purpose is not clearly stated in the repo's opening docs"
    stack_text = ", ".join(stack[:3])
    return f"{project_name}: {cleaned}. Main stack: {stack_text}."


def build_plain_english_summary(
    project_name: str,
    summary_source: str,
    stack: list[str],
    folder_roles: list[str],
) -> str:
    summary = clean_summary_text(summary_source) or "The repo does not clearly state its purpose in the opening docs"
    folder_text = ", ".join(folder_roles[:5]) if folder_roles else "a small top-level layout"
    return (
        f"Based on the repo's visible docs, {project_name} is meant to do this: {summary}. "
        f"It looks like a {', '.join(stack[:2])} project, and its visible structure starts with {folder_text}. "
        f"Someone new to the repo should think of it first as a product or tool with a clear job, then as code."
    )


def build_technical_summary(
    project_name: str,
    manifests: dict[str, Any],
    stack: list[str],
    language_counts: Counter[str],
    structure: StructureSignals,
) -> str:
    technical_bits = [f"Primary stack signals: {', '.join(stack)}."]
    if language_counts:
        dominant = ", ".join(f"{name} ({count} files)" for name, count in language_counts.most_common(3))
        technical_bits.append(f"Dominant file types: {dominant}.")

    package = manifests.get("package.json", {})
    scripts = package.get("scripts", {}) if isinstance(package, dict) else {}
    if scripts:
        technical_bits.append(f"Package scripts suggest runnable entrypoints such as: {', '.join(list(scripts)[:4])}.")

    pyproject = manifests.get("pyproject", {})
    if isinstance(pyproject, dict):
        project_section = pyproject.get("project", {})
        if isinstance(project_section, dict):
            script_table = project_section.get("scripts", {})
            if isinstance(script_table, dict) and script_table:
                technical_bits.append(
                    f"Python packaging exposes CLI entrypoints including: {', '.join(list(script_table)[:4])}."
                )

    if structure.folder_roles:
        technical_bits.append(f"Top-level folders: {'; '.join(structure.folder_roles[:6])}.")
    if structure.run_hints:
        technical_bits.append(f"Likely run commands: {', '.join(structure.run_hints[:4])}.")
    if structure.test_signals:
        technical_bits.append(f"Test signals: {', '.join(structure.test_signals[:4])}.")
    if structure.entrypoints:
        technical_bits.append(f"Likely entrypoints: {', '.join(structure.entrypoints[:4])}.")
    if structure.route_files:
        technical_bits.append(f"Likely web/API route files: {', '.join(structure.route_files[:4])}.")
    if structure.component_hints:
        technical_bits.append(f"Named implementation areas seen in code: {', '.join(structure.component_hints[:5])}.")

    return " ".join(technical_bits)


def build_initial_intent(
    project_name: str,
    summary_source: str,
    git: GitSummary,
) -> str:
    commit_note = ""
    if git.first_commit_date and git.first_commit_subject:
        commit_note = f" The first visible git point is {git.first_commit_date} with '{git.first_commit_subject}'."
    summary = clean_summary_text(summary_source) or "The repo does not make its initial product intent very explicit"
    return (
        f"The initial intent was probably the same as the opening project description: {summary}. "
        f"That intent is inferred mainly from the README and manifest metadata, not from private planning notes."
        f"{commit_note}"
    )


def evaluate_current_state(
    project_dir: Path,
    readme_text: str,
    manifests: dict[str, Any],
    git: GitSummary,
    test_signals: list[str],
) -> tuple[str, list[str], list[str]]:
    signals: list[str] = []
    risks: list[str] = []
    score = 0.0

    if readme_text:
        signals.append("Has a README, which lowers onboarding friction.")
        score += 1.0
    else:
        risks.append("No obvious README, so a new reader may have to infer purpose from code alone.")

    if git.tracked and git.commit_count:
        signals.append(f"Tracked in git with {git.commit_count} commits.")
        score += 0.8
        if git.latest_commit_date:
            age_days = days_since(git.latest_commit_date)
            if age_days is not None and age_days < 120:
                signals.append("Recent commit activity suggests the project is not abandoned.")
                score += 0.8
            elif age_days is not None and age_days > 365:
                risks.append("Last visible commit is more than a year old.")
                score -= 0.6
    else:
        risks.append("No usable git history was detected.")

    if test_signals:
        signals.append(f"Test tooling detected: {', '.join(test_signals[:3])}.")
        score += 0.8
    else:
        risks.append("No test signals detected from manifests or layout.")

    if (project_dir / ".github" / "workflows").exists():
        signals.append("Has CI workflow definitions.")
        score += 0.4

    if "pyproject" in manifests or "package.json" in manifests or "cargo" in manifests:
        signals.append("Has package metadata or a build manifest.")
        score += 0.4
    else:
        risks.append("No standard build manifest was found.")

    todo_count = count_repo_markers(project_dir, r"\b(TODO|FIXME|HACK|XXX)\b")
    if todo_count:
        risks.append(f"Contains {todo_count} TODO/FIXME-style markers, which may indicate unfinished work.")
        score -= min(todo_count / 15.0, 0.8)

    archived = "archive" in project_dir.name.lower() or "deprecated" in readme_text.lower()
    if archived:
        risks.append("Archive/deprecated language suggests this may not be a live investment target.")
        score -= 1.0

    if score >= 2.6:
        state = "Healthy enough to understand quickly and potentially invest in further."
    elif score >= 1.4:
        state = "Understandable and somewhat maintained, but there are still trust gaps."
    else:
        state = "Exploratory or stale; treat it as a repo that needs validation before you depend on it."

    return state, signals, risks


def build_recommendations(
    project_name: str,
    summary_source: str,
    stack: list[str],
    risks: list[str],
    health_signals: list[str],
) -> list[str]:
    text = " ".join([project_name, summary_source])
    lowered = text.lower()
    recs: list[str] = []

    if not summary_source:
        recs.append("Write a real project overview near the top of the README that explains the product, user, and outcome in plain language.")
    if "No obvious README" in " ".join(risks):
        recs.append("Write a short README that starts with who this is for, what problem it solves, and how to run it.")
    if "No test signals detected from manifests or layout." in risks:
        recs.append("Add one happy-path smoke test so the repo can prove its core promise still works.")
    if "Recent commit activity suggests the project is not abandoned." in health_signals and any(
        token in lowered for token in ("server", "api", "desktop", "client", "obs", "export", "video", "music")
    ):
        recs.append("Package the easiest user-facing workflow so someone can install it without reading the whole codebase.")
    if any(token in lowered for token in ("video", "music", "image", "obs", "creator", "ffmpeg")):
        recs.append("Lean into demos and example outputs, because media tools sell better when the result is visible immediately.")
    if any(token in lowered for token in ("wordpress", "cms", "laravel", "backoffice", "admin panel")):
        recs.append("Treat this as serviceable consulting infrastructure: reliability, deployment notes, and repeatable setup may matter more than fancy architecture.")
    if "Python" in stack and "Node.js" not in stack:
        recs.append("If you keep investing here, expose a crisp CLI command or minimal web view so the repo is easier to evaluate quickly.")
    if not recs:
        recs.append("Clarify the main promise of the project before making deeper technical changes.")
    return dedupe_keep_order(recs)[:4]


def build_priority_recommendation(
    project_name: str,
    stack: list[str],
    summary_source: str,
    health_signals: list[str],
    risks: list[str],
) -> str:
    text = f"{project_name} {summary_source}".lower()
    user_facing = any(token in text for token in ("video", "music", "image", "viewer", "browser", "desktop", "obs"))
    active = any("Recent commit activity" in signal for signal in health_signals)
    onboarding_gap = any("README" in risk or "test signals" in risk.lower() for risk in risks)

    if user_facing and active:
        return (
            "Priority suggestion: keep this near the top if it already helps you directly. "
            "The next high-leverage move is reducing setup friction, then testing whether another person can use it."
        )
    if user_facing and onboarding_gap:
        return (
            "Priority suggestion: before adding features, make the project legible and runnable in one sitting. "
            "That is the cheapest way to recover value from it."
        )
    if "Laravel" in stack or "WordPress" in stack:
        return (
            "Priority suggestion: optimize for reliability and repeatability first. "
            "For client-like projects, operational trust usually beats new features."
        )
    return (
        "Priority suggestion: clarify whether this repo is a live product, an internal tool, or an archive. "
        "That decision should drive whether you harden it, sell it, or simply document it."
    )


def build_monetization_assessment(
    project_name: str,
    summary_source: str,
    health_signals: list[str],
) -> str:
    text = " ".join([project_name, summary_source]).lower()
    score = 0.0
    for token, weight in MONETIZATION_HINTS.items():
        if token in text:
            score += weight
    if any("Recent commit activity" in signal for signal in health_signals):
        score += 0.5
    if any(token in text for token in ("local", "desktop", "cli", "workflow", "automation")):
        score += 0.4

    if score >= 3.0:
        return (
            "Monetization read: promising. It looks close to a user-facing utility or creator tool, "
            "which could support paid downloads, niche subscriptions, or consulting around setup."
        )
    if score >= 1.8:
        return (
            "Monetization read: moderate. The repo may be more valuable as consulting leverage, a bundled service, "
            "or a feature inside a larger product than as a standalone sale."
        )
    return (
        "Monetization read: low or unclear from repo signals alone. It may still be valuable internally, "
        "but the path to revenue is not obvious yet."
    )


def build_similarity_tokens(
    project_name: str,
    readme_text: str,
    manifests: dict[str, Any],
    stack: list[str],
) -> list[str]:
    text = " ".join([project_name, readme_text[:6000], json.dumps(manifests, default=str), " ".join(stack)])
    tokens = []
    for token in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", text.lower()):
        if token not in KEYWORD_STOPWORDS and not token.isdigit():
            tokens.append(token)
    counts = Counter(tokens)
    return [token for token, _ in counts.most_common(40)]


def enrich_similarity(reports: list[ProjectReport]) -> None:
    for report in reports:
        scored: list[SimilarProject] = []
        left_tokens = set(report.similarity_tokens)
        for other in reports:
            if other.name == report.name:
                continue
            right_tokens = set(other.similarity_tokens)
            if not left_tokens or not right_tokens:
                continue
            shared = sorted(left_tokens & right_tokens)
            similarity = len(shared) / len(left_tokens | right_tokens)
            if similarity < 0.1:
                continue
            scored.append(
                SimilarProject(
                    name=other.name,
                    similarity=similarity,
                    shared_signals=shared[:6],
                )
            )
        report.similar_projects = sorted(scored, key=lambda item: item.similarity, reverse=True)[:3]


def apply_llm_enrichment(reports: list[ProjectReport], config: LLMConfig) -> None:
    if config.provider == "none":
        return

    selected = reports[: config.max_projects] if config.max_projects is not None else reports
    for report in selected:
        response = enrich_report_with_llm(report, config)
        if not response:
            continue
        report.one_liner = response.get("one_liner", report.one_liner).strip() or report.one_liner
        report.plain_english_summary = response.get("plain_english_summary", report.plain_english_summary).strip() or report.plain_english_summary
        report.technical_summary = response.get("technical_summary", report.technical_summary).strip() or report.technical_summary
        report.initial_intent = response.get("initial_intent", report.initial_intent).strip() or report.initial_intent
        report.current_state = response.get("current_state", report.current_state).strip() or report.current_state
        recommendations = response.get("recommendations")
        if isinstance(recommendations, list):
            cleaned = [str(item).strip() for item in recommendations if str(item).strip()]
            if cleaned:
                report.recommendations = cleaned[:4]
        priority = response.get("priority_recommendation")
        if isinstance(priority, str) and priority.strip():
            report.priority_recommendation = priority.strip()
        money = response.get("monetization_potential")
        if isinstance(money, str) and money.strip():
            report.monetization_potential = money.strip()
        report.llm_provider = config.provider


def format_wiki_link(title: str) -> str:
    """Bear-style inter-note link; title must match the target note's heading."""
    return f"[[{title}]]"


def format_project_link(report_name: str, brief_path: Path, link_style: str) -> str:
    if link_style == LINK_STYLE_MARKED:
        return f"- [{report_name}]({brief_path})"
    return f"- {format_wiki_link(report_name)}"


def format_similar_project_links(items: list[SimilarProject], link_style: str) -> str:
    if not items:
        return "None yet"
    if link_style == LINK_STYLE_MARKED:
        return ", ".join(item.name for item in items)
    return ", ".join(format_wiki_link(item.name) for item in items)


def write_reports(
    reports: list[ProjectReport],
    source_dir: Path,
    output_dir: Path,
    *,
    link_style: str = DEFAULT_LINK_STYLE,
) -> None:
    reports_dir = output_dir / "projects"
    facts_dir = output_dir / "facts"
    reports_dir.mkdir(parents=True, exist_ok=True)
    facts_dir.mkdir(parents=True, exist_ok=True)

    index_path = (output_dir / "index.md").resolve()

    for report in reports:
        slug = slugify(report.name)
        (reports_dir / f"{slug}.md").write_text(
            render_project_markdown(report, link_style=link_style, index_path=index_path),
            encoding="utf-8",
        )
        (facts_dir / f"{slug}.json").write_text(
            json.dumps(build_project_facts(report), indent=2),
            encoding="utf-8",
        )

    index_md = render_index_markdown(reports, source_dir, output_dir, link_style=link_style)
    (output_dir / "index.md").write_text(index_md, encoding="utf-8")
    (output_dir / "projects.json").write_text(
        json.dumps([asdict(report) for report in reports], indent=2),
        encoding="utf-8",
    )
    (output_dir / "facts.json").write_text(
        json.dumps([build_project_facts(report) for report in reports], indent=2),
        encoding="utf-8",
    )


def render_index_markdown(
    reports: list[ProjectReport],
    source_dir: Path,
    output_dir: Path,
    *,
    link_style: str = DEFAULT_LINK_STYLE,
) -> str:
    lines = [
        f"Marked Style: {MARKED_PREVIEW_STYLE}",
        f"Processor: {MARKED_PROCESSOR}",
        "",
        "# Project Briefs",
        "",
        f"Scanned source directory: `{source_dir}`",
        "",
        "Each project gets its own layered brief under `projects/`.",
        "",
        "## Projects",
        "",
    ]
    for report in reports:
        slug = slugify(report.name)
        brief_path = (output_dir / "projects" / f"{slug}.md").resolve()
        lines.append(format_project_link(report.name, brief_path, link_style))
    link_help = (
        "Links use absolute paths so preview apps like Marked can find the files."
        if link_style == LINK_STYLE_MARKED
        else (
            "Links use Bear-style `[[Note Title]]` wiki links (same pattern as infomux `store_bear`). "
            "Titles match each brief's `#` heading so Bear can jump between notes."
        )
    )
    lines.extend(
        [
            "",
            "## Summary Table",
            "",
            f"Open briefs from the list above. {link_help}",
            "",
            "| Project | One-line read | Current state | Similar projects |",
            "|---|---|---|---|",
        ]
    )
    for report in reports:
        similar = format_similar_project_links(report.similar_projects, link_style)
        lines.append(
            f"| {escape_pipes(report.name)} | {escape_pipes(report.one_liner)} | "
            f"{escape_pipes(report.current_state)} | {escape_pipes(similar)} |"
        )
    return "\n".join(lines) + "\n"


def render_project_markdown(
    report: ProjectReport,
    *,
    link_style: str = DEFAULT_LINK_STYLE,
    index_path: Path | None = None,
) -> str:
    lines = [
        f"# {report.name}",
        "",
    ]
    if link_style == LINK_STYLE_BEAR:
        lines.extend([f"← {format_wiki_link(INDEX_NOTE_TITLE)}", ""])
    elif index_path is not None:
        lines.extend([f"← [Project Briefs]({index_path})", ""])

    lines.extend(
        [
            f"Path: `{report.path}`",
            "",
            "## Start Here",
            "",
            report.one_liner,
            "",
            "## Plain-English Summary",
            "",
            report.plain_english_summary,
            "",
            "## Technical Summary",
            "",
            report.technical_summary,
            "",
            "## Metadata",
            "",
            f"- Stack: {', '.join(report.stack)}",
            f"- Top-level folders: {'; '.join(report.structure.folder_roles) if report.structure.folder_roles else 'None detected'}",
            f"- Likely run commands: {', '.join(report.structure.run_hints) if report.structure.run_hints else 'None detected'}",
            f"- Test signals: {', '.join(report.structure.test_signals) if report.structure.test_signals else 'None detected'}",
            f"- Summary provider: {f'repo scan + LLM enrichment ({report.llm_provider})' if report.llm_provider != 'none' else 'repo files only'}",
            f"- Initial intent: {report.initial_intent}",
            f"- Current state: {report.current_state}",
            "",
            "## Chronology",
            "",
        ]
    )

    if report.git.tracked:
        lines.extend(
            [
                f"- First commit: {report.git.first_commit_date or 'Unknown'}"
                + (f" - {report.git.first_commit_subject}" if report.git.first_commit_subject else ""),
                f"- Latest commit: {report.git.latest_commit_date or 'Unknown'}"
                + (f" - {report.git.latest_commit_subject}" if report.git.latest_commit_subject else ""),
                f"- Commit count: {report.git.commit_count}",
                "",
                "### Notable Moments",
                "",
            ]
        )
        for moment in report.git.notable_moments:
            lines.append(f"- {moment.date}: {moment.summary} ({moment.reason})")
    else:
        lines.append("- No git history was detected.")

    lines.extend(
        [
            "",
            "## Current State Evaluation",
            "",
            "### Positive Signals",
            "",
        ]
    )
    for signal in report.health_signals or ["No strong positive signals detected."]:
        lines.append(f"- {signal}")

    lines.extend(["", "### Risks Or Gaps", ""])
    for risk in report.risks or ["No major gaps surfaced from the first-pass scan."]:
        lines.append(f"- {risk}")

    lines.extend(["", "## Recommendations", ""])
    for recommendation in report.recommendations:
        lines.append(f"- {recommendation}")
    lines.append(f"- {report.priority_recommendation}")
    lines.append(f"- {report.monetization_potential}")

    lines.extend(["", "## Similar Projects", ""])
    if report.similar_projects:
        for item in report.similar_projects:
            name_link = (
                item.name
                if link_style == LINK_STYLE_MARKED
                else format_wiki_link(item.name)
            )
            lines.append(
                f"- {name_link} ({item.similarity:.0%} similarity by local signals; "
                f"shared: {', '.join(item.shared_signals)})"
            )
    else:
        lines.append("- No strong sibling project matches yet.")

    return "\n".join(lines) + "\n"


def count_repo_markers(project_dir: Path, pattern: str) -> int:
    rg_path = shutil_which("rg")
    if rg_path:
        output = run_command(
            [rg_path, "-n", "--hidden", "--glob", "!.git", pattern, str(project_dir)],
            timeout=20,
        )
        return len(output.splitlines()) if output else 0

    count = 0
    compiled = re.compile(pattern)
    for root, dirs, files in os.walk(project_dir):
        dirs[:] = [name for name in dirs if not is_ignored_dir(name)]
        for file_name in files[:1000]:
            candidate = Path(root) / file_name
            try:
                text = candidate.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            count += len(compiled.findall(text))
            if count > 200:
                return count
    return count


def run_command(args: list[str], timeout: int) -> str:
    try:
        completed = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()


def strip_markdown(text: str) -> str:
    text = re.sub(r"`{1,3}.*?`{1,3}", " ", text, flags=re.S)
    text = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", text)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"^[#>\-\*\d\.\|\s]+", "", text, flags=re.M)
    return text


def looks_like_command(text: str) -> bool:
    return bool(re.search(r"(uv run|npm |yarn |pnpm |docker |git clone|http://|https://|127\.0\.0\.1)", text))


def dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            result.append(item)
            seen.add(item)
    return result


def days_since(date_string: str) -> int | None:
    try:
        then = datetime.strptime(date_string, "%Y-%m-%d").replace(tzinfo=UTC)
    except ValueError:
        return None
    now = datetime.now(UTC)
    return (now - then).days


def format_date(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, tz=UTC).strftime("%Y-%m-%d")


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip().lower()).strip("-")
    return slug or "project"


def escape_pipes(text: str) -> str:
    return text.replace("|", "\\|")


def shutil_which(command: str) -> str | None:
    path = os.environ.get("PATH", "")
    for directory in path.split(os.pathsep):
        candidate = Path(directory) / command
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def extract_readme_paragraphs(readme_text: str) -> list[str]:
    stripped = strip_markdown(readme_text)
    paragraphs = [re.sub(r"\s+", " ", part).strip() for part in re.split(r"\n\s*\n", stripped)]
    return [paragraph for paragraph in paragraphs if paragraph]


def is_good_intro_paragraph(paragraph: str) -> bool:
    lowered = paragraph.lower()
    bad_markers = (
        "prerequisites",
        "getting started",
        "quick start",
        "install ",
        "installation",
        "clone the repository",
        "ensure you have",
        "run the following",
        "requirements",
        "useful commands",
        "troubleshooting",
    )
    if any(marker in lowered for marker in bad_markers):
        return False
    if looks_like_command(paragraph):
        return False
    words = paragraph.split()
    return 8 <= len(words) <= 80


def clean_summary_text(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", strip_markdown(text)).strip()
    return cleaned.rstrip(".")


def derive_summary_from_signals(
    project_dir: Path,
    manifests: dict[str, Any],
    stack: list[str],
    top_level_folders: list[str],
    readme_text: str,
    structure: StructureSignals,
) -> str:
    kind = infer_project_kind(project_dir, manifests, stack, top_level_folders)
    domain = infer_domain_phrase(project_dir.name, manifests, readme_text, top_level_folders, structure)
    audience = infer_audience_phrase(project_dir.name, manifests, readme_text)
    traits = infer_trait_phrases(project_dir, manifests, readme_text, top_level_folders, structure)

    pieces = [kind]
    if domain:
        pieces.append(f"focused on {domain}")
    if audience:
        pieces.append(f"for {audience}")

    summary = " ".join(pieces).strip()
    if traits:
        summary = f"{summary}; it includes {', '.join(traits[:3])}"

    return summary[:1].upper() + summary[1:] if summary else ""


def infer_project_kind(
    project_dir: Path,
    manifests: dict[str, Any],
    stack: list[str],
    top_level_folders: list[str],
) -> str:
    package = manifests.get("package.json", {}) if isinstance(manifests.get("package.json", {}), dict) else {}
    package_scripts = set(package.get("scripts", {}).keys())

    pyproject = manifests.get("pyproject", {}) if isinstance(manifests.get("pyproject", {}), dict) else {}
    pyproject_scripts = pyproject.get("project", {}).get("scripts", {}) if isinstance(pyproject.get("project", {}), dict) else {}

    if "WordPress" in stack:
        return "A WordPress codebase"
    if "Laravel" in stack and "React" in stack:
        return "A Laravel web application with a React frontend"
    if "Laravel" in stack:
        return "A Laravel web application"
    if "React" in stack and "Vite" in stack:
        return "A web application with a React frontend"
    if "Node.js" in stack and {"dev", "build"} & package_scripts:
        return "A Node-based application"
    if "Python" in stack and isinstance(pyproject_scripts, dict) and pyproject_scripts:
        if any(name for name in pyproject_scripts if any(token in name for token in ("serve", "server", "desktop", "client"))):
            return "A Python application with runnable entrypoints"
        return "A Python CLI or utility project"
    if "Rust" in stack:
        return "A Rust project"
    if "PHP" in stack:
        return "A PHP application"
    if "Shell" in stack:
        return "A shell-based utility repo"
    if any(folder.endswith(".app") for folder in top_level_folders):
        return "A small desktop utility"
    if stack and stack != ["Unknown stack"]:
        return f"A {', '.join(stack[:2])} project"
    return "A small utility repo"


def infer_domain_phrase(
    project_name: str,
    manifests: dict[str, Any],
    readme_text: str,
    top_level_folders: list[str],
    structure: StructureSignals,
) -> str:
    text = " ".join(
        [
            project_name,
            readme_text[:5000],
            json.dumps(manifests, default=str)[:4000],
            " ".join(top_level_folders),
            " ".join(structure.route_hints),
            " ".join(structure.inferred_capabilities),
            " ".join(structure.component_hints),
        ]
    ).lower()

    name_patterns = [
        (("apple", "card", "simplifi"), "converting Apple Card exports into Simplifi-friendly data"),
        (("open", "iterm"), "opening iTerm in the current Finder location"),
        (("ssh", "setup"), "SSH setup and connection workflow"),
    ]
    name_text = project_name.lower().replace("_", " ").replace("-", " ")
    for needles, phrase in name_patterns:
        if all(needle in name_text for needle in needles):
            return phrase

    domain_patterns = [
        (("music", "video", "bpm"), "music-aligned video performance"),
        (("apple music", "spotify", "obs"), "now-playing status and streaming overlays"),
        (("calendar", "ical", ".ics", "schedule"), "calendar and scheduling data"),
        (("prompt", "image", "generated images"), "AI image organization"),
        (("ascii", "terminal", "video"), "terminal-friendly video rendering"),
        (("aviation", "pegasas", "airport", "flight"), "general aviation operations"),
        (("screenshot", "activity logging", "screen"), "on-device activity capture"),
        (("draw things", "grpc", "render"), "image generation workflows"),
        (("api docs", "backoffice", "placement", "deal"), "internal business workflows and APIs"),
        (("wordpress", "cms", "content"), "website content management"),
    ]
    for needles, phrase in domain_patterns:
        if all(needle in text for needle in needles):
            return phrase
    for needles, phrase in domain_patterns:
        if sum(needle in text for needle in needles) >= max(1, len(needles) - 1):
            return phrase
    return ""


def infer_audience_phrase(project_name: str, manifests: dict[str, Any], readme_text: str) -> str:
    text = " ".join([project_name, readme_text[:4000], json.dumps(manifests, default=str)[:3000]]).lower()
    if any(token in text for token in ("obs", "ffmpeg", "music", "video", "creator")):
        return "media or creator workflows"
    if any(token in text for token in ("admin", "backoffice", "dashboard", "internal")):
        return "internal operators or admins"
    if any(token in text for token in ("cli", "terminal", "developer", "dev")):
        return "developers"
    return ""


def infer_trait_phrases(
    project_dir: Path,
    manifests: dict[str, Any],
    readme_text: str,
    top_level_folders: list[str],
    structure: StructureSignals,
) -> list[str]:
    text = " ".join([readme_text[:4000], json.dumps(manifests, default=str), " ".join(top_level_folders)]).lower()
    traits: list[str] = []
    if "tests" in top_level_folders or "test" in top_level_folders:
        traits.append("tests")
    if "docs" in top_level_folders:
        traits.append("project docs")
    if "routes" in top_level_folders or "api" in text:
        traits.append("API or route definitions")
    if "scripts" in top_level_folders:
        traits.append("automation scripts")
    if "public" in top_level_folders or "resources" in top_level_folders or "web" in top_level_folders:
        traits.append("frontend or public-facing assets")
    if any(token in text for token in ("storybook", "ui")):
        traits.append("UI development tooling")
    if structure.entrypoints:
        traits.append("runnable entrypoints")
    if structure.route_files:
        traits.append("web or API routes")
    if structure.inferred_capabilities:
        traits.append(f"code paths for {', '.join(structure.inferred_capabilities[:2])}")
    return traits


def is_test_or_fixture_path(rel_path: str) -> bool:
    lowered = rel_path.lower()
    if lowered.startswith(("tests/", "test/", "__tests__/")):
        return True
    return "/fixtures/" in lowered


def iter_source_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for current_root, dirs, names in os.walk(root):
        dirs[:] = [name for name in dirs if not is_ignored_dir(name)]
        for name in names:
            path = Path(current_root) / name
            if path.suffix.lower() in {".py", ".php", ".js", ".ts", ".tsx", ".jsx", ".sh"}:
                files.append(path)
            if len(files) >= 120:
                return files
    return files


def safe_read_text(path: Path, max_chars: int) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:max_chars]
    except OSError:
        return ""


def is_entrypoint_file(path: Path, text: str) -> bool:
    rel = path.as_posix().lower()
    if path.name in {"__main__.py", "main.py", "main.ts", "main.js", "server.py", "server.js"}:
        return True
    entrypoint_markers = [
        "if __name__ == \"__main__\":",
        "if __name__ == '__main__':",
        "def main(",
        "argparse.ArgumentParser",
        "click.command(",
        "typer.Typer(",
        "uvicorn.run(",
        "express(",
        "ReactDOM.createRoot",
        "createRoot(",
    ]
    return any(marker in text for marker in entrypoint_markers) or "/scripts/" in rel


def looks_like_route_file(path: Path, text: str) -> bool:
    route_markers = [
        "@router.",
        "@app.",
        "Route::",
        "router.get(",
        "router.post(",
        "app.get(",
        "app.post(",
        "Blueprint(",
    ]
    rel = path.as_posix()
    if "/routes/" in rel or path.name.startswith("route"):
        return True
    if "/providers/" in rel.lower():
        return False
    marker_hits = sum(marker in text for marker in route_markers)
    return marker_hits >= 2


def extract_route_hints(text: str) -> list[str]:
    hints = re.findall(r'["\']/(api/[^"\']+|[^"\']+)["\']', text)
    cleaned: list[str] = []
    for hint in hints[:20]:
        hint = hint.strip("/")
        if not hint:
            continue
        first = hint.split("/")[0]
        if len(first) > 2 and not first.startswith("{"):
            cleaned.append(first.replace("-", " "))
    return cleaned


def extract_component_hints(rel_path: str, text: str, stack: list[str]) -> list[str]:
    hints: list[str] = []
    if "React" in stack:
        for match in re.findall(r"function\s+([A-Z][A-Za-z0-9]+)|const\s+([A-Z][A-Za-z0-9]+)\s*=", text):
            name = next(part for part in match if part)
            if name not in {"App", "Page"}:
                hints.append(name)
    for match in re.findall(r"class\s+([A-Z][A-Za-z0-9_]+Controller)\b", text):
        hints.append(match)
    for match in re.findall(r"class\s+([A-Z][A-Za-z0-9_]+Service)\b", text):
        hints.append(match)
    if rel_path.endswith("__main__.py"):
        hints.append("__main__ entrypoint")
    return hints


def extract_capability_hints(rel_path: str, lower_text: str) -> list[str]:
    capability_markers = [
        ("export", "export"),
        ("preview", "preview"),
        ("health", "health checks"),
        ("login", "authentication"),
        ("auth", "authentication"),
        ("report", "reporting"),
        ("campaign", "campaign management"),
        ("deal", "deal management"),
        ("creative", "creative management"),
        ("spotify", "Spotify integration"),
        ("apple music", "Apple Music integration"),
        ("artwork", "artwork handling"),
        ("upload", "uploads"),
        ("billing", "billing"),
        ("webhook", "webhooks"),
        ("api key", "API key management"),
    ]
    found: list[str] = []
    haystack = f"{rel_path.lower()} {lower_text}"
    for needle, label in capability_markers:
        if needle in haystack:
            found.append(label)
    return found


def is_generic_summary(text: str, project_name: str) -> bool:
    cleaned = clean_summary_text(text).lower()
    generic_phrases = {
        "",
        f"{project_name.lower()} is a software project in this source tree",
        "the skeleton application for the laravel framework",
        "software project",
        "add your description here",
    }
    return cleaned in generic_phrases


def build_project_facts(report: ProjectReport) -> dict[str, Any]:
    return {
        "name": report.name,
        "path": report.path,
        "stack": report.stack,
        "top_level_folders": report.top_level_folders,
        "git": asdict(report.git),
        "structure": asdict(report.structure),
        "current_state": report.current_state,
        "health_signals": report.health_signals,
        "risks": report.risks,
        "similar_projects": [asdict(item) for item in report.similar_projects],
        "deterministic_summary": {
            "one_liner": report.one_liner,
            "plain_english_summary": report.plain_english_summary,
            "technical_summary": report.technical_summary,
            "initial_intent": report.initial_intent,
            "recommendations": report.recommendations,
            "priority_recommendation": report.priority_recommendation,
            "monetization_potential": report.monetization_potential,
        },
        "llm_provider": report.llm_provider,
    }


def enrich_report_with_llm(report: ProjectReport, config: LLMConfig) -> dict[str, Any] | None:
    prompt = build_llm_prompt(report)
    raw_text = call_llm(config, prompt)
    if not raw_text:
        return None
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw_text, flags=re.S)
        if not match:
            return None
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return payload if isinstance(payload, dict) else None


def build_llm_prompt(report: ProjectReport) -> str:
    facts = build_project_facts(report)
    return (
        "You are enriching a deterministic project brief.\n"
        "Use only the structured facts below. Do not invent facts or capabilities.\n"
        "Write concise, explicit prose for a newcomer. Return JSON only with these keys:\n"
        'one_liner, plain_english_summary, technical_summary, initial_intent, current_state, recommendations, priority_recommendation, monetization_potential.\n'
        "Rules:\n"
        "- Keep each string grounded in the facts.\n"
        "- recommendations must be a JSON array of up to 4 strings.\n"
        "- If the deterministic output is already strong, you may stay close to it.\n"
        "- Do not mention unavailable information.\n\n"
        f"FACTS:\n{json.dumps(facts, indent=2)}"
    )


def call_llm(config: LLMConfig, prompt: str) -> str | None:
    if config.provider == "openai":
        return call_openai(config, prompt)
    if config.provider == "ollama":
        return call_ollama(config, prompt)
    return None


def call_openai(config: LLMConfig, prompt: str) -> str | None:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    model = config.model or "gpt-5-mini"
    base_url = (config.base_url or "https://api.openai.com").rstrip("/")
    body = {
        "model": model,
        "input": prompt,
        "temperature": config.temperature,
    }
    payload = http_post_json(
        f"{base_url}/v1/responses",
        body,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=60,
    )
    if not payload:
        return None
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]
    output = payload.get("output", [])
    for item in output:
        for content in item.get("content", []):
            text = content.get("text")
            if text:
                return text
    return None


def env_or_none(name: str) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def normalize_ollama_base_url(raw: str) -> str:
    cleaned = raw.strip().rstrip("/")
    if "://" not in cleaned:
        return f"http://{cleaned}"
    return cleaned


def ollama_base_url_from_env() -> str | None:
    if value := env_or_none("OLLAMA_BASE_URL"):
        return normalize_ollama_base_url(value)
    if value := env_or_none("OLLAMA_HOST"):
        return normalize_ollama_base_url(value)
    return None


def resolve_llm_config(args: argparse.Namespace) -> LLMConfig:
    provider = args.llm_provider
    model = args.llm_model or env_or_none("OLLAMA_MODEL")
    env_ollama_url = ollama_base_url_from_env()

    if provider == "ollama":
        if args.llm_base_url:
            base_url = normalize_ollama_base_url(args.llm_base_url)
        else:
            base_url = env_ollama_url or DEFAULT_OLLAMA_BASE_URL
    elif args.llm_base_url:
        base_url = normalize_ollama_base_url(args.llm_base_url)
    else:
        base_url = None

    if provider == "ollama" and not model:
        model = DEFAULT_OLLAMA_MODEL

    return LLMConfig(
        provider=provider,
        model=model,
        max_projects=args.llm_limit,
        temperature=args.llm_temperature,
        base_url=base_url,
    )


def ollama_request_timeout(model: str) -> int:
    lower = model.lower()
    if "32b" in lower or "70b" in lower:
        return 300
    return 120


def call_ollama(config: LLMConfig, prompt: str) -> str | None:
    model = config.model or DEFAULT_OLLAMA_MODEL
    base_url = (config.base_url or DEFAULT_OLLAMA_BASE_URL).rstrip("/")
    body = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": config.temperature},
    }
    payload = http_post_json(
        f"{base_url}/api/generate",
        body,
        timeout=ollama_request_timeout(model),
    )
    if not payload:
        return None
    response = payload.get("response")
    return response if isinstance(response, str) else None


def http_post_json(
    url: str,
    body: dict[str, Any],
    headers: dict[str, str] | None = None,
    timeout: int = 60,
) -> dict[str, Any] | None:
    all_headers = {"Content-Type": "application/json"}
    if headers:
        all_headers.update(headers)
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers=all_headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
