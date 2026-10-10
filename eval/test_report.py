from .metrics import AggregatedAccuracy
from .report import build_report, render_markdown_table


def _sample_aggregated() -> list[AggregatedAccuracy]:
    return [
        AggregatedAccuracy("A", "lieferschein", "clean", "quantity", 4, 0.75, 1.0),
        AggregatedAccuracy("B", "lieferschein", "clean", "quantity", 4, 0.5, 0.5),
    ]


def test_render_markdown_table_has_header_separator_and_one_row_per_entry() -> None:
    table = render_markdown_table(_sample_aggregated())
    lines = table.splitlines()

    assert lines[0].startswith("| doc_type")
    assert lines[1].startswith("|---")
    assert len(lines) == 2 + len(_sample_aggregated())
    assert "0.75" in lines[2]


def test_build_report_has_run_metadata_and_per_field_entries() -> None:
    report = build_report("test-run", 20, _sample_aggregated())

    assert report["run_id"] == "test-run"
    assert report["n_docs"] == 20
    assert len(report["per_field"]) == 2
    assert report["per_field"][0]["field"] == "quantity"
