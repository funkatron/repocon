from pathlib import Path

from repocon.analyzer import (
    LINK_STYLE_BEAR,
    LINK_STYLE_MARKED,
    analyze_project,
    build_folder_roles,
    collect_top_level_folders,
    detect_test_signals,
    format_wiki_link,
    is_ignored_dir,
    load_manifests,
    render_index_markdown,
    render_project_markdown,
)

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_APP = FIXTURES / "sample-cli-app"


def test_is_ignored_dir_skips_report_artifacts() -> None:
    assert is_ignored_dir("reports")
    assert is_ignored_dir("reports-ollama")
    assert is_ignored_dir("reports-sample")
    assert not is_ignored_dir("src")
    assert not is_ignored_dir("scripts")


def test_collect_top_level_folders_ignores_report_output_dirs() -> None:
    folders = collect_top_level_folders(SAMPLE_APP)
    assert "src" in folders
    assert "tests" in folders
    assert "reports" not in folders
    assert "reports-sample" not in folders


def test_build_folder_roles_adds_descriptions() -> None:
    roles = build_folder_roles(["src", "tests", "custom-dir"])
    assert roles[0] == "src — application source code"
    assert roles[1] == "tests — automated tests"
    assert roles[2] == "custom-dir"


def test_detect_test_signals_from_manifest_and_layout() -> None:
    manifests = load_manifests(SAMPLE_APP)
    signals = detect_test_signals(SAMPLE_APP, manifests)
    assert any("tests/" in signal for signal in signals)
    assert any("pytest configured in pyproject.toml" in signal for signal in signals)


def test_analyze_project_includes_run_and_test_metadata() -> None:
    report = analyze_project(SAMPLE_APP)

    assert "reports" not in report.top_level_folders
    assert any("src — application source code" in role for role in report.structure.folder_roles)
    assert report.structure.run_hints
    assert report.structure.test_signals
    assert "Test tooling detected" in " ".join(report.health_signals)

    markdown = render_project_markdown(report)
    assert "Likely run commands:" in markdown
    assert "Test signals:" in markdown
    assert "reports-sample" not in markdown


def test_format_wiki_link_matches_bear_style() -> None:
    assert format_wiki_link("now-playing") == "[[now-playing]]"
    assert format_wiki_link("Project Briefs") == "[[Project Briefs]]"


def test_render_index_uses_bear_links_by_default() -> None:
    report = analyze_project(SAMPLE_APP)
    index_md = render_index_markdown([report], SAMPLE_APP.parent, FIXTURES / "output")
    assert "- [[sample-cli-app]]" in index_md
    assert "Bear-style" in index_md


def test_render_index_marked_uses_absolute_paths() -> None:
    report = analyze_project(SAMPLE_APP)
    output_dir = FIXTURES / "output"
    index_md = render_index_markdown(
        [report],
        SAMPLE_APP.parent,
        output_dir,
        link_style=LINK_STYLE_MARKED,
    )
    brief_path = (output_dir / "projects" / "sample-cli-app.md").resolve()
    assert f"- [sample-cli-app]({brief_path})" in index_md
    assert "absolute paths" in index_md


def test_render_project_includes_back_link_to_index() -> None:
    report = analyze_project(SAMPLE_APP)
    markdown = render_project_markdown(report, link_style=LINK_STYLE_BEAR)
    assert "← [[Project Briefs]]" in markdown
