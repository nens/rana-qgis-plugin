from qgis.PyQt.QtCore import QEvent, QSize, Qt
from qgis.PyQt.QtGui import QTextDocument
from qgis.PyQt.QtWidgets import (
    QApplication,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QToolTip,
)


class WordWrapDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        options = QStyleOptionViewItem(option)
        self.initStyleOption(options, index)
        options.features |= QStyleOptionViewItem.WrapText
        style = (
            QApplication.style() if options.widget is None else options.widget.style()
        )
        style.drawControl(QStyle.CE_ItemViewItem, options, painter)

    def sizeHint(self, option, index):
        options = QStyleOptionViewItem(option)
        self.initStyleOption(options, index)
        options.features |= QStyleOptionViewItem.WrapText

        # Calculate required size with wrapping
        doc = QTextDocument()
        doc.setHtml(options.text)
        doc.setTextWidth(option.rect.width())

        # Convert float height to int using round or int
        return QSize(option.rect.width(), int(doc.size().height()))

    def helpEvent(self, event, view, option, index):
        """Handle tooltip events to show the full text when hovering."""
        if not event or not view or event.type() != QEvent.ToolTip:
            return super().helpEvent(event, view, option, index)

        text = index.data(Qt.DisplayRole)
        if not text:
            return super().helpEvent(event, view, option, index)

        QToolTip.showText(event.globalPos(), text)
        return True
