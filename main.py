import json
import sys
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)


class PanelCargaJSON(QWidget):
    """Panel izquierdo encargado de cargar y mostrar un JSON sin procesar."""

    json_cargado = Signal(dict, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._nombre_archivo = QLabel("Ningún archivo seleccionado")
        self._nombre_archivo.setWordWrap(True)

        self._btn_cargar = QPushButton("Cargar JSON…")
        self._btn_cargar.clicked.connect(self._abrir_dialogo_archivo)

        self._texto_crudo = QPlainTextEdit()
        self._texto_crudo.setPlaceholderText("Contenido original del archivo JSON")
        self._texto_crudo.setReadOnly(True)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Entrada</b>"))
        layout.addWidget(self._nombre_archivo)
        layout.addWidget(self._btn_cargar)
        layout.addWidget(self._texto_crudo, stretch=1)

    def _abrir_dialogo_archivo(self) -> None:
        ruta, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar archivo JSON",
            "",
            "Archivos JSON (*.json);;Todos los archivos (*.*)",
        )
        if not ruta:
            return

        try:
            contenido = Path(ruta).read_text(encoding="utf-8")
            data = json.loads(contenido)
        except (OSError, json.JSONDecodeError) as exc:
            QMessageBox.critical(self, "Error", f"No se pudo cargar el JSON:\n{exc}")
            return

        self._nombre_archivo.setText(ruta)
        self._texto_crudo.setPlainText(contenido)
        self.json_cargado.emit(data, contenido)


class PanelJSONProcesado(QWidget):
    """Panel central para mostrar el JSON transformado."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._texto = QPlainTextEdit()
        self._texto.setPlaceholderText("Aquí se mostrará el JSON procesado")
        self._texto.setReadOnly(True)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>JSON procesado</b>"))
        layout.addWidget(self._texto, stretch=1)

    def actualizar_json(self, data: dict, _contenido_original: str) -> None:
        try:
            procesado = json.dumps(data, indent=4, ensure_ascii=False)
        except (TypeError, ValueError):
            procesado = "No fue posible transformar el contenido en JSON legible."
        self._texto.setPlainText(procesado)


class PanelVacio(QWidget):
    """Panel derecho sin contenido por el momento."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        mensaje = QLabel("<b>Panel libre</b><br>Sin contenido por ahora.")
        mensaje.setAlignment(Qt.AlignCenter)
        mensaje.setWordWrap(True)
        layout.addWidget(mensaje, alignment=Qt.AlignCenter)
        layout.addStretch()


class VentanaPrincipal(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Procesador de JSON")
        self.resize(1200, 700)

        panel_carga = PanelCargaJSON(self)
        panel_procesado = PanelJSONProcesado(self)
        panel_vacio = PanelVacio(self)

        panel_carga.json_cargado.connect(panel_procesado.actualizar_json)

        contenedor = QSplitter(Qt.Horizontal)
        contenedor.addWidget(panel_carga)
        contenedor.addWidget(panel_procesado)
        contenedor.addWidget(panel_vacio)
        contenedor.setStretchFactor(0, 1)
        contenedor.setStretchFactor(1, 1)
        contenedor.setStretchFactor(2, 1)

        self.setCentralWidget(contenedor)


def main() -> int:
    app = QApplication(sys.argv)
    ventana = VentanaPrincipal()
    ventana.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
