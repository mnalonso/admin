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
    QAbstractItemView,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
import sys
from typing import List, Tuple
from collections import defaultdict
from datetime import date, timedelta
import calendar

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
REDMINE_TIME_ENTRIES_URL = f"{REDMINE_BASE_URL}/time_entries.json"


def formatear_horas(valor: float) -> str:
    minutos_totales = int(round(valor * 60))
    horas = minutos_totales // 60
    minutos = minutos_totales % 60
    return f"{horas}:{minutos:02d}"


def calcular_rangos_meses():
    hoy = date.today()
    inicio_actual = hoy.replace(day=1)
    ultimo_dia_actual = calendar.monthrange(inicio_actual.year, inicio_actual.month)[1]
    fin_actual = inicio_actual.replace(day=ultimo_dia_actual)

    fin_anterior = inicio_actual - timedelta(days=1)
    inicio_anterior = fin_anterior.replace(day=1)
    ultimo_dia_anterior = calendar.monthrange(inicio_anterior.year, inicio_anterior.month)[1]
    fin_anterior = inicio_anterior.replace(day=ultimo_dia_anterior)

    return (inicio_anterior, fin_anterior), (inicio_actual, fin_actual)


def obtener_horas_por_dia(
    credentials: Tuple[str, str],
    usuario_id: int,
    fecha_desde: date,
    fecha_hasta: date,
):
    entradas = obtener_time_entries(credentials, usuario_id, fecha_desde, fecha_hasta)
    totales = defaultdict(float)
    for entrada in entradas:
        dia = entrada.get("spent_on")
        horas = entrada.get("hours", 0)
        if not dia:
            continue
        try:
            totales[dia] += float(horas or 0)
        except (TypeError, ValueError):
            continue

    dias = []
    actual = fecha_desde
    while actual <= fecha_hasta:
        clave = actual.isoformat()
        horas = totales.get(clave, 0.0)
        es_fin_de_semana = actual.weekday() >= 5
        dias.append((actual, horas, es_fin_de_semana))
        actual += timedelta(days=1)

    return dias


def resolver_usuario(credentials: Tuple[str, str], identificador: str) -> Tuple[int | None, str | None]:
    usuario, clave = credentials
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


def obtener_time_entries(
    credentials: Tuple[str, str],
    user_id: int,
    fecha_desde: date,
    fecha_hasta: date,
):
    usuario, clave = credentials
    entradas = []
    offset = 0
    limit = 100

    while True:
        respuesta = requests.get(
            REDMINE_TIME_ENTRIES_URL,
            params={
                "user_id": user_id,
                "from": fecha_desde.isoformat(),
                "to": fecha_hasta.isoformat(),
                "limit": limit,
                "offset": offset,
            },
            auth=HTTPBasicAuth(usuario, clave),
            timeout=15,
            verify=False,
        )
        respuesta.raise_for_status()
        data = respuesta.json() or {}
        lote = data.get("time_entries", []) or []
        entradas.extend(lote)

        total = data.get("total_count", len(entradas))
        offset += limit

        if offset >= total or not lote:
            break

    return entradas


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
            usuario_id, usuario_nombre = resolver_usuario(self._credentials, identificador)
            if usuario_id is None:
                self._estado.setText("No se encontró el usuario especificado.")
                self._limpiar_tablas()
                self._btn_buscar.setEnabled(True)
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

        estados_categorias = {
            2: "progreso",  # En progreso
            4: "pruebas",   # En pruebas
            3: "rtd",       # RTD
        }

        for issue in issues:
            status_info = issue.get("status") or {}
            estado_id = status_info.get("id")
            categoria = estados_categorias.get(estado_id)
            if categoria:
                categorias[categoria].append(issue)

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

    def _obtener_tickets_usuario(self, usuario_id: int):
        usuario, clave = self._credentials
        issues = []
        offset = 0
        limit = 100

        while True:
            respuesta = requests.get(
                REDMINE_ISSUES_SEARCH_URL,
                params={
                    "assigned_to_id": usuario_id,
                    "status_id": "*",
                    "limit": limit,
                    "offset": offset,
                },
                auth=HTTPBasicAuth(usuario, clave),
                timeout=15,
                verify=False,
            )
            respuesta.raise_for_status()
            data = respuesta.json() or {}
            lote = data.get("issues", []) or []
            issues.extend(lote)

            total = data.get("total_count", len(issues))
            offset += limit

            if offset >= total or not lote:
                break

        return issues


