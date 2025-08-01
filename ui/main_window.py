from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QComboBox, QPushButton, QListWidget, QProgressBar, 
                             QMenuBar, QMenu, QAction, QMessageBox, QStyleFactory,
                             QDialog, QTextBrowser, QTabWidget, QGroupBox, QFormLayout,
                             QSizePolicy, QFrame, QSpacerItem, QApplication)
from PyQt5.QtCore import Qt, QTimer, QSize, QUrl, QThread, QMetaObject, Q_ARG, pyqtSlot, pyqtSignal
from PyQt5.QtGui import QFont, QPalette, QColor, QIcon, QDesktopServices
from ui.components import StyledItemDelegate, DarkPalette, MessageBox
from core.usb_manager import USBManager
from core.format_converter import FormatConverter
from core.admin_check import is_admin
from utils.i18n import resource_path
from utils.i18n import Translator
from logger import logger
import config
import webbrowser
import time
import os
import sys

class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Acerca de")
        self.setFixedSize(500, 400)
        self.setStyleSheet("""
            QDialog {
                background-color: #2c3e50;
                color: #ecf0f1;
            }
            QLabel {
                color: #ecf0f1;
            }
            QPushButton {
                background-color: #3498db;
                color: white;
                border-radius: 5px;
                padding: 8px 16px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QTabWidget::pane {
                border: 1px solid #34495e;
                border-radius: 5px;
                padding: 10px;
                background-color: #2c3e50;
            }
            QTabBar::tab {
                background: #34495e;
                color: #ecf0f1;
                padding: 8px 16px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #3498db;
                color: white;
            }
        """)
        
        layout = QVBoxLayout(self)
        
        # Título
        self.title_label = QLabel(f"{config.APP_NAME} v{config.APP_VERSION}")
        title_font = QFont("Segoe UI", 16, QFont.Bold)
        self.title_label.setFont(title_font)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("color: #3498db; padding: 10px;")
        layout.addWidget(self.title_label)
        
        # Pestañas
        tabs = QTabWidget()
        
        # Pestaña de información
        info_tab = QWidget()
        info_layout = QVBoxLayout(info_tab)
        
        info_group = QGroupBox("Información del programa")
        info_group.setStyleSheet("""
            QGroupBox {
                font-size: 12pt;
                color: #3498db;
                border: 1px solid #34495e;
                border-radius: 5px;
                margin-top: 20px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 10px;
            }
        """)
        form_layout = QFormLayout(info_group)
        
        form_layout.addRow("Autor:", QLabel(config.AUTHOR))
        form_layout.addRow("Versión:", QLabel(config.APP_VERSION))
        form_layout.addRow("Licencia:", QLabel("GPL-3.0"))
        
        info_layout.addWidget(info_group)
        info_layout.addStretch()
        
        # Pestaña de créditos
        credits_tab = QWidget()
        credits_layout = QVBoxLayout(credits_tab)
        
        credits = QTextBrowser()
        credits.setOpenExternalLinks(True)
        credits.setHtml("""
            <h2>Créditos y agradecimientos</h2>
            <p>Esta aplicación fue desarrollada por <strong>Vicemi</strong> con las siguientes tecnologías:</p>
            <ul>
                <li>Python 3.12</li>
                <li>PyQt5 para la interfaz gráfica</li>
                <li>PyInstaller para la distribución</li>
            </ul>
            <p><strong>Librerías utilizadas:</strong></p>
            <ul>
                <li>psutil - Monitoreo del sistema</li>
                <li>wmi - Gestión de dispositivos Windows</li>
                <li>pywin32 - Integración con Windows API</li>
            </ul>
            <h3>¡Apoya este proyecto!</h3>
            <p>Si te gusta esta aplicación, considera apoyar al desarrollador:</p>
        """)
        credits_layout.addWidget(credits)
        
        # Botones de acción
        buttons_layout = QHBoxLayout()
        
        donate_btn = QPushButton(QIcon(resource_path("resources/donate.png")), "Donar")
        donate_btn.setIconSize(QSize(24, 24))
        donate_btn.clicked.connect(lambda: webbrowser.open("https://paypal.me/vicemi"))
        buttons_layout.addWidget(donate_btn)
        
        repo_btn = QPushButton(QIcon(resource_path("resources/github.png")), "Repositorio")
        repo_btn.setIconSize(QSize(24, 24))
        repo_btn.clicked.connect(lambda: webbrowser.open("https://github.com/vicemi/ChangeFormatUSB"))
        buttons_layout.addWidget(repo_btn)
        
        credits_layout.addLayout(buttons_layout)
        
        # Añadir pestañas
        tabs.addTab(info_tab, "Información")
        tabs.addTab(credits_tab, "Créditos")
        
        layout.addWidget(tabs)
        
        # Botón de cierre
        close_btn = QPushButton("Cerrar")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignCenter)

class ConversionWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    progress_updated = pyqtSignal(int)

    def __init__(self, drive_letter, new_fs, parent=None):
        super().__init__(parent)
        self.drive_letter = drive_letter
        self.new_fs = new_fs
        self.running = True

    def run(self):
        try:
            def on_success(drive_letter):
                self.progress_updated.emit(100)
                self.finished.emit(drive_letter)

            def on_error(error_msg):
                self.error.emit(error_msg)

            # Llama al convertidor real
            FormatConverter().iniciar_conversion(
                self.drive_letter,
                self.new_fs,
                on_success,
                on_error
            )
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.running = False

    def cancel(self):
        self.running = False

class ChangeFormatUSB(QMainWindow):
    def __init__(self):
        super().__init__()
        self.translator = Translator()
        self.usb_manager = USBManager()
        self.setup_ui()
        self.setup_menu()
        self.setWindowIcon(QIcon(resource_path("resources/icon.ico")))
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_usb_list)
        self.refresh_timer.start(config.REFRESH_INTERVAL)
        self.refresh_usb_list()
        self.debug_mode = False
        self.conversion_thread = None
        
        # Verificar permisos de administrador
        if not is_admin():
            self.show_admin_warning()

    def setup_ui(self):
        self.setWindowTitle(f"{config.APP_NAME} (By {config.AUTHOR})")
        self.setGeometry(100, 100, 900, 600)
        
        # Estilo global
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2c3e50;
            }
            QLabel {
                color: #ecf0f1;
            }
            QGroupBox {
                font-size: 12pt;
                color: #3498db;
                border: 1px solid #34495e;
                border-radius: 5px;
                margin-top: 20px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 10px;
            }
            QPushButton {
                background-color: #3498db;
                color: white;
                border-radius: 5px;
                padding: 8px 16px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:disabled {
                background-color: #7f8c8d;
            }
            QListWidget {
                font-size: 11pt;
            }
            QComboBox {
                font-size: 11pt;
            }
        """)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Título
        self.title_label = QLabel(f"{config.APP_NAME} (By {config.AUTHOR})") 
        title_font = QFont("Segoe UI", 20, QFont.Bold)
        self.title_label.setFont(title_font)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("color: #3498db; padding: 10px;")
        main_layout.addWidget(self.title_label)

        # Contenedor principal
        container = QHBoxLayout()
        container.setSpacing(20)

        # Panel izquierdo - Dispositivos
        left_panel = QVBoxLayout()
        left_panel.setSpacing(15)
        
        # Grupo de dispositivos
        device_group = QGroupBox("Dispositivos USB")
        device_group.setObjectName("devicesGroup")
        device_layout = QVBoxLayout(device_group)
        
        self.usb_label = QLabel(self.translator.gettext("DISCONNECTED_DEVICES"))
        self.usb_label.setFont(QFont("Segoe UI", 10))
        device_layout.addWidget(self.usb_label)
        
        self.usb_list = QListWidget()
        self.usb_list.setItemDelegate(StyledItemDelegate())
        self.usb_list.setStyleSheet("""
            QListView {
                background-color: #34495e;
                color: #ecf0f1;
                border: 1px solid #2c3e50;
                border-radius: 5px;
                padding: 5px;
                font-size: 11pt;
            }
            QListView::item {
                padding: 12px;
                border-bottom: 1px solid #3d566e;
            }
            QListView::item:selected {
                background-color: #3498db;
                color: white;
                border-radius: 5px;
            }
        """)
        self.usb_list.setMinimumHeight(250)
        device_layout.addWidget(self.usb_list)
        
        left_panel.addWidget(device_group)

        # Panel derecho - Información y acciones
        right_panel = QVBoxLayout()
        right_panel.setSpacing(15)
        
        # Grupo de información
        info_group = QGroupBox("Información del dispositivo")
        info_group.setObjectName("infoGroup")
        info_layout = QVBoxLayout(info_group)
        
        self.info_widget = QWidget()
        info_inner_layout = QFormLayout(self.info_widget)
        info_inner_layout.setContentsMargins(15, 15, 15, 15)
        info_inner_layout.setSpacing(15)
        
        self.drive_label = QLabel(self.translator.gettext("DRIVE_LABEL"))
        self.drive_label.setFont(QFont("Segoe UI", 10))
        self.fs_label = QLabel(self.translator.gettext("FS_LABEL"))
        self.fs_label.setFont(QFont("Segoe UI", 10))
        self.size_label = QLabel(self.translator.gettext("SIZE_LABEL"))
        self.size_label.setFont(QFont("Segoe UI", 10))
        self.free_label = QLabel(self.translator.gettext("FREE_LABEL"))
        self.free_label.setFont(QFont("Segoe UI", 10))
        
        info_inner_layout.addRow("Unidad:", self.drive_label)
        info_inner_layout.addRow("Sistema de archivos:", self.fs_label)
        info_inner_layout.addRow("Tamaño total:", self.size_label)
        info_inner_layout.addRow("Espacio libre:", self.free_label)
        
        info_layout.addWidget(self.info_widget)
        right_panel.addWidget(info_group)
        
        # Grupo de formato
        format_group = QGroupBox("Convertir formato")
        format_group.setObjectName("formatGroup")
        format_layout = QVBoxLayout(format_group)
        
        format_controls = QHBoxLayout()
        format_controls.setSpacing(15)
        
        self.format_label = QLabel(self.translator.gettext("NEW_FORMAT")) 
        self.format_label.setFont(QFont("Segoe UI", 10))
        
        format_label = QLabel(self.translator.gettext("NEW_FORMAT"))
        format_label.setFont(QFont("Segoe UI", 10))
        self.format_combo = QComboBox()
        self.format_combo.addItems(config.SUPPORTED_FORMATS)
        self.format_combo.setStyleSheet("""
            QComboBox {
                background-color: #34495e;
                color: #ecf0f1;
                padding: 8px;
                border: 1px solid #2c3e50;
                border-radius: 4px;
                min-width: 120px;
            }
            QComboBox::drop-down {
                border: none;
            }
        """)
        
        format_controls.addWidget(format_label)
        format_controls.addWidget(self.format_combo)
        format_controls.addStretch()
        
        format_layout.addLayout(format_controls)
        
        self.convert_btn = QPushButton(self.translator.gettext("CONVERT_BTN"))
        self.convert_btn.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.convert_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                padding: 12px 24px;
                font-size: 12pt;
            }
            QPushButton:hover {
                background-color: #2ecc71;
            }
            QPushButton:disabled {
                background-color: #7f8c8d;
            }
        """)
        self.convert_btn.clicked.connect(self.convert_format)
        self.convert_btn.setEnabled(False)
        format_layout.addWidget(self.convert_btn, alignment=Qt.AlignCenter)
        
        right_panel.addWidget(format_group)
        
        # Barra de progreso
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setRange(0, 100)
        self.progress.setStyleSheet("""
            QProgressBar {
                border: 2px solid #3498db;
                border-radius: 5px;
                text-align: center;
                background-color: #2c3e50;
                height: 25px;
                font-size: 11pt;
                color: #ecf0f1;
            }
            QProgressBar::chunk {
                background-color: #2ecc71;
                width: 10px;
            }
        """)
        right_panel.addWidget(self.progress)
        
        # Añadir paneles al contenedor
        container.addLayout(left_panel, 55)
        container.addLayout(right_panel, 45)
        main_layout.addLayout(container)

        # Conexiones
        self.usb_list.itemSelectionChanged.connect(self.update_device_info)

        # Establecer paleta de colores
        self.setPalette(DarkPalette())
        self.setStyle(QStyleFactory.create("Fusion"))
        
        # Botón de créditos
        credits_btn = QPushButton("Créditos y Donaciones")
        credits_btn.setStyleSheet("background-color: #8e44ad;")
        credits_btn.clicked.connect(self.show_credits)
        main_layout.addWidget(credits_btn, alignment=Qt.AlignCenter)

    def setup_menu(self):
        menu_bar = QMenuBar(self)
        menu_bar.setStyleSheet("""
            QMenuBar {
                background-color: #34495e;
                color: #ecf0f1;
                padding: 5px;
            }
            QMenuBar::item {
                padding: 8px 16px;
                background-color: #34495e;
            }
            QMenuBar::item:selected {
                background-color: #3498db;
            }
            QMenu {
                background-color: #34495e;
                color: #ecf0f1;
                border: 1px solid #2c3e50;
                padding: 5px;
            }
            QMenu::item {
                padding: 8px 25px 8px 20px;
            }
            QMenu::item:selected {
                background-color: #3498db;
            }
            QMenu::icon {
                padding-left: 10px;
            }
        """)
        self.setMenuBar(menu_bar)

        # Menú de debug
        debug_menu = menu_bar.addMenu("🐞 Debug")
        toggle_debug_action = QAction("Activar modo Debug", self)
        toggle_debug_action.triggered.connect(self.toggle_debug_mode)
        debug_menu.addAction(toggle_debug_action)
        
        view_logs_action = QAction("Ver logs", self)
        view_logs_action.triggered.connect(self.view_logs)
        debug_menu.addAction(view_logs_action)

        # Menú de idioma
        language_menu = menu_bar.addMenu("🌐 " + self.translator.gettext("LANGUAGE_MENU"))
        language_menu.setObjectName("languageMenu")
        
        languages = self.translator.get_available_languages()
        for lang_code, lang_name in languages.items():
            action = QAction(lang_name, self)
            action.triggered.connect(lambda _, lc=lang_code: self.change_language(lc))
            language_menu.addAction(action)
        
        # Menú de ayuda
        help_menu = menu_bar.addMenu("❓ Ayuda")
        about_action = QAction("Acerca de", self)
        about_action.triggered.connect(self.show_credits)
        help_menu.addAction(about_action)

    def toggle_debug_mode(self):
        self.debug_mode = not self.debug_mode
        msg = "Modo debug ACTIVADO" if self.debug_mode else "Modo debug DESACTIVADO"
        logger.info(msg)
        QMessageBox.information(self, "Modo Debug", msg)
        
    def view_logs(self):
        log_dir = os.path.abspath("logs")
        if os.path.exists(log_dir):
            os.startfile(log_dir)
        else:
            QMessageBox.warning(self, "Logs", "No se encontró el directorio de logs")

    def show_credits(self):
        dialog = AboutDialog(self)
        dialog.exec_()

    def change_language(self, lang_code):
        self.translator.set_language(lang_code)
        self.retranslate_ui()

    def retranslate_ui(self):
        try:
            self.title_label.setText(f"{config.APP_NAME} (By {config.AUTHOR})")
            self.format_label.setText(self.translator.gettext("NEW_FORMAT"))
            self.setWindowTitle(f"{config.APP_NAME} (By {config.AUTHOR})")
            self.usb_label.setText(self.translator.gettext("DISCONNECTED_DEVICES"))
            
            devices_group = self.findChild(QGroupBox, "devicesGroup")
            if devices_group:
                devices_group.setTitle(self.translator.gettext("DEVICES_GROUP"))
                
            info_group = self.findChild(QGroupBox, "infoGroup")
            if info_group:
                info_group.setTitle(self.translator.gettext("DEVICE_INFO_GROUP"))
                
            format_group = self.findChild(QGroupBox, "formatGroup")
            if format_group:
                format_group.setTitle(self.translator.gettext("CONVERT_GROUP"))
            
            self.convert_btn.setText(self.translator.gettext("CONVERT_BTN"))
            
            if self.usb_list.selectedItems():
                self.update_device_info()
            else:
                self.clear_device_info()
                
            language_menu = self.menuBar().findChild(QMenu, "languageMenu")
            if language_menu:
                language_menu.setTitle("🌐 " + self.translator.gettext("LANGUAGE_MENU"))
                
            self.update()
        except Exception as e:
            logger.error(f"Error actualizando idioma: {str(e)}")

    def show_admin_warning(self):
        msg = MessageBox(
            self,
            self.translator.gettext("ADMIN_REQUIRED_TITLE"),
            self.translator.gettext("ADMIN_REQUIRED_MSG"),
            QMessageBox.Warning
        )
        msg.exec_()

    def refresh_usb_list(self):
        current_selection = self.usb_list.currentItem()
        current_drive = current_selection.text().split()[0] if current_selection else None
        
        self.usb_list.clear()
        usb_drives = self.usb_manager.get_usb_devices()
        
        if usb_drives:
            self.usb_label.setText(self.translator.gettext("CONNECTED_DEVICES"))
        else:
            self.usb_label.setText(self.translator.gettext("DISCONNECTED_DEVICES"))
        
        for drive in usb_drives:
            size_gb = int(drive['size']) / (1024**3) if drive['size'] else 0
            free_gb = int(drive['free']) / (1024**3) if drive['free'] else 0
            item_text = f"{drive['letter']} - {drive['label']} ({size_gb:.1f} GB, {drive['filesystem']})"
            self.usb_list.addItem(item_text)
            
            if current_drive == drive['letter']:
                self.usb_list.setCurrentRow(self.usb_list.count() - 1)

    def update_device_info(self):
        if not self.usb_list.selectedItems():
            self.clear_device_info()
            return
            
        selected_text = self.usb_list.currentItem().text()
        drive_letter = selected_text.split()[0]
        
        for drive in self.usb_manager.get_usb_devices():
            if drive['letter'] == drive_letter:
                size_gb = int(drive['size']) / (1024**3) if drive['size'] else 0
                free_gb = int(drive['free']) / (1024**3) if drive['free'] else 0
                
                self.drive_label.setText(
                    self.translator.gettext("DRIVE_LABEL_FORMAT").format(
                        letter=drive['letter'], label=drive['label']
                    )
                )
                self.fs_label.setText(
                    self.translator.gettext("FS_LABEL_FORMAT").format(
                        fs=drive['filesystem']
                    )
                )
                self.size_label.setText(
                    self.translator.gettext("SIZE_LABEL_FORMAT").format(
                        size=size_gb
                    )
                )
                self.free_label.setText(
                    self.translator.gettext("FREE_LABEL_FORMAT").format(
                        free=free_gb
                    )
                )
                self.convert_btn.setEnabled(True)
                break

    def clear_device_info(self):
        self.drive_label.setText(self.translator.gettext("DRIVE_LABEL"))
        self.fs_label.setText(self.translator.gettext("FS_LABEL"))
        self.size_label.setText(self.translator.gettext("SIZE_LABEL"))
        self.free_label.setText(self.translator.gettext("FREE_LABEL"))
        self.convert_btn.setEnabled(False)

    def convert_format(self):
        logger.debug("Iniciando proceso de conversión...")
        if not self.usb_list.selectedItems():
            return
            
        selected_text = self.usb_list.currentItem().text()
        drive_letter = selected_text.split()[0]
        new_fs = self.format_combo.currentText()
        
        reply = MessageBox(
            self,
            self.translator.gettext("CONFIRM_TITLE"),
            self.translator.gettext("CONFIRM_MSG").format(drive=drive_letter, format=new_fs),
            QMessageBox.Question
        ).exec_()
        
        if reply == QMessageBox.No:
            return
            
        # Deshabilitar controles durante la conversión
        self.convert_btn.setEnabled(False)
        self.usb_list.setEnabled(False)
        self.format_combo.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        
        # Crear y configurar el hilo de conversión
        self.conversion_thread = ConversionWorker(drive_letter, new_fs)
        self.conversion_thread.finished.connect(self.conversion_completed)
        self.conversion_thread.error.connect(self.conversion_error)
        self.conversion_thread.progress_updated.connect(self.update_progress)
        self.conversion_thread.start()

    def update_progress(self, value):
        self.progress.setValue(value)

    def conversion_completed(self, drive_letter):
        logger.info(f"Conversión completada exitosamente para {drive_letter}")
        
        # Restaurar UI
        self.progress.setVisible(False)
        self.convert_btn.setEnabled(True)
        self.usb_list.setEnabled(True)
        self.format_combo.setEnabled(True)
        
        # Limpiar referencia al hilo
        self.conversion_thread = None
        
        # Mostrar mensaje de éxito
        MessageBox(
            self,
            self.translator.gettext("SUCCESS_TITLE"),
            self.translator.gettext("SUCCESS_MSG").format(drive=drive_letter),
            QMessageBox.Information
        ).exec_()
        
        # Actualizar lista después de un tiempo
        QTimer.singleShot(1000, self.refresh_usb_list)
    
    def conversion_error(self, error_msg):
        logger.error(f"Error en conversión: {error_msg}")
        
        # Restaurar UI
        self.progress.setVisible(False)
        self.convert_btn.setEnabled(True)
        self.usb_list.setEnabled(True)
        self.format_combo.setEnabled(True)
        
        # Limpiar referencia al hilo
        self.conversion_thread = None
        
        # Mostrar mensaje de error
        MessageBox(
            self,
            self.translator.gettext("ERROR_TITLE"),
            self.translator.gettext("ERROR_MSG").format(error=error_msg),
            QMessageBox.Critical
        ).exec_()
    
    def closeEvent(self, event):
        if self.conversion_thread and self.conversion_thread.isRunning():
            reply = QMessageBox.question(
                self,
                "Operación en progreso",
                "Una conversión está en curso. ¿Estás seguro de que quieres salir?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.conversion_thread.cancel()
                self.conversion_thread.quit()
                self.conversion_thread.wait(2000)
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ChangeFormatUSB()
    window.show()
    sys.exit(app.exec_())