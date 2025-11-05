from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QVBoxLayout, QTabWidget,
    QToolBar, QStatusBar, QFileDialog, QMessageBox, QMenu, QStyle, QStyleFactory,
    QTableWidget, QTableWidgetItem, QFormLayout, QLineEdit, QPushButton, QHBoxLayout, QHeaderView,
    QDialog, QDialogButtonBox
)
from PySide6.QtGui import QAction, QIcon
from PySide6.QtCore import Qt
import sys
from typing import Tuple

import requests
from requests.auth import HTTPBasicAuth
from requests.exceptions import RequestException
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

REDMINE_ISSUES_URL = (
    "https://redmine.famiq.com.ar/projects/ipin/issues.json?query_id=77&"
    "sort=priority%3Adesc%2Cupdated_on%3Adesc"
)


class CredencialesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Credenciales de Redmine")
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self._usuario = QLineEdit()
        self._usuario.setPlaceholderText("Usuario")
        self._clave = QLineEdit()
        self._clave.setPlaceholderText("Contraseña")
        self._clave.setEchoMode(QLineEdit.Password)

        form.addRow("Usuario:", self._usuario)
        form.addRow("Contraseña:", self._clave)
        layout.addLayout(form)

        self._buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

    def get_credentials(self) -> Tuple[str, str]:
        return self._usuario.text().strip(), self._clave.text()

    def accept(self):
        usuario, clave = self.get_credentials()
        if not usuario or not clave:
            QMessageBox.warning(self, "Credenciales incompletas", "Ingresá usuario y contraseña de Redmine.")
            return
        super().accept()


# --- Vista con formulario + tabla (para la pestaña "Inicio") ---
class VistaInicio(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        # --- Formulario simple ---
        form = QFormLayout()
        self.txt_nombre = QLineEdit()
        self.txt_apellido = QLineEdit()
        self.txt_email = QLineEdit()
        btn_enviar = QPushButton("Enviar")
        btn_enviar.clicked.connect(self.enviar_formulario)

        form.addRow("Nombre:", self.txt_nombre)
        form.addRow("Apellido:", self.txt_apellido)
        form.addRow("Email:", self.txt_email)
        layout.addLayout(form)
        layout.addWidget(btn_enviar)

        # --- Tabla de ejemplo 6x10 ---
        tabla = QTableWidget(6, 10)
        tabla.setHorizontalHeaderLabels([f"Col {i+1}" for i in range(10)])
        for f in range(6):
            for c in range(10):
                tabla.setItem(f, c, QTableWidgetItem(f"Fila {f+1}, Col {c+1}"))
        layout.addWidget(tabla)

        layout.addStretch()
        self.tabla = tabla

    def enviar_formulario(self):
        nombre = self.txt_nombre.text()
        apellido = self.txt_apellido.text()
        email = self.txt_email.text()
        QMessageBox.information(
            self,
            "Formulario enviado",
            f"Nombre: {nombre}\nApellido: {apellido}\nEmail: {email}"
        )

class VistaTicketsSoporte(QWidget):
    def __init__(self, credentials: Tuple[str, str]):
        super().__init__()
        self._credentials = credentials

        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        header.addWidget(QLabel("<b>Tickets de soporte</b>"))
        header.addStretch()
        self._btn_refresh = QPushButton("Actualizar")
        self._btn_refresh.clicked.connect(self.cargar_datos)
        header.addWidget(self._btn_refresh)
        layout.addLayout(header)

        self._estado = QLabel()
        self._estado.setWordWrap(True)
        layout.addWidget(self._estado)

        self._headers = [
            "ID", "Proyecto", "Tracker", "Estado", "Prioridad",
            "Asignado a", "Sector", "Gerencia", "Origen", "Subject", "Actualizado"
        ]
        self._tabla = QTableWidget(0, len(self._headers))
        self._tabla.setHorizontalHeaderLabels(self._headers)
        self._tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self._tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self._tabla.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._tabla)

        self.cargar_datos()

    def cargar_datos(self):
        self._btn_refresh.setEnabled(False)
        self._estado.setText("Cargando tickets desde Redmine…")
        QApplication.processEvents()

        usuario, clave = self._credentials
        try:
            respuesta = requests.get(
                REDMINE_ISSUES_URL,
                auth=HTTPBasicAuth(usuario, clave),
                timeout=15,
                verify=False,
            )
            respuesta.raise_for_status()
            data = respuesta.json()
            issues = data.get("issues", []) or []
        except (RequestException, ValueError) as exc:
            self._tabla.setRowCount(0)
            self._estado.setText(f"Error al obtener tickets: {exc}")
            self._btn_refresh.setEnabled(True)
            return

        self._tabla.setRowCount(len(issues))

        def buscar_custom_field(campos, nombre):
            for campo in campos or []:
                if campo.get("name") == nombre:
                    valor = campo.get("value")
                    if isinstance(valor, list):
                        return ", ".join(valor)
                    return valor or ""
            return ""

        for fila, issue in enumerate(issues):
            custom_fields = issue.get("custom_fields")
            valores = [
                issue.get("id", ""),
                issue.get("project", {}).get("name", ""),
                issue.get("tracker", {}).get("name", ""),
                issue.get("status", {}).get("name", ""),
                issue.get("priority", {}).get("name", ""),
                issue.get("assigned_to", {}).get("name", ""),
                buscar_custom_field(custom_fields, "Sector"),
                buscar_custom_field(custom_fields, "Gerencia"),
                buscar_custom_field(custom_fields, "Origen"),
                issue.get("subject", ""),
                issue.get("updated_on", ""),
            ]
            for col, valor in enumerate(valores):
                item = QTableWidgetItem(str(valor))
                if self._headers[col] == "ID":
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self._tabla.setItem(fila, col, item)

        self._estado.setText(f"Tickets cargados: {len(issues)}")
        self._btn_refresh.setEnabled(True)


