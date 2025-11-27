import logging
from typing import Dict

from flask import Flask, jsonify, request

from ldap_service import LDAPConfig, LDAPService, LdapSearchError

app = Flask(__name__)
app.logger.setLevel(logging.INFO)

ldap_service = LDAPService(LDAPConfig.from_env())


@app.route("/ldap/search", methods=["GET"])
def ldap_search():
    filtros: Dict[str, str] = {
        "legajo": request.args.get("legajo", ""),
        "id": request.args.get("id", ""),
        "nombre": request.args.get("nombre", ""),
        "email": request.args.get("email", ""),
        "samaccountname": request.args.get("samaccountname", ""),
    }
    app_user = request.headers.get("X-App-User", "anonymous")

    try:
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", ldap_service.config.page_size))
        resultados = ldap_service.search(
            filtros, page=page, page_size=page_size, app_user=app_user
        )
        return jsonify(resultados)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except LdapSearchError as exc:
        return jsonify({"error": str(exc)}), 502
    except Exception as exc:  # pragma: no cover
        app.logger.exception("Error inesperado en /ldap/search: %s", exc)
        return jsonify({"error": "Error interno en el servidor"}), 500


if __name__ == "__main__":  # pragma: no cover
    app.run(host="0.0.0.0", port=8000, debug=False)
