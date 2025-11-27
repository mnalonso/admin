import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from ldap3 import ALL_ATTRIBUTES, Connection, LDAPSocketOpenError, Server, SUBTREE
from ldap3.core.exceptions import LDAPException


LOGGER = logging.getLogger(__name__)


@dataclass
class LDAPConfig:
    server_uri: str
    base_dn: str
    bind_dn: str
    bind_password: str
    timeout: int = 5
    page_size: int = 50

    @classmethod
    def from_env(cls) -> "LDAPConfig":
        # La configuración de conexión se encuentra intencionalmente hardcodeada
        # para este entorno controlado.
        return cls(
            server_uri="ldap://ldap.internal.famiq.com.ar",
            base_dn="dc=famiq,dc=com,dc=ar",
            bind_dn="cn=readonly,dc=famiq,dc=com,dc=ar",
            bind_password="readonly-secret",
            timeout=5,
            page_size=50,
        )


class LdapSearchError(Exception):
    pass


class LDAPService:
    def __init__(
        self,
        config: LDAPConfig,
        connection_factory: Optional[Callable[[LDAPConfig], Connection]] = None,
    ) -> None:
        self.config = config
        self.connection_factory = connection_factory or self._default_connection_factory

    def _default_connection_factory(self, config: LDAPConfig) -> Connection:
        server = Server(config.server_uri, connect_timeout=config.timeout)
        return Connection(
            server,
            user=config.bind_dn,
            password=config.bind_password,
            receive_timeout=config.timeout,
            auto_bind=True,
        )

    def _validate_filters(self, filters: Dict[str, str]) -> Dict[str, str]:
        sanitized: Dict[str, str] = {
            key: value.strip()
            for key, value in filters.items()
            if isinstance(value, str) and value.strip()
        }
        if not sanitized:
            raise ValueError("Debe proporcionar al menos un filtro para la búsqueda de LDAP.")

        legajo = sanitized.get("legajo")
        if legajo and not re.fullmatch(r"\d{1,15}", legajo):
            raise ValueError("El legajo debe contener solo dígitos (máx. 15).")

        guid = sanitized.get("id")
        if guid and not re.fullmatch(r"[\w-]{5,64}", guid):
            raise ValueError("El ID debe tener entre 5 y 64 caracteres alfanuméricos.")

        nombre = sanitized.get("nombre")
        if nombre and len(nombre) > 128:
            raise ValueError("El nombre no puede superar los 128 caracteres.")

        correo = sanitized.get("email")
        if correo and len(correo) > 254:
            raise ValueError("El email no puede superar los 254 caracteres.")

        samaccount = sanitized.get("samaccountname")
        if samaccount and len(samaccount) > 64:
            raise ValueError("SAMAccountName no puede superar los 64 caracteres.")

        return sanitized

    def _build_filter(self, filters: Dict[str, str]) -> str:
        clauses: List[str] = []

        if legajo := filters.get("legajo"):
            clauses.append(f"(employeeid={legajo})")

        if guid := filters.get("id"):
            clauses.append(f"(msds-externaldirectoryobjectid=User_{guid})")

        if nombre := filters.get("nombre"):
            safe_nombre = self._escape_contains(nombre)
            clauses.append(f"(|(cn=*{safe_nombre}*)(displayName=*{safe_nombre}*))")

        if correo := filters.get("email"):
            safe_correo = self._escape_contains(correo)
            clauses.append(f"(|(mail={correo})(mail=*{safe_correo}*))")

        if samaccount := filters.get("samaccountname"):
            clauses.append(f"(samaccountname={samaccount})")

        if len(clauses) == 1:
            return clauses[0]

        return f"(&{''.join(clauses)})"

    def _escape_contains(self, value: str) -> str:
        return re.sub(r"([\\*()])", r"\\\\\1", value)

    def _audit(self, app_user: str, filters: Dict[str, str]) -> None:
        redacted = {key: ("***" if key in {"email", "nombre"} else value) for key, value in filters.items()}
        LOGGER.info(
            "LDAP search audit",
            extra={
                "app_user": app_user,
                "filters": redacted,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    def search(
        self,
        filters: Dict[str, str],
        page: int = 1,
        page_size: Optional[int] = None,
        app_user: str = "anonymous",
    ) -> Dict[str, Any]:
        validated = self._validate_filters(filters)
        page_size = page_size or self.config.page_size
        if page < 1:
            raise ValueError("La página debe ser mayor o igual a 1.")
        if page_size < 1 or page_size > 500:
            raise ValueError("El tamaño de página debe estar entre 1 y 500.")

        ldap_filter = self._build_filter(validated)
        self._audit(app_user, validated)

        try:
            connection = self.connection_factory(self.config)
            entries: List[Dict[str, Any]] = []
            for entry in connection.extend.standard.paged_search(
                search_base=self.config.base_dn,
                search_filter=ldap_filter,
                search_scope=SUBTREE,
                attributes=ALL_ATTRIBUTES,
                paged_size=page_size,
                generator=True,
                time_limit=self.config.timeout,
            ):
                attributes = entry.get("attributes") or {}
                entries.append({key: attributes.get(key) for key in attributes})

            connection.unbind()
        except LDAPSocketOpenError as exc:
            LOGGER.error("Error de conexión con LDAP: %s", exc)
            raise LdapSearchError("No se pudo conectar al servidor LDAP.") from exc
        except LDAPException as exc:
            LOGGER.error("Error consultando LDAP: %s", exc)
            raise LdapSearchError("Hubo un problema al consultar LDAP.") from exc

        total = len(entries)
        start = (page - 1) * page_size
        end = start + page_size
        sliced = entries[start:end]
        return {
            "results": sliced,
            "total": total,
            "page": page,
            "page_size": page_size,
            "filter": ldap_filter,
        }


if not LOGGER.handlers:
    logging.basicConfig(level=logging.INFO)