class HorasPanel(QWidget):
    def __init__(self, credentials: Tuple[str, str]):
        super().__init__()
        self._credentials = credentials
        layout = QVBoxLayout(self)

        self._tablas = {
            "actual": self._crear_tabla("Mes en curso"),
            "anterior": self._crear_tabla("Mes anterior"),
        }

        layout.addWidget(self._tablas["actual"]["contenedor"])
        layout.addWidget(self._tablas["anterior"]["contenedor"])

    def limpiar(self):
        for tabla in self._tablas.values():
            tabla_widget = tabla["tabla"]
            tabla_widget.clearContents()
            tabla_widget.setRowCount(0)
            tabla_widget.setColumnCount(0)
            tabla_widget.setHorizontalHeaderLabels([])

    def mostrar_para_usuario(self, usuario_id: int):
        rango_anterior, rango_actual = calcular_rangos_meses()
        horas_anterior = obtener_horas_por_dia(self._credentials, usuario_id, *rango_anterior)
        horas_actual = obtener_horas_por_dia(self._credentials, usuario_id, *rango_actual)

        self._cargar_tabla(self._tablas["anterior"]["tabla"], horas_anterior)
        self._cargar_tabla(self._tablas["actual"]["tabla"], horas_actual)

        total_anterior = sum(horas for _, horas, _ in horas_anterior)
        total_actual = sum(horas for _, horas, _ in horas_actual)

        return {
            "anterior_total": total_anterior,
            "anterior_dias": len(horas_anterior),
            "actual_total": total_actual,
            "actual_dias": len(horas_actual),
        }

    def _crear_tabla(self, titulo: str):
        contenedor = QWidget()
        contenedor_layout = QVBoxLayout(contenedor)
        contenedor_layout.setContentsMargins(0, 12, 0, 0)
        contenedor_layout.addWidget(QLabel(f"<b>{titulo}</b>"))
        tabla = QTableWidget(0, 0)
        tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        header = tabla.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setDefaultSectionSize(42)
        header.setMinimumSectionSize(28)
        tabla.verticalHeader().setVisible(True)
        contenedor_layout.addWidget(tabla)
        return {"contenedor": contenedor, "tabla": tabla}

    def _cargar_tabla(self, tabla: QTableWidget, datos):
        tabla.clearContents()
        tabla.setRowCount(0)
        tabla.setColumnCount(0)

        if not datos:
            tabla.setHorizontalHeaderLabels([])
            return

        tabla.setRowCount(1)
        tabla.setColumnCount(len(datos))
        encabezados = []
        for columna, (fecha, horas, es_fin_de_semana) in enumerate(datos):
            encabezados.append(str(fecha.day))
            item = QTableWidgetItem(f"{horas:.2f}")
            item.setTextAlignment(Qt.AlignCenter)
            if horas < 8 and not es_fin_de_semana:
                item.setBackground(QColor(255, 200, 200))
            elif es_fin_de_semana:
                item.setBackground(QColor(235, 235, 235))
            tabla.setItem(0, columna, item)

        tabla.setHorizontalHeaderLabels(encabezados)
        tabla.setVerticalHeaderLabels(["Horas"])


