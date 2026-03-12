from copy import deepcopy
from functools import cached_property

from threedi_api_client.openapi import ApiException

from rana_qgis_plugin.simulation.threedi_calls import ThreediCalls
from rana_qgis_plugin.utils import get_threedi_api
from rana_qgis_plugin.utils_api import get_tenant_file_descriptor_view


def get_ready_state_from_descriptor(descriptor: dict) -> bool:
    return (descriptor.get("status") or {}).get("id") in ["completed", "processing"]


def get_is_3di_simulation(descriptor: dict) -> bool:
    return (descriptor.get("meta") or {})["simulation"].get("software", {}).get(
        "id"
    ) == "3Di"


class ScenarioInfo:
    def __init__(self, descriptor: dict):
        # Cannot be initialized for a descriptor without meta data or of any other type then scenario
        assert descriptor["data_type"] == "scenario"
        assert descriptor["meta"]
        self.descriptor = descriptor
        self.meta = descriptor["meta"]
        # set simulation info from metadata
        schematisation = self.meta.get("schematisation") or {}
        self.schematisation_id = schematisation.get("id")
        self.schematisation_name = schematisation.get("name")
        self.revision_number = schematisation.get("version")
        simulation = self.meta.get("simulation") or {}
        self.simulation_id = simulation.get("id")
        self.simulation_name = simulation.get("name")
        # set preliminary value of has_3di_simulation
        self.has_3di_simulation: bool = self.simulation_id is not None
        # check if all simulation data exists, and update if needed
        if self.has_3di_simulation:
            self.set_simulation_info_from_threedi()

    def set_simulation_info_from_threedi(self):
        """
        Ensure all simulation info is properly set and update missing information via threedi.
        If any information cannot be retrieved, set has_3di_simulation to False.
        """
        if all(
            [
                self.schematisation_id,
                self.schematisation_name,
                self.revision_number,
                self.simulation_id,
                self.simulation_name,
            ]
        ):
            return
        tc = ThreediCalls(get_threedi_api())
        # threedi-api fails when the simulation cannot be found
        try:
            simulation = tc.fetch_simulation(self.simulation_id)
        except ApiException:
            self.has_3di_simulation = False
            return
        if not self.simulation_name:
            self.simulation_name = simulation.name
        if not all(
            [
                self.schematisation_id,
                self.schematisation_name,
                self.revision_number,
                self.simulation_id,
            ]
        ):
            threedimodel = tc.fetch_3di_model(simulation.threedimodel_id)
            if threedimodel:
                if not self.schematisation_name:
                    self.schematisation_name = threedimodel.name
                if not self.schematisation_id:
                    self.schematisation_id = threedimodel.id
                if not self.revision_number:
                    self.revision_number = threedimodel.revision_number
        if not all(
            [
                self.schematisation_id,
                self.schematisation_name,
                self.revision_number,
                self.simulation_id,
                self.simulation_name,
            ]
        ):
            self.has_3di_simulation = False

    @cached_property
    def ready(self) -> bool:
        return get_ready_state_from_descriptor(self.descriptor)

    @cached_property
    def has_lizard_results(self) -> bool:
        return self.meta.get("id") is not None

    def get_grid(self):
        return deepcopy(self.grid) or {}

    @cached_property
    def lizard_results(self):
        return get_tenant_file_descriptor_view(
            self.descriptor.get("id"), "lizard-scenario-results"
        )

    @cached_property
    def grid(self):
        return self.meta.get("grid") or {}

    @cached_property
    def crs(self):
        return self.grid.get("crs")

    @cached_property
    def pixel_size(self):
        return self.grid.get("x", {}).get("cell_size", 1)
