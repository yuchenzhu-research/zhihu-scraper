import unittest
from pathlib import Path

from cli.save_contracts import SaveRunResult
from cli.save_pipeline import SavePipelineSettings
from cli.workflow_contracts import BatchWorkflowResult, UrlTaskResult
from cli.workflow_service import ArchiveWorkflowService, WorkflowServiceConfig


class WorkflowContractTests(unittest.TestCase):
    def test_batch_workflow_result_aggregates_counts(self):
        result = BatchWorkflowResult(
            items=(
                UrlTaskResult(url="u1", success=True),
                UrlTaskResult(url="u2", success=False, error="boom"),
            )
        )
        self.assertEqual(result.total_count, 2)
        self.assertEqual(result.success_count, 1)
        self.assertEqual(result.failed_count, 1)
        self.assertTrue(result.has_failures)


class WorkflowServiceTests(unittest.IsolatedAsyncioTestCase):
    def _make_service(self, **kwargs):
        return ArchiveWorkflowService(
            WorkflowServiceConfig(
                save_settings=SavePipelineSettings(
                    folder_template="[{date}] {title}",
                    images_subdir="images",
                    image_concurrency=4,
                    image_timeout=30,
                ),
                printer=lambda *_args, **_kwargs: None,
                logger=None,
            ),
            **kwargs,
        )

    async def test_run_fetch_urls_builds_question_scrape_config(self):
        captured = []

        async def fake_fetch_runner(**kwargs):
            captured.append(kwargs)
            return SaveRunResult(source_url=kwargs["url"], content_root=Path("data/entries"), records=())

        service = self._make_service(fetch_runner=fake_fetch_runner)
        await service.run_fetch_urls(
            urls=["https://www.zhihu.com/question/123"],
            output_dir=Path("data"),
            limit=5,
            download_images=False,
            headless=True,
        )

        self.assertEqual(captured[0]["scrape_config"], {"start": 0, "limit": 5})

    async def test_run_monitor_only_advances_pointer_when_all_success(self):
        class FakeMonitor:
            def __init__(self, data_dir):
                self.data_dir = data_dir
                self.marked = None

            def get_new_items(self, collection_id):
                return (
                    [
                        {"url": "https://www.zhihu.com/question/1/answer/2"},
                        {"url": "https://zhuanlan.zhihu.com/p/3"},
                    ],
                    "latest-id",
                )

            def mark_updated(self, collection_id, new_last_id):
                self.marked = (collection_id, new_last_id)

        monitor = FakeMonitor("data")

        async def fake_fetch_runner(**kwargs):
            return SaveRunResult(source_url=kwargs["url"], content_root=Path("data/entries"), records=())

        async def no_sleep(_delay: float):
            return None

        service = self._make_service(
            fetch_runner=fake_fetch_runner,
            monitor_factory=lambda data_dir: monitor,
            sleep=no_sleep,
        )
        result = await service.run_monitor(
            collection_id="78170682",
            output_dir=Path("data"),
            concurrency=4,
            download_images=False,
            headless=True,
        )

        self.assertEqual(result.discovered_count, 2)
        self.assertTrue(result.pointer_advanced)
        self.assertEqual(monitor.marked, ("78170682", "latest-id"))

    async def test_run_single_fetch_returns_failure_result_without_raising(self):
        async def broken_fetch_runner(**_kwargs):
            raise RuntimeError("boom")

        service = self._make_service(fetch_runner=broken_fetch_runner, error_handler=lambda *_args, **_kwargs: None)
        result = await service.run_single_fetch(
            url="https://www.zhihu.com/question/1/answer/2",
            output_dir=Path("data"),
            scrape_config={},
            download_images=False,
            headless=True,
        )

        self.assertFalse(result.success)
        self.assertIn("boom", result.error)


if __name__ == "__main__":
    unittest.main()
