from qgis.PyQt.QtCore import QEvent, QPoint, QRect, QSize, Qt
from qgis.PyQt.QtGui import QPainter, QTextDocument
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


class ContributorAvatarsDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.avatar_size = 24
        self.max_avatars = 3

    def paint(self, painter: QPainter, option, index):
        contributors = index.data(Qt.ItemDataRole.UserRole)
        if not contributors:
            return

        # Calculate number of remaining contributors
        remaining = max(len(contributors) - self.max_avatars, 0)
        # Only show first 3 avatars
        visible_contributors = contributors[: self.max_avatars]

        x = option.rect.x() + (len(visible_contributors) - 1) * (self.avatar_size) // 2
        y = option.rect.y() + (option.rect.height() - self.avatar_size) // 2

        # Draw avatars
        for contributor in visible_contributors[::-1]:
            avatar = contributor.get("avatar")
            if avatar and not avatar.isNull():
                scaled_avatar = avatar.scaled(
                    self.avatar_size,
                    self.avatar_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                point = QPoint(x, y)
                painter.drawPixmap(point, scaled_avatar)
                x -= self.avatar_size // 2

        # Draw +m if there are remaining contributors
        if remaining > 0:
            painter.save()
            remaining_text = f"+{remaining}"
            # Position text after the last avatar
            text_x = option.rect.x() + 2 * self.avatar_size

            # Set up text style
            font = painter.font()
            font.setBold(True)
            painter.setFont(font)

            # Get font metrics to calculate vertical centering
            metrics = painter.fontMetrics()
            text_height = metrics.height()

            # Calculate y position to center the text vertically in the available space
            text_y = y + (self.avatar_size + metrics.ascent()) // 2

            # Draw the +m text
            painter.drawText(text_x, text_y, remaining_text)
            painter.restore()

    def sizeHint(self, option, index):
        contributors = index.data(Qt.ItemDataRole.UserRole)
        if not contributors:
            return QSize(0, self.avatar_size)

        visible_count = min(len(contributors), 3)
        width = self.avatar_size + (visible_count - 1) * self.avatar_size // 2

        # Add extra space for the +m text if needed
        if len(contributors) > 3:
            width += self.avatar_size  # Extra space for "+m" text

        return QSize(width, self.avatar_size)

    def helpEvent(self, event, view, option, index):
        if not event or not view:
            return False
        contributors = index.data(Qt.ItemDataRole.UserRole)
        if not contributors:
            return False

        mouse_pos = event.pos()
        radius = self.avatar_size // 2

        # Calculate the starting position (same as in paint method)
        x = option.rect.x()
        y = option.rect.y() + (option.rect.height() - self.avatar_size) // 2

        # Convert mouse position to be relative to the cell
        mouse_x = mouse_pos.x() - option.rect.x()
        mouse_y = mouse_pos.y() - option.rect.y()
        center_y = y + radius - option.rect.y()
        dy2 = (mouse_y - center_y) ** 2
        rad2 = radius**2

        # Check if mouse is over the +m text
        visible_contributors = contributors[: self.max_avatars]
        text_x = x + 2 * self.avatar_size
        if len(contributors) > self.max_avatars:
            text_rect = QRect(text_x, y, self.avatar_size, self.avatar_size)
            if text_rect.contains(mouse_pos):
                remaining = contributors[3:]
                tooltip = "Additional contributors:\n" + "\n".join(
                    c.get("name", "") for c in remaining if c.get("name")
                )
                QToolTip.showText(event.globalPos(), tooltip, view)
                return True

        # Check each visible avatar from front to back (reverse order of drawing)
        for contributor in visible_contributors:
            center_x = x + radius - option.rect.x()
            # If mouse is within the circle
            if ((mouse_x - center_x) ** 2 + dy2) <= rad2:
                name = contributor.get("name", "")
                if name:
                    QToolTip.showText(event.globalPos(), name, view)
                    return True
            # Move to next avatar position
            x += self.avatar_size // 2

        # Hide tooltip if we're not over any avatar
        QToolTip.hideText()
        return True