class VistaHorasCargadas(QWidget):
    def __init__(self, credentials: Tuple[str, str]):
        super().__init__()
        self._credentials = credentials

        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        header.addWidget(QLabel("<b>Horas cargadas</b>"))
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

        self._panel = HorasPanel(self._credentials)
        layout.addWidget(self._panel)

    def buscar_usuario(self):
        identificador = self._entrada_usuario.text().strip()
        if not identificador:
            QMessageBox.warning(self, "Dato requerido", "Ingresá un ID o usuario de Redmine.")
            return

        self._btn_buscar.setEnabled(False)
        self._estado.setText("Buscando horas cargadas…")
        QApplication.processEvents()

        try:
            usuario_id, usuario_nombre = resolver_usuario(self._credentials, identificador)
            if usuario_id is None:
                self._estado.setText("No se encontró el usuario especificado.")
                self._panel.limpiar()
                self._btn_buscar.setEnabled(True)
                return

            resumen = self._panel.mostrar_para_usuario(usuario_id)
        except (RequestException, ValueError) as exc:
            self._estado.setText(f"Error consultando Redmine: {exc}")
            self._panel.limpiar()
            self._btn_buscar.setEnabled(True)
            return

        nombre = usuario_nombre or identificador
        self._estado.setText(
            (
                f"Usuario: {nombre} (ID {usuario_id}). "
                f"Mes anterior: {resumen['anterior_total']:.2f} h en {resumen['anterior_dias']} días. "
                f"Mes en curso: {resumen['actual_total']:.2f} h en {resumen['actual_dias']} días."
            )
        )
        self._btn_buscar.setEnabled(True)


