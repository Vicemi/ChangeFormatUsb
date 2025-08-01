from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QStyledItemDelegate, QStyleFactory, QMessageBox
from PyQt5.QtGui import QPalette, QColor, QLinearGradient, QBrush

class StyledItemDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        # Mejorar el aspecto de los elementos seleccionados
        if option.state & QStyleFactory.create("Fusion").State_Selected:
            gradient = QLinearGradient(option.rect.topLeft(), option.rect.bottomLeft())
            gradient.setColorAt(0, QColor(52, 152, 219))
            gradient.setColorAt(1, QColor(41, 128, 185))
            painter.fillRect(option.rect, QBrush(gradient))
            painter.setPen(Qt.white)
        else:
            super().paint(painter, option, index)
        
        super().paint(painter, option, index)

class DarkPalette(QPalette):
    def __init__(self):
        super().__init__()
        # Colores principales
        dark_color = QColor(44, 62, 80)       # Azul oscuro
        darker_color = QColor(34, 47, 62)     # Azul más oscuro
        text_color = QColor(236, 240, 241)    # Texto claro
        highlight = QColor(52, 152, 219)      # Azul brillante
        button_color = QColor(52, 73, 94)     # Botones
        
        # Configurar paleta
        self.setColor(QPalette.Window, dark_color)
        self.setColor(QPalette.WindowText, text_color)
        self.setColor(QPalette.Base, darker_color)
        self.setColor(QPalette.AlternateBase, dark_color)
        self.setColor(QPalette.ToolTipBase, text_color)
        self.setColor(QPalette.ToolTipText, text_color)
        self.setColor(QPalette.Text, text_color)
        self.setColor(QPalette.Button, button_color)
        self.setColor(QPalette.ButtonText, text_color)
        self.setColor(QPalette.BrightText, Qt.red)
        self.setColor(QPalette.Highlight, highlight)
        self.setColor(QPalette.HighlightedText, Qt.white)
        
        # Deshabilitados
        self.setColor(QPalette.Disabled, QPalette.Text, QColor(127, 140, 141))
        self.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(127, 140, 141))

class MessageBox(QMessageBox):
    def __init__(self, parent, title, text, icon):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setText(text)
        self.setIcon(icon)
        
        # Estilo personalizado para alertas
        self.setStyleSheet("""
            QMessageBox {
                background-color: #2c3e50;
            }
            QLabel {
                color: #ecf0f1;
                font-size: 12pt;
            }
            QPushButton {
                background-color: #3498db;
                color: white;
                border-radius: 5px;
                padding: 10px 20px;
                min-width: 100px;
                font-size: 11pt;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        
        # Aplicar paleta oscura
        palette = DarkPalette()
        self.setPalette(palette)