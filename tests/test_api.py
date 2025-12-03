import unittest
from unittest.mock import MagicMock, patch

from api import app, ldap_service


class ApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.client = app.test_client()

    @patch("api.ldap_service")
    def test_reject_empty_filters(self, mock_service):
        mock_service.search.side_effect = ValueError("Debe proporcionar filtros")
        response = self.client.get("/ldap/search")
        self.assertEqual(response.status_code, 400)
        self.assertIn("filtros", response.get_json()["error"])

    @patch("api.ldap_service")
    def test_successful_search(self, mock_service):
        mock_service.search.return_value = {
            "results": [{"employeeid": "123", "displayName": "Alice"}],
            "total": 1,
            "page": 1,
            "page_size": 25,
        }
        response = self.client.get(
            "/ldap/search",
            query_string={"legajo": "123", "page": 1},
            headers={"X-App-User": "tester"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["total"], 1)
        mock_service.search.assert_called_once()

    @patch("api.ldap_service")
    def test_connection_error(self, mock_service):
        mock_service.search.side_effect = Exception("boom")
        response = self.client.get("/ldap/search", query_string={"legajo": "123"})
        self.assertEqual(response.status_code, 500)
        self.assertIn("error", response.get_json())


if __name__ == "__main__":
    unittest.main()
