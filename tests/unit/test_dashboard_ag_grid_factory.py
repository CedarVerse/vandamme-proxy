import pytest


@pytest.mark.unit
def test_build_ag_grid_merges_row_selection_overrides():
    from src.dashboard.ag_grid.factories import build_ag_grid

    grid = build_ag_grid(
        grid_id="g",
        column_defs=[],
        row_data=[],
        dash_grid_options_overrides={"rowSelection": {"enableClickSelection": True}},
    )

    # Dash components store props in .to_plotly_json()
    props = grid.to_plotly_json()["props"]
    opts = props["dashGridOptions"]

    assert opts["rowSelection"]["mode"] == "multiRow"
    assert opts["rowSelection"]["enableClickSelection"] is True


@pytest.mark.unit
def test_build_ag_grid_sets_no_rows_message():
    from src.dashboard.ag_grid.factories import build_ag_grid

    grid = build_ag_grid(
        grid_id="g",
        column_defs=[],
        row_data=[],
        no_rows_message="Nope",
    )

    props = grid.to_plotly_json()["props"]
    assert props["dashGridOptions"]["localeText"]["noRowsToShow"] == "Nope"
