from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QLabel,
    QVBoxLayout,
    QTabWidget,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QHBoxLayout,
    QHeaderView,
    QDialog,
    QDialogButtonBox,
)
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


# --- Ventana Principal ---
class VentanaPrincipal(QMainWindow):
    def __init__(self, credentials: Tuple[str, str]):
        super().__init__()
        self.setWindowTitle("Tickets de soporte")
        self.resize(1000, 650)
        self._credentials = credentials

        self.tabs = QTabWidget()
        self.tabs.addTab(VistaTicketsSoporte(self._credentials), "Tickets de soporte")
        self.setCentralWidget(self.tabs)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    dlg = CredencialesDialog()
    if dlg.exec() != QDialog.Accepted:
        sys.exit(0)

    credenciales = dlg.get_credentials()
    win = VentanaPrincipal(credenciales)
    win.show()
    sys.exit(app.exec())
