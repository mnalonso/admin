import json
import os
import sys
import time
from pathlib import Path

from openai import OpenAI
from PySide6.QtCore import QObject, Qt, Signal, QThread
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
    solicitar_procesamiento = Signal(dict, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._nombre_archivo = QLabel("Ningún archivo seleccionado")
        self._nombre_archivo.setWordWrap(True)

        self._btn_cargar = QPushButton("Cargar JSON…")
        self._btn_cargar.clicked.connect(self._abrir_dialogo_archivo)

        self._texto_crudo = QPlainTextEdit()
        self._texto_crudo.setPlaceholderText("Contenido original del archivo JSON")
        self._texto_crudo.setReadOnly(True)

        self._btn_procesar = QPushButton("Procesar")
        self._btn_procesar.setEnabled(False)
        self._btn_procesar.clicked.connect(self._emitir_procesamiento)

        self._json_data: dict | None = None
        self._contenido_original: str | None = None
        self._procesando = False

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Entrada</b>"))
        layout.addWidget(self._nombre_archivo)
        layout.addWidget(self._btn_cargar)
        layout.addWidget(self._texto_crudo, stretch=1)
        layout.addWidget(self._btn_procesar)

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
        self._json_data = data
        self._contenido_original = contenido
        self._actualizar_estado_boton()
        self.json_cargado.emit(data, contenido)

    def _emitir_procesamiento(self) -> None:
        if self._json_data is None or self._contenido_original is None:
            return
        self.solicitar_procesamiento.emit(self._json_data, self._contenido_original)

    def establecer_estado_procesamiento(self, procesando: bool) -> None:
        self._procesando = procesando
        self._actualizar_estado_boton()

    def _actualizar_estado_boton(self) -> None:
        hay_json = self._json_data is not None and self._contenido_original is not None
        self._btn_procesar.setEnabled(hay_json and not self._procesando)


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

    def mostrar_texto(self, contenido: str) -> None:
        self._texto.setPlainText(contenido)


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


class GPTWorker(QObject):
    """Ejecuta la invocación al asistente de forma aislada en un hilo."""

    finished = Signal()
    success = Signal(str)
    failure = Signal(str)

    def __init__(self, prompt: str, api_key: str, assistant_id: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._prompt = prompt
        self._api_key = api_key
        self._assistant_id = assistant_id

    def run(self) -> None:
        try:
            client = OpenAI(api_key=self._api_key)
            thread = client.beta.threads.create()
            client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=self._prompt,
            )

            run = client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=self._assistant_id,
            )

            max_attempts = 30
            attempts = 0
            while attempts < max_attempts:
                run = client.beta.threads.runs.retrieve(
                    thread_id=thread.id,
                    run_id=run.id,
                )
                status = getattr(run, "status", "")
                if status == "completed":
                    break
                if status in {"failed", "cancelled", "expired"}:
                    raise RuntimeError(f"El asistente finalizó con estado: {status}")
                attempts += 1
                time.sleep(1)
            else:
                raise TimeoutError("El asistente no respondió a tiempo.")

            messages = client.beta.threads.messages.list(thread_id=thread.id)
            respuesta = None
            for message in getattr(messages, "data", []):
                if getattr(message, "role", "") != "assistant":
                    continue
                partes: list[str] = []
                for item in getattr(message, "content", []):
                    item_type = getattr(item, "type", "")
                    if item_type != "text":
                        continue
                    texto = getattr(getattr(item, "text", None), "value", "")
                    if texto:
                        partes.append(texto)
                if partes:
                    respuesta = "\n".join(partes).strip()
                    if respuesta:
                        break

            if not respuesta:
                raise RuntimeError("No se obtuvo una respuesta válida del asistente.")

            self.success.emit(respuesta)
        except Exception as exc:  # noqa: BLE001
            self.failure.emit(str(exc))
        finally:
            self.finished.emit()


class VentanaPrincipal(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Procesador de JSON")
        self.resize(1200, 700)

        self._panel_carga = PanelCargaJSON(self)
        self._panel_procesado = PanelJSONProcesado(self)
        panel_vacio = PanelVacio(self)

        self._panel_carga.json_cargado.connect(self._panel_procesado.actualizar_json)
        self._panel_carga.solicitar_procesamiento.connect(self._procesar_json)

        self._worker_thread: QThread | None = None
        self._worker: GPTWorker | None = None

        contenedor = QSplitter(Qt.Horizontal)
        contenedor.addWidget(self._panel_carga)
        contenedor.addWidget(self._panel_procesado)
        contenedor.addWidget(panel_vacio)
        contenedor.setStretchFactor(0, 1)
        contenedor.setStretchFactor(1, 1)
        contenedor.setStretchFactor(2, 1)

        self.setCentralWidget(contenedor)

    def _procesar_json(self, _data: dict, contenido_original: str) -> None:
        if self._worker_thread is not None:
            QMessageBox.information(
                self,
                "Procesamiento en curso",
                "Ya hay un procesamiento en ejecución, por favor espere a que finalice.",
            )
            return

        api_key = os.environ.get("OPENAI_API_KEY")
        assistant_id = os.environ.get("OPENAI_ASSISTANT_ID")

        if not api_key or not assistant_id:
            QMessageBox.critical(
                self,
                "Configuración faltante",
                "Debe definir las variables de entorno OPENAI_API_KEY y OPENAI_ASSISTANT_ID.",
            )
            return

        self._panel_carga.establecer_estado_procesamiento(True)
        self._panel_procesado.mostrar_texto("Procesando JSON con el asistente…")

        self._worker_thread = QThread(self)
        self._worker = GPTWorker(contenido_original, api_key, assistant_id)
        self._worker.moveToThread(self._worker_thread)

        self._worker_thread.started.connect(self._worker.run)
        self._worker.success.connect(self._panel_procesado.mostrar_texto)
        self._worker.failure.connect(self._mostrar_error_procesamiento)
        self._worker.finished.connect(self._finalizar_procesamiento)
        self._worker.finished.connect(self._worker_thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker_thread.finished.connect(self._limpiar_hilo)
        self._worker_thread.finished.connect(self._worker_thread.deleteLater)

        self._worker_thread.start()

    def _mostrar_error_procesamiento(self, mensaje: str) -> None:
        self._panel_procesado.mostrar_texto("No se pudo procesar el JSON.")
        QMessageBox.critical(
            self,
            "Error al procesar",
            f"No se pudo obtener una respuesta del asistente:\n{mensaje}",
        )

    def _finalizar_procesamiento(self) -> None:
        self._panel_carga.establecer_estado_procesamiento(False)

    def _limpiar_hilo(self) -> None:
        self._worker_thread = None
        self._worker = None


def main() -> int:
    app = QApplication(sys.argv)
    ventana = VentanaPrincipal()
    ventana.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
