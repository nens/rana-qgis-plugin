from qgis.utils import plugins


def get_plugin_instance(plugin_name):
    """Return given plugin name instance."""
    try:
        plugin_instance = plugins[plugin_name]
    except (AttributeError, KeyError):
        plugin_instance = None
    return plugin_instance


def get_threedi_models_and_simulations_instance():
    """Return ThreeDi Models and Simulations plugin instance."""
    return get_plugin_instance("threedi_models_and_simulations")


def get_threedi_results_analysis_tool_instance():
    return get_plugin_instance("threedi_results_analysis")
