import unittest
from typing import Any, Dict, List

from ldap3 import LDAPSocketOpenError

from ldap_service import LDAPConfig, LDAPService, LdapSearchError


class DummyStandard:
    def __init__(self, responses: List[Dict[str, Any]]):
        self._responses = responses

    def paged_search(
        self,
        search_base: str,
        search_filter: str,
        search_scope: Any,
        attributes: Any,
        paged_size: int,
        generator: bool,
        time_limit: int,
    ):
        for entry in self._responses:
            yield {"attributes": entry}


class DummyExtend:
    def __init__(self, responses: List[Dict[str, Any]]):
        self.standard = DummyStandard(responses)


class DummyConnection:
    def __init__(self, responses: List[Dict[str, Any]]):
        self.extend = DummyExtend(responses)
        self.unbound = False

    def unbind(self):
        self.unbound = True


class DummyConnectionFactory:
    def __init__(self, responses: List[Dict[str, Any]]):
        self.responses = responses

    def __call__(self, config: LDAPConfig) -> DummyConnection:
        return DummyConnection(self.responses)


class LDAPServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.config = LDAPConfig(
            server_uri="ldap://test",
            base_dn="dc=example,dc=com",
            bind_dn="cn=readonly,dc=example,dc=com",
            bind_password="secret",
            timeout=5,
            page_size=2,
        )

    def test_employeeid_filter(self):
        connection_factory = DummyConnectionFactory(
            [{"employeeid": "123", "displayName": "Alice"}]
        )
        service = LDAPService(self.config, connection_factory=connection_factory)
        result = service.search({"legajo": "123"}, page=1, page_size=1)

        self.assertEqual(result["results"][0]["employeeid"], "123")
        self.assertEqual(result["filter"], "(employeeid=123)")

    def test_combined_filters(self):
        responses = [
            {"employeeid": "123", "displayName": "Alice", "mail": "alice@test"},
            {"employeeid": "456", "displayName": "Alicia", "mail": "alicia@test"},
        ]
        service = LDAPService(self.config, connection_factory=DummyConnectionFactory(responses))
        result = service.search(
            {
                "legajo": "123",
                "id": "abcde",
                "nombre": "Ali",
                "email": "alice@test",
                "samaccountname": "alice",
            },
            page=1,
            page_size=10,
            app_user="tester",
        )

        expected_filter = "(&(employeeid=123)(msds-externaldirectoryobjectid=User_abcde)(|(cn=*Ali*)(displayName=*Ali*))(|(mail=alice@test)(mail=*alice@test*))(samaccountname=alice))"
        self.assertEqual(result["filter"], expected_filter)
        self.assertEqual(result["total"], 2)

    def test_reject_empty_filters(self):
        service = LDAPService(self.config, connection_factory=DummyConnectionFactory([]))
        with self.assertRaises(ValueError):
            service.search({})

    def test_invalid_format_legajo(self):
        service = LDAPService(self.config, connection_factory=DummyConnectionFactory([]))
        with self.assertRaises(ValueError):
            service.search({"legajo": "abc"})

    def test_timeout_error(self):
        def failing_factory(config: LDAPConfig):
            raise LDAPSocketOpenError("timeout")

        service = LDAPService(self.config, connection_factory=failing_factory)
        with self.assertRaises(LdapSearchError):
            service.search({"legajo": "123"})

    def test_pagination_slice(self):
        responses = [
            {"employeeid": "1"},
            {"employeeid": "2"},
            {"employeeid": "3"},
        ]
        service = LDAPService(self.config, connection_factory=DummyConnectionFactory(responses))
        result = service.search({"legajo": "1"}, page=2, page_size=1)
        self.assertEqual(len(result["results"]), 1)
        self.assertEqual(result["results"][0]["employeeid"], "2")


if __name__ == "__main__":
    unittest.main()
