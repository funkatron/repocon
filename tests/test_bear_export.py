from pathlib import Path
from unittest.mock import patch

import pytest

from repocon.analyzer import (
    GitSummary,
    ProjectReport,
    StructureSignals,
    detect_project_families,
    render_index_markdown,
)
from repocon.bear_export import export_reports_to_bear, note_title_from_markdown


def _report(name: str) -> ProjectReport:
    return ProjectReport(
        name=name,
        path=f"/src/{name}",
        stack=["Python"],
        top_level_folders=["src"],
        one_liner=f"{name} one-liner",
        plain_english_summary="plain",
        technical_summary="technical",
        initial_intent="intent",
        git=GitSummary(tracked=False),
        current_state="Healthy",
        health_signals=[],
        risks=[],
        recommendations=[],
        priority_recommendation="priority",
        monetization_potential="low",
        similarity_tokens=[],
        structure=StructureSignals(),
    )


def test_detect_project_families_groups_prefix_clusters() -> None:
    reports = [
        _report("draw-things"),
        _report("draw-things-grpcservercli-installer"),
        _report("dts-utils"),
        _report("now-playing"),
    ]
    families = detect_project_families(reports)
    labels = {family.label for family in families}
    assert "draw-things" in labels
    draw_family = next(family for family in families if family.label == "draw-things")
    assert "draw-things-grpcservercli-installer" in draw_family.members


def test_render_index_includes_families_section() -> None:
    reports = [_report("draw-things"), _report("draw-things-batch")]
    index_md = render_index_markdown(
        reports,
        Path("/src"),
        Path("/tmp/reports"),
        families=detect_project_families(reports),
    )
    assert "## Families" in index_md
    assert "### draw-things" in index_md
    assert "| Run | Tests |" in index_md


def test_note_title_from_markdown_uses_heading() -> None:
    path = Path("/tmp/example.md")
    path.write_text("# now-playing\n\nBody\n", encoding="utf-8")
    assert note_title_from_markdown(path) == "now-playing"


@patch("repocon.bear_export.create_bear_note")
@patch("repocon.bear_export.time.sleep")
@patch("sys.platform", "darwin")
def test_export_reports_to_bear_creates_index_last(
    _sleep: object,
    mock_create: object,
    tmp_path: Path,
) -> None:
    projects = tmp_path / "projects"
    projects.mkdir()
    (projects / "repocon.md").write_text("# repocon\n\nBrief\n", encoding="utf-8")
    (tmp_path / "index.md").write_text("# Project Briefs\n", encoding="utf-8")

    count = export_reports_to_bear(tmp_path, open_index=True)

    assert count == 2
    assert mock_create.call_count == 2
    last_call = mock_create.call_args_list[-1]
    assert last_call.args[0] == "Project Briefs"
    assert last_call.kwargs["open_note"] is True


@patch("sys.platform", "linux")
def test_export_reports_to_bear_requires_macos() -> None:
    with pytest.raises(RuntimeError, match="macOS"):
        export_reports_to_bear(Path("/tmp/reports"))