class VistaHorasTeam(QWidget):
    _USUARIOS = [
        "jarmentia",
        "pchero",
        "jpaez",
        "agroppa",
        "rmonte",
        "rgil",
        "lgaetan",
        "gsilva",
        "afontana",
    ]

    def __init__(self, credentials: Tuple[str, str]):
        super().__init__()
        self._credentials = credentials
        self._cache_usuarios: dict[str, Tuple[int, str | None]] = {}
        self._cargando = False

        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        header.addWidget(QLabel("<b>Horas team</b>"))
        header.addStretch()
        self._btn_actualizar = QPushButton("Actualizar")
        self._btn_actualizar.clicked.connect(self._consultar_todos)
        header.addWidget(self._btn_actualizar)
        layout.addLayout(header)

        self._estado = QLabel("Consultá las horas cargadas del equipo.")
        self._estado.setWordWrap(True)
        layout.addWidget(self._estado)

        self._tablas = {
            "actual": self._crear_tabla("Mes en curso"),
            "anterior": self._crear_tabla("Mes anterior"),
        }

        layout.addWidget(self._tablas["actual"]["contenedor"])
        layout.addWidget(self._tablas["anterior"]["contenedor"])

        if self._USUARIOS:
            self._consultar_todos()

    def _consultar_todos(self):
        if self._cargando:
            return

        self._establecer_cargando(True)
        self._estado.setText("Buscando horas cargadas del equipo…")
        QApplication.processEvents()

        for tabla in self._tablas.values():
            self._limpiar_tabla(tabla["tabla"])

        errores: list[str] = []
        usuarios_datos: list[dict] = []

        rango_anterior, rango_actual = calcular_rangos_meses()

        for login in self._USUARIOS:
            QApplication.processEvents()
            try:
                if login in self._cache_usuarios:
                    usuario_id, nombre_cache = self._cache_usuarios[login]
                else:
                    usuario_id, nombre_cache = resolver_usuario(self._credentials, login)
                    if usuario_id is None:
                        raise ValueError("No se encontró el usuario especificado en Redmine.")
                    self._cache_usuarios[login] = (usuario_id, nombre_cache)

                horas_anterior = obtener_horas_por_dia(
                    self._credentials, usuario_id, *rango_anterior
                )
                horas_actual = obtener_horas_por_dia(
                    self._credentials, usuario_id, *rango_actual
                )

            except (RequestException, ValueError) as exc:
                errores.append(f"{login}: {exc}")
                usuarios_datos.append(
                    {
                        "login": login,
                        "id": None,
                        "nombre": login,
                        "datos": None,
                    }
                )
            else:
                usuarios_datos.append(
                    {
                        "login": login,
                        "id": usuario_id,
                        "nombre": nombre_cache or login,
                        "datos": {
                            "anterior": horas_anterior,
                            "actual": horas_actual,
                        },
                    }
                )

        self._cargar_tabla_equipo(
            self._tablas["anterior"]["tabla"], usuarios_datos, rango_anterior, "anterior"
        )
        self._cargar_tabla_equipo(
            self._tablas["actual"]["tabla"], usuarios_datos, rango_actual, "actual"
        )

        if errores:
            self._estado.setText(
                "Actualizado con errores: " + "; ".join(errores)
            )
        else:
            self._estado.setText("Horas actualizadas para todo el equipo.")

        self._establecer_cargando(False)

    def _establecer_cargando(self, cargando: bool):
        self._cargando = cargando
        self._btn_actualizar.setEnabled(not cargando)

    def _crear_tabla(self, titulo: str):
        contenedor = QWidget()
        contenedor_layout = QVBoxLayout(contenedor)
        contenedor_layout.setContentsMargins(0, 12, 0, 0)
        contenedor_layout.addWidget(QLabel(f"<b>{titulo}</b>"))

        tabla = QTableWidget(0, 0)
        tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        tabla.setSelectionMode(QAbstractItemView.NoSelection)
        tabla.setSelectionBehavior(QAbstractItemView.SelectItems)
        tabla.verticalHeader().setVisible(False)
        tabla.horizontalHeader().setStretchLastSection(False)
        tabla.horizontalHeader().setSectionsMovable(False)

        contenedor_layout.addWidget(tabla)
        return {"contenedor": contenedor, "tabla": tabla}

    def _limpiar_tabla(self, tabla: QTableWidget):
        tabla.clearContents()
        tabla.setRowCount(0)
        tabla.setColumnCount(0)
        tabla.setHorizontalHeaderLabels([])

    def _cargar_tabla_equipo(
        self,
        tabla: QTableWidget,
        usuarios_datos: List[dict],
        rango: Tuple[date, date],
        clave: str,
    ):
        self._limpiar_tabla(tabla)

        inicio, fin = rango
        dias = []
        actual = inicio
        while actual <= fin:
            dias.append(actual)
            actual += timedelta(days=1)

        if not usuarios_datos or not dias:
            return

        filas = len(usuarios_datos) + 1
        columnas = len(dias) + 1
        tabla.setRowCount(filas)
        tabla.setColumnCount(columnas)

        encabezados = ["Usuario"] + [str(dia.day) for dia in dias]
        tabla.setHorizontalHeaderLabels(encabezados)

        header = tabla.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Fixed)
        header.setDefaultSectionSize(42)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)

        tabla.verticalHeader().setDefaultSectionSize(28)

        totales_por_dia = [0.0 for _ in dias]

        fuente_total = QFont()
        fuente_total.setBold(True)

        for fila, info in enumerate(usuarios_datos):
            nombre = info.get("nombre") or info.get("login")
            login = info.get("login")
            item_usuario = QTableWidgetItem(f"{nombre} ({login})")
            tabla.setItem(fila, 0, item_usuario)

            datos_usuario = info.get("datos")
            if not datos_usuario or clave not in datos_usuario:
                item_usuario.setForeground(QColor(200, 0, 0))
                continue

            horas_por_dia = {dato[0]: (dato[1], dato[2]) for dato in datos_usuario[clave]}

            for indice, dia in enumerate(dias, start=1):
                horas, es_fin = horas_por_dia.get(
                    dia, (0.0, dia.weekday() >= 5)
                )
                item = QTableWidgetItem(formatear_horas(horas))
                item.setTextAlignment(Qt.AlignCenter)
                if es_fin:
                    item.setBackground(QColor(235, 235, 235))
                elif horas < 8:
                    item.setBackground(QColor(255, 200, 200))
                tabla.setItem(fila, indice, item)
                totales_por_dia[indice - 1] += horas

        fila_total = filas - 1
        item_total = QTableWidgetItem("Total")
        item_total.setFont(fuente_total)
        tabla.setItem(fila_total, 0, item_total)

        for indice, dia in enumerate(dias, start=1):
            horas_totales = totales_por_dia[indice - 1]
            item = QTableWidgetItem(formatear_horas(horas_totales))
            item.setTextAlignment(Qt.AlignCenter)
            item.setFont(fuente_total)
            if dia.weekday() >= 5:
                item.setBackground(QColor(235, 235, 235))
            tabla.setItem(fila_total, indice, item)

        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        for columna in range(1, columnas):
            header.resizeSection(columna, 42)


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
        self.tabs.addTab(VistaHorasCargadas(self._credentials), "Horas cargadas")
        self.tabs.addTab(VistaHorasTeam(self._credentials), "Horas team")
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
