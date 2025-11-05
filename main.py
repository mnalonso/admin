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

REDMINE_BASE_URL = "https://redmine.famiq.com.ar"
REDMINE_ISSUES_URL = (
    f"{REDMINE_BASE_URL}/projects/ipin/issues.json?query_id=77&"
    "sort=priority%3Adesc%2Cupdated_on%3Adesc"
)
REDMINE_USERS_URL = f"{REDMINE_BASE_URL}/users.json"
REDMINE_USER_DETAIL_URL = f"{REDMINE_BASE_URL}/users/{{user_id}}.json"
REDMINE_ISSUES_SEARCH_URL = f"{REDMINE_BASE_URL}/issues.json"


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


class VistaActividadUsuario(QWidget):
    _COLUMNAS = ["ID", "Proyecto", "Estado", "Prioridad", "Subject", "Actualizado"]

    def __init__(self, credentials: Tuple[str, str]):
        super().__init__()
        self._credentials = credentials

        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        header.addWidget(QLabel("<b>Actividad por usuario</b>"))
        header.addStretch()
        layout.addLayout(header)

        form = QHBoxLayout()
        self._entrada_usuario = QLineEdit()
        self._entrada_usuario.setPlaceholderText("Ingresá ID numérico o usuario de Redmine")
        form.addWidget(self._entrada_usuario)

        self._btn_buscar = QPushButton("Buscar")
        self._btn_buscar.clicked.connect(self.buscar_usuario)
        form.addWidget(self._btn_buscar)
        layout.addLayout(form)

        self._estado = QLabel("Ingresá un usuario y presioná Buscar.")
        self._estado.setWordWrap(True)
        layout.addWidget(self._estado)

        self._tablas_por_estado = {
            "progreso": self._crear_tabla("Tickets en progreso"),
            "pruebas": self._crear_tabla("Tickets en pruebas"),
            "rtd": self._crear_tabla("Tickets en RTD"),
        }
        for tabla in self._tablas_por_estado.values():
            layout.addWidget(tabla["contenedor"])

    def _crear_tabla(self, titulo: str):
        contenedor = QWidget()
        contenedor_layout = QVBoxLayout(contenedor)
        contenedor_layout.setContentsMargins(0, 12, 0, 0)
        contenedor_layout.addWidget(QLabel(f"<b>{titulo}</b>"))
        tabla = QTableWidget(0, len(self._COLUMNAS))
        tabla.setHorizontalHeaderLabels(self._COLUMNAS)
        tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        tabla.horizontalHeader().setStretchLastSection(True)
        contenedor_layout.addWidget(tabla)
        return {"contenedor": contenedor, "tabla": tabla}

    def buscar_usuario(self):
        identificador = self._entrada_usuario.text().strip()
        if not identificador:
            QMessageBox.warning(self, "Dato requerido", "Ingresá un ID o usuario de Redmine.")
            return

        self._btn_buscar.setEnabled(False)
        self._estado.setText("Buscando información del usuario…")
        QApplication.processEvents()

        try:
            usuario_id, usuario_nombre = self._resolver_usuario(identificador)
            if usuario_id is None:
                self._estado.setText("No se encontró el usuario especificado.")
                self._limpiar_tablas()
                return

            issues = self._obtener_tickets_usuario(usuario_id)
        except (RequestException, ValueError) as exc:
            self._estado.setText(f"Error consultando Redmine: {exc}")
            self._limpiar_tablas()
            self._btn_buscar.setEnabled(True)
            return

        categorias = {
            "progreso": [],
            "pruebas": [],
            "rtd": [],
        }

        for issue in issues:
            estado = (issue.get("status", {}) or {}).get("name", "").lower()
            if "progreso" in estado:
                categorias["progreso"].append(issue)
            elif "prueba" in estado:
                categorias["pruebas"].append(issue)
            elif "rtd" in estado or "ready" in estado:
                categorias["rtd"].append(issue)

        for clave, items in categorias.items():
            tabla = self._tablas_por_estado[clave]["tabla"]
            tabla.setRowCount(len(items))
            for fila, issue in enumerate(items):
                valores = [
                    issue.get("id", ""),
                    (issue.get("project", {}) or {}).get("name", ""),
                    (issue.get("status", {}) or {}).get("name", ""),
                    (issue.get("priority", {}) or {}).get("name", ""),
                    issue.get("subject", ""),
                    issue.get("updated_on", ""),
                ]
                for columna, valor in enumerate(valores):
                    item = QTableWidgetItem(str(valor))
                    if self._COLUMNAS[columna] == "ID":
                        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    tabla.setItem(fila, columna, item)
            if not items:
                tabla.setRowCount(0)

        total = sum(len(items) for items in categorias.values())
        self._estado.setText(
            f"Usuario: {usuario_nombre} (ID {usuario_id}). Tickets analizados: {total}."
        )
        self._btn_buscar.setEnabled(True)

    def _limpiar_tablas(self):
        for tabla in self._tablas_por_estado.values():
            tabla["tabla"].setRowCount(0)

    def _resolver_usuario(self, identificador: str) -> Tuple[int | None, str | None]:
        usuario, clave = self._credentials
        if identificador.isdigit():
            url = REDMINE_USER_DETAIL_URL.format(user_id=identificador)
            respuesta = requests.get(
                url,
                auth=HTTPBasicAuth(usuario, clave),
                timeout=15,
                verify=False,
            )
            if respuesta.status_code == 404:
                return None, None
            respuesta.raise_for_status()
            data = respuesta.json().get("user", {})
            return data.get("id"), data.get("name") or data.get("login")

        respuesta = requests.get(
            REDMINE_USERS_URL,
            params={"name": identificador, "limit": 5},
            auth=HTTPBasicAuth(usuario, clave),
            timeout=15,
            verify=False,
        )
        respuesta.raise_for_status()
        usuarios = respuesta.json().get("users", []) or []
        if not usuarios:
            return None, None

        usuario_obj = None
        for candidato in usuarios:
            if candidato.get("login", "").lower() == identificador.lower():
                usuario_obj = candidato
                break
        if usuario_obj is None:
            usuario_obj = usuarios[0]

        return usuario_obj.get("id"), usuario_obj.get("name") or usuario_obj.get("login")

    def _obtener_tickets_usuario(self, usuario_id: int):
        usuario, clave = self._credentials
        respuesta = requests.get(
            REDMINE_ISSUES_SEARCH_URL,
            params={"assigned_to_id": usuario_id, "status_id": "*", "limit": 100},
            auth=HTTPBasicAuth(usuario, clave),
            timeout=15,
            verify=False,
        )
        respuesta.raise_for_status()
        return respuesta.json().get("issues", []) or []


# --- Ventana Principal ---
class VentanaPrincipal(QMainWindow):
    def __init__(self, credentials: Tuple[str, str]):
        super().__init__()
        self.setWindowTitle("Tickets de soporte")
        self.resize(1000, 650)
        self._credentials = credentials

        self.tabs = QTabWidget()
        self.tabs.addTab(VistaTicketsSoporte(self._credentials), "Tickets de soporte")
        self.tabs.addTab(VistaActividadUsuario(self._credentials), "Actividad usuario")
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
