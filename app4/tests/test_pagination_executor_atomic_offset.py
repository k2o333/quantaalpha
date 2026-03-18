import unittest

from app4.core.pagination_executor import PaginationExecutor


class PaginationExecutorAtomicOffsetTests(unittest.TestCase):
    def setUp(self):
        self.executor = PaginationExecutor()
        self.interface_config = {"name": "test_interface"}

    def test_commit_on_success_discards_partial_streamed_data_on_error(self):
        callbacks = []
        requests = []

        def make_request(_interface_config, params):
            requests.append((params["offset"], params["limit"]))
            if params["offset"] == 0:
                return [{"id": 1}, {"id": 2}]
            raise RuntimeError("boom")

        params = {
            "_offset_pagination": {
                "enabled": True,
                "limit": 2,
                "commit_on_success": True,
            }
        }

        with self.assertRaises(RuntimeError):
            self.executor._execute_single_request(
                self.interface_config,
                params,
                make_request,
                on_data_ready=callbacks.append,
            )

        self.assertEqual(requests, [(0, 2), (2, 2)])
        self.assertEqual(callbacks, [])

    def test_commit_on_success_aggregates_pages_before_single_callback(self):
        callbacks = []

        def make_request(_interface_config, params):
            if params["offset"] == 0:
                return [{"id": 1}, {"id": 2}]
            if params["offset"] == 2:
                return [{"id": 3}]
            return []

        params = {
            "_offset_pagination": {
                "enabled": True,
                "limit": 2,
                "commit_on_success": True,
            }
        }

        result = self.executor._execute_single_request(
            self.interface_config,
            params,
            make_request,
            on_data_ready=callbacks.append,
        )

        self.assertEqual(result, 3)
        self.assertEqual(callbacks, [[{"id": 1}, {"id": 2}, {"id": 3}]])

    def test_non_atomic_streaming_keeps_existing_page_by_page_behavior(self):
        callbacks = []

        def make_request(_interface_config, params):
            if params["offset"] == 0:
                return [{"id": 1}, {"id": 2}]
            raise RuntimeError("boom")

        params = {
            "_offset_pagination": {
                "enabled": True,
                "limit": 2,
                "commit_on_success": False,
            }
        }

        with self.assertRaises(RuntimeError):
            self.executor._execute_single_request(
                self.interface_config,
                params,
                make_request,
                on_data_ready=callbacks.append,
            )

        self.assertEqual(callbacks, [[{"id": 1}, {"id": 2}]])


if __name__ == "__main__":
    unittest.main()