# --- Vista genérica (para las otras pestañas) ---
class VistaPlaceholder(QWidget):
    def __init__(self, titulo: str, descripcion: str = ""):
        super().__init__()
        lay = QVBoxLayout(self)
        lbl_t = QLabel(f"<h2>{titulo}</h2>")
        lbl_d = QLabel(descripcion or "Contenido de ejemplo…")
        lbl_t.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        lbl_d.setWordWrap(True)
        lay.addWidget(lbl_t)
        lay.addWidget(lbl_d)
        lay.addStretch()


# --- Ventana Principal ---
class VentanaPrincipal(QMainWindow):
    def __init__(self, credentials: Tuple[str, str]):
        super().__init__()
        self.setWindowTitle("Demo PySide6 - Menú + Formulario + Tabla + Issues")
        self.resize(1000, 650)
        self._credentials = credentials

        # ----- Crear pestañas -----
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setMovable(True)

        vistas = [
            ("Inicio", VistaInicio()),
            ("Carga de horas", VistaPlaceholder("Formas", "Rectángulos, círculos, flechas.")),
            ("Corrector de tickets", VistaPlaceholder("Texto", "Cajas de texto, tipografías.")),
            ("Tickets de soporte", VistaTicketsSoporte(self._credentials)),
            ("Colores", VistaPlaceholder("Colores", "Paletas, cuentagotas.")),
            ("Efectos", VistaPlaceholder("Efectos", "Filtros y ajustes rápidos.")),
            ("Capas", VistaPlaceholder("Capas", "Organiza elementos por capas.")),
            ("Historial", VistaPlaceholder("Historial", "Deshacer/rehacer y snapshots.")),
            ("Configuración", VistaPlaceholder("Configuración", "Preferencias de la aplicación."))
        ]
        for nombre, widget in vistas:
            self.tabs.addTab(widget, nombre)
        self.setCentralWidget(self.tabs)

        # ----- Menús, barra, estado -----
        self._crear_menus()
        self._crear_toolbar()
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Listo")
        QApplication.setStyle(QStyleFactory.create("Fusion"))

    # ====== Menús ======
    def _crear_menus(self):
        menubar = self.menuBar()

        # Archivo
        m_archivo = menubar.addMenu("&Archivo")
        act_nuevo = QAction(self.style().standardIcon(QStyle.SP_FileIcon), "Nuevo", self)
        act_nuevo.setShortcut("Ctrl+N")
        act_nuevo.triggered.connect(self.accion_nuevo)

        act_abrir = QAction(self.style().standardIcon(QStyle.SP_DialogOpenButton), "Abrir…", self)
        act_abrir.setShortcut("Ctrl+O")
        act_abrir.triggered.connect(self.accion_abrir)

        act_guardar = QAction(self.style().standardIcon(QStyle.SP_DialogSaveButton), "Guardar", self)
        act_guardar.setShortcut("Ctrl+S")
        act_guardar.triggered.connect(self.accion_guardar)

        m_archivo.addAction(act_nuevo)
        m_archivo.addAction(act_abrir)
        m_archivo.addAction(act_guardar)
        m_archivo.addSeparator()
        m_archivo.addAction("Salir", self.close)

        # Editar
        m_editar = menubar.addMenu("&Editar")
        for texto, sc in [("Deshacer", "Ctrl+Z"), ("Rehacer", "Ctrl+Y"),
                          ("Copiar", "Ctrl+C"), ("Pegar", "Ctrl+V")]:
            act = QAction(texto, self)
            act.setShortcut(sc)
            act.triggered.connect(self._accion_stub)
            m_editar.addAction(act)

        # Ver
        m_ver = menubar.addMenu("&Ver")
        self.act_toggle_toolbar = QAction("Mostrar barra de herramientas", self, checkable=True, checked=True)
        self.act_toggle_toolbar.triggered.connect(self._toggle_toolbar)
        self.act_toggle_status = QAction("Mostrar barra de estado", self, checkable=True, checked=True)
        self.act_toggle_status.triggered.connect(self._toggle_status)
        m_ver.addAction(self.act_toggle_toolbar)
        m_ver.addAction(self.act_toggle_status)

        # Ayuda
        m_ayuda = menubar.addMenu("Ay&uda")
        act_acerca = QAction("Acerca de…", self)
        act_acerca.triggered.connect(self.accion_acerca_de)
        m_ayuda.addAction(act_acerca)

        self.act_nuevo = act_nuevo
        self.act_abrir = act_abrir
        self.act_guardar = act_guardar

    # ====== Toolbar ======
    def _crear_toolbar(self):
        tb = QToolBar("Acceso rápido", self)
        tb.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.addToolBar(Qt.TopToolBarArea, tb)
        tb.addAction(self.act_nuevo)
        tb.addAction(self.act_abrir)
        tb.addAction(self.act_guardar)
        self.toolbar = tb

    # ====== Acciones y helpers ======
    def _toggle_toolbar(self, checked): self.toolbar.setVisible(checked)
    def _toggle_status(self, checked): self.statusBar().setVisible(checked)
    def _accion_stub(self): self.status.showMessage("Acción demo", 2000)

    def accion_nuevo(self):
        QMessageBox.information(self, "Nuevo", "Crear un nuevo documento.")

    def accion_abrir(self):
        ruta, _ = QFileDialog.getOpenFileName(self, "Abrir", "", "Proyecto (*.pnt);;Todos (*.*)")
        if ruta:
            QMessageBox.information(self, "Abrir", f"Abriste:\n{ruta}")

    def accion_guardar(self):
        ruta, _ = QFileDialog.getSaveFileName(self, "Guardar", "proyecto.pnt", "Proyecto (*.pnt)")
        if ruta:
            QMessageBox.information(self, "Guardar", f"Guardado en:\n{ruta}")

    def accion_acerca_de(self):
        QMessageBox.information(
            self, "Acerca de",
            "Demo PySide6\nMenú tipo Paint + Formulario + Tabla + Issues (JSON)."
        )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    dlg = CredencialesDialog()
    if dlg.exec() != QDialog.Accepted:
        sys.exit(0)

    credenciales = dlg.get_credentials()
    win = VentanaPrincipal(credenciales)
    win.show()
    sys.exit(app.exec())
