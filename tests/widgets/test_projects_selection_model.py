from qgis.PyQt.QtCore import Qt

from rana_qgis_plugin.widgets.projects_selection_dialog import ProjectsModel

PROJECTS = [{"id": f"p{i}", "name": f"p{i}"} for i in range(10)]
PERSISTED_HIDDEN = {f"p{i}" for i in range(7)}
HIDDEN_AFTER_P0_SHOWN = {f"p{i}" for i in range(1, 7)}
NO_SORT = -1
NAME_COLUMN = 1
CHECK_COLUMN = 0


def load(model: ProjectsModel, projects: list[dict] = PROJECTS) -> None:
    model.load_projects(projects, NO_SORT, Qt.SortOrder.AscendingOrder)


def id_at(model: ProjectsModel, row: int) -> str:
    return model.data(model.index(row, NAME_COLUMN), Qt.ItemDataRole.DisplayRole)


def row_of(model: ProjectsModel, project_id: str) -> int:
    for row in range(model.rowCount()):
        if id_at(model, row) == project_id:
            return row
    raise AssertionError(f"{project_id} not displayed")


def set_checked(model: ProjectsModel, project_id: str, checked: bool) -> None:
    state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
    model.setData(
        model.index(row_of(model, project_id), CHECK_COLUMN),
        state,
        Qt.ItemDataRole.CheckStateRole,
    )


def visible_ids(model: ProjectsModel) -> set[str]:
    return {
        id_at(model, row)
        for row in range(model.rowCount())
        if model.data(model.index(row, CHECK_COLUMN), Qt.ItemDataRole.CheckStateRole)
        == Qt.CheckState.Checked
    }


def test_untouched_hidden_projects_stay_hidden_when_one_is_shown():
    model = ProjectsModel(set(PERSISTED_HIDDEN))
    load(model)

    set_checked(model, "p0", True)

    assert model.effective_hidden_ids(PERSISTED_HIDDEN) == HIDDEN_AFTER_P0_SHOWN


def test_confirm_without_changes_keeps_hidden_set():
    model = ProjectsModel(set(PERSISTED_HIDDEN))
    load(model)

    assert model.effective_hidden_ids(PERSISTED_HIDDEN) == PERSISTED_HIDDEN


def test_hiding_additional_project_adds_it_to_hidden_set():
    model = ProjectsModel(set(PERSISTED_HIDDEN))
    load(model)

    set_checked(model, "p9", False)

    assert model.effective_hidden_ids(PERSISTED_HIDDEN) == PERSISTED_HIDDEN | {"p9"}


def test_hidden_project_outside_filtered_list_stays_hidden():
    model = ProjectsModel(set(PERSISTED_HIDDEN))
    load(model, [PROJECTS[9]])

    set_checked(model, "p9", True)

    assert model.effective_hidden_ids(PERSISTED_HIDDEN) == PERSISTED_HIDDEN


def test_override_survives_reload_after_filter_change():
    model = ProjectsModel(set(PERSISTED_HIDDEN))
    load(model)
    set_checked(model, "p0", True)

    load(model, [PROJECTS[1]])

    assert visible_ids(model) == set()
    assert model.effective_hidden_ids(PERSISTED_HIDDEN) == HIDDEN_AFTER_P0_SHOWN


def test_set_all_hidden_then_show_one_leaves_only_that_visible():
    model = ProjectsModel(set(PERSISTED_HIDDEN))
    load(model)

    model.set_all_visible(False)
    set_checked(model, "p0", True)

    assert visible_ids(model) == {"p0"}
    expected = {f"p{i}" for i in range(1, 10)}
    assert model.effective_hidden_ids(PERSISTED_HIDDEN) == expected
