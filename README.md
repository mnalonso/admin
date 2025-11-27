# Admin LDAP y Directorio AD

Este proyecto incluye una pequeña aplicación de escritorio (PySide6) y un servicio interno para consultar el Directorio Activo a través de un endpoint HTTP.

## Configuración de entorno

Las credenciales y parámetros de LDAP se leen desde variables de entorno para evitar hardcodear datos sensibles:

- `LDAP_SERVER_URI`: URL del servidor LDAP (ej. `ldap://ldap.example.com`).
- `LDAP_BASE_DN`: Base DN desde donde se realizará la búsqueda.
- `LDAP_BIND_DN`: Usuario de solo lectura para el bind.
- `LDAP_BIND_PASSWORD`: Contraseña del bind de solo lectura.
- `LDAP_TIMEOUT`: Tiempo máximo en segundos para respuestas LDAP (por defecto 5).
- `LDAP_PAGE_SIZE`: Tamaño de página para la paginación del servicio.
- `DIRECTORIO_API_URL`: URL del endpoint `/ldap/search` que consume la pestaña de frontend (por defecto `http://localhost:8000/ldap/search`).

## Uso del endpoint

1. Levantá el servicio (por ejemplo `python api.py`).
2. Realizá una petición `GET` a `/ldap/search` con uno o varios filtros: `legajo`, `id`, `nombre`, `email`, `samaccountname`.
3. Parámetros opcionales: `page` y `page_size`.
4. El servicio rechaza consultas vacías y valida formatos básicos antes de consultar LDAP.

## Pestaña "Directorio AD"

En la aplicación de escritorio encontrarás una pestaña "Directorio AD" con un formulario de búsqueda y una tabla paginada. Al presionar **Buscar** se llamará al endpoint configurado en `DIRECTORIO_API_URL` y se mostrarán los resultados devueltos por el servicio.
