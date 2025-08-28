import pyplugin_installer
from qgis.core import QgsSettings
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.utils import isPluginLoaded, startPlugin


def check_dependency_loader():
    required_plugin = "nens_dependency_loader"
    if not isPluginLoaded(required_plugin):
        if (
            QMessageBox.question(
                None,
                "N&S Dependency Loader",
                "N&S Dependency Loader is required, but not loaded. Would you like to load it?",
            )
            == QMessageBox.Yes
        ):
            try:  # This is basically what qgis.utils.loadPlugin() does, but that also shows errors, so we need to do it explicitly
                __import__(required_plugin)
                plugin_loadable = True
            except:
                plugin_loadable = False

            if plugin_loadable:
                if not startPlugin(required_plugin):
                    QMessageBox.warning(
                        None,
                        "N&S Dependency Loader",
                        "Unable to start N&S Dependency Loader, please enable the plugin manually",
                    )
                    return
            else:
                pyplugin_installer.instance().fetchAvailablePlugins(True)
                pyplugin_installer.instance().installPlugin(required_plugin)

            QgsSettings().setValue("/PythonPlugins/" + required_plugin, True)
            QgsSettings().remove("/PythonPlugins/watchDogTimestamp/" + required_plugin)


def classFactory(iface):  # pylint: disable=invalid-name
    """Load RanaQgisPlugin class from file rana_qgis_plugin.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    check_dependency_loader()

    from .rana_qgis_plugin import RanaQgisPlugin

    return RanaQgisPlugin(iface)
