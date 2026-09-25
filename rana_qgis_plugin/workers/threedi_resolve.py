"""Background resolution of scenario 3Di metadata."""

from typing import cast

from qgis.core import QgsTask

from rana_qgis_plugin.utils.scenario import ScenarioInfo


class ScenarioResolveTask(QgsTask):
    """Resolve one scenario's missing 3Di metadata in the background."""

    def __init__(self, scenario_info: ScenarioInfo, threedi_api) -> None:
        cancel_flag = cast("QgsTask.Flags", getattr(QgsTask, "CanCancel", 0))
        super().__init__("Resolve scenario details", cancel_flag)
        self.scenario_info = scenario_info
        self.threedi_api = threedi_api

    def run(self) -> bool:
        if self.isCanceled():
            return False

        try:
            self.scenario_info.set_simulation_info_from_threedi(self.threedi_api)
        except Exception:
            self.scenario_info.has_3di_simulation = False
        return True
