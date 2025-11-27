# Admin LDAP y Directorio AD

Este proyecto incluye una pequeña aplicación de escritorio (PySide6) y un servicio interno para consultar el Directorio Activo a través de un endpoint HTTP.

## Configuración de conexión

Para este entorno la configuración de LDAP se encuentra hardcodeada en `ldap_service.LDAPConfig.from_env` con los siguientes valores de ejemplo:

- `LDAP_SERVER_URI`: `ldap://ldap.internal.famiq.com.ar`.
- `LDAP_BASE_DN`: `dc=famiq,dc=com,dc=ar`.
- `LDAP_BIND_DN`: `cn=readonly,dc=famiq,dc=com,dc=ar`.
- `LDAP_BIND_PASSWORD`: `readonly-secret`.
- `LDAP_TIMEOUT`: `5`.
- `LDAP_PAGE_SIZE`: `50`.

La pestaña de frontend sigue leyendo `DIRECTORIO_API_URL` desde el entorno (por defecto `http://localhost:8000/ldap/search`).

## Uso del endpoint

1. Levantá el servicio (por ejemplo `python api.py`).
2. Realizá una petición `GET` a `/ldap/search` con uno o varios filtros: `legajo`, `id`, `nombre`, `email`, `samaccountname`.
3. Parámetros opcionales: `page` y `page_size`.
4. El servicio rechaza consultas vacías y valida formatos básicos antes de consultar LDAP.

## Pestaña "Directorio AD"

En la aplicación de escritorio encontrarás una pestaña "Directorio AD" con un formulario de búsqueda y una tabla paginada. Al presionar **Buscar** se llamará al endpoint configurado en `DIRECTORIO_API_URL` y se mostrarán los resultados devueltos por el servicio.
