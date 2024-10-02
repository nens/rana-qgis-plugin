def classFactory(iface):  # pylint: disable=invalid-name
    """Load RanaQgisPlugin class from file rana_qgis_plugin.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """

    from .rana_qgis_plugin import RanaQgisPlugin

    return RanaQgisPlugin(iface)
