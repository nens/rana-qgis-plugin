from qgis.PyQt.QtGui import QIcon, QPalette
from qgis.PyQt.QtWidgets import QComboBox, QStyle, QStyleOptionComboBox, QStylePainter


class FilterComboBox(QComboBox):
    # Fix for placeholder in QComboBox
    # bugreport (fixed in 6.0.1 and 5.15.9): https://qt-project.atlassian.net/browse/QTBUG-90595
    # fix: https://stackoverflow.com/a/65830989
    def paintEvent(self, event):
        painter = QStylePainter(self)
        painter.setPen(self.palette().color(QPalette.Text))

        # draw the combobox frame, focusrect and selected etc.
        opt = QStyleOptionComboBox()
        self.initStyleOption(opt)
        painter.drawComplexControl(QStyle.CC_ComboBox, opt)

        if self.currentIndex() < 0:
            opt.palette.setBrush(
                QPalette.ButtonText,
                opt.palette.brush(QPalette.PlaceholderText).color(),
            )
            if self.placeholderText():
                opt.currentText = self.placeholderText()
                opt.currentIcon = QIcon(":images/themes/default/mActionFilter2.svg")

        # draw the icon and text
        painter.drawComplexControl(QStyle.CC_ComboBox, opt)
        painter.drawControl(QStyle.CE_ComboBoxLabel, opt)
