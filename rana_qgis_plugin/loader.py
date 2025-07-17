from qgis.core import QgsDataSourceUri, QgsProject, QgsRasterLayer
from qgis.PyQt.QtCore import QObject, pyqtSlot

from rana_qgis_plugin.auth import get_authcfg_id
from rana_qgis_plugin.utils_api import get_tenant_file_descriptor


class Loader(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)

    @pyqtSlot(str)
    def open_wms(self, descriptor_id: str) -> bool:
        descriptor = get_tenant_file_descriptor(descriptor_id)
        for link in descriptor["links"]:
            if link["rel"] == "wms":
                for layer in descriptor["meta"]["layers"]:
                    quri = QgsDataSourceUri()
                    quri.setParam("layers", layer["code"])
                    quri.setParam("styles", "")
                    quri.setParam("format", "image/png")
                    quri.setParam("url", link["href"])
                    # the wms provider will take care to expand authcfg URI parameter with credential
                    # just before setting the HTTP connection.
                    quri.setAuthConfigId(get_authcfg_id())
                    rlayer = QgsRasterLayer(
                        bytes(quri.encodedUri()).decode(),
                        f"{layer['name']} ({layer['label']})",
                        "wms",
                    )
                    QgsProject.instance().addMapLayer(rlayer)
                return True

        return False
