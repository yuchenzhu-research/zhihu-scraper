import unittest
import sys

try:
    from textual.widgets import Static
    from cli.tui.app import ZhihuInteractiveShell
    from cli.tui.state import (
        ExecutionRecord,
        ExecutionReport,
        apply_question_limit,
        build_detail_snapshot,
        build_history_snapshot,
        build_retry_draft,
        build_running_summary,
        parse_input_to_draft,
    )
    from cli.tui.widgets import ArchiveInput, DetailCard, HistoryCard, QueueCard, StatusPill, SummaryCard
    from core.i18n import set_language
    HAS_TEXTUAL = True
except ImportError:
    HAS_TEXTUAL = False


def _mixed_executor(draft, progress_callback=None):
    if progress_callback is not None:
        progress_callback(
            build_running_summary(
                draft,
                current_index=1,
                total=len(draft.targets),
                output_dir="data",
                phase="模拟执行",
            )
        )
    return ExecutionReport(
        output_dir="data",
        records=(
            ExecutionRecord(
                target=draft.targets[0],
                saved_count=1,
                markdown_paths=("data/entries/answer/index.md",),
            ),
            ExecutionRecord(
                target=draft.targets[1],
                saved_count=0,
                markdown_paths=(),
                error="503",
                log_tail=("warmup", "retry failed"),
            ),
        ),
    )


@unittest.skipIf(not HAS_TEXTUAL, "textual dependency not installed")
class TuiStateTests(unittest.TestCase):
    def setUp(self):
        set_language("zh")

    def test_question_draft_requires_limit_then_becomes_runnable(self):
        draft = parse_input_to_draft("https://www.zhihu.com/question/123", True)
        self.assertTrue(draft.requires_question_limit)
        resolved = apply_question_limit(draft, 20, "Top 20 预设")
        self.assertTrue(resolved.ready_to_run)
        self.assertIn("Top 20", resolved.lines[0])

    def test_retry_draft_comes_from_failed_records_only(self):
        draft = parse_input_to_draft(
            "https://www.zhihu.com/question/123/answer/456 https://zhuanlan.zhihu.com/p/789",
            True,
        )
        report = ExecutionReport(
            output_dir="data",
            records=(
                ExecutionRecord(target=draft.targets[0], saved_count=1, markdown_paths=("data/entries/a/index.md",)),
                ExecutionRecord(
                    target=draft.targets[1],
                    saved_count=0,
                    markdown_paths=(),
                    error="503",
                    log_tail=("retry failed",),
                ),
            ),
        )
        retry_draft = build_retry_draft(report)
        self.assertIsNotNone(retry_draft)
        assert retry_draft is not None
        self.assertEqual(len(retry_draft.targets), 1)
        self.assertEqual(retry_draft.targets[0].url_type, "article")

    def test_multiline_paste_extracts_answer_url(self):
        draft = parse_input_to_draft(
            "你对下一代Transformer架构的预测是什么？ - 第欧根尼的回答 - 知乎\n"
            "https://www.zhihu.com/question/1904728228213548260/answer/2018626185983215533",
            True,
        )
        self.assertTrue(draft.ready_to_run)
        self.assertEqual(len(draft.targets), 1)
        self.assertEqual(draft.targets[0].url_type, "answer")

    def test_history_snapshot_contains_failure_hint(self):
        draft = parse_input_to_draft("https://zhuanlan.zhihu.com/p/789", True)
        report = ExecutionReport(
            output_dir="data",
            records=(
                ExecutionRecord(
                    target=draft.targets[0],
                    saved_count=0,
                    markdown_paths=(),
                    error="403",
                    log_tail=("blocked",),
                ),
            ),
        )
        history = build_history_snapshot((report,))
        self.assertEqual(history.tone, "warn")
        self.assertTrue(any("Ctrl+Y" in line for line in history.lines))

    def test_detail_snapshot_contains_log_tail(self):
        draft = parse_input_to_draft("https://zhuanlan.zhihu.com/p/789", True)
        report = ExecutionReport(
            output_dir="data",
            records=(
                ExecutionRecord(
                    target=draft.targets[0],
                    saved_count=0,
                    markdown_paths=(),
                    error="403",
                    log_tail=("warmup", "blocked"),
                ),
            ),
        )
        detail = build_detail_snapshot(draft, (report,))
        self.assertEqual(detail.title, "执行详情")
        self.assertTrue(any("blocked" in line for line in detail.lines))

    def test_status_pill_renders_a_group(self):
        pill = StatusPill("Cookie", "已就绪", "success")
        self.assertEqual(type(pill.render()).__name__, "Group")

    def test_execution_snapshots_include_translation_feedback(self):
        draft = parse_input_to_draft("https://zhuanlan.zhihu.com/p/789", True)
        report = ExecutionReport(
            output_dir="data",
            records=(
                ExecutionRecord(
                    target=draft.targets[0],
                    saved_count=1,
                    markdown_paths=("data/entries/article/index.md",),
                    translated_paths=("data/entries/article/[EN] index.md",),
                    notes=("翻译配置初始化失败：missing key",),
                ),
            ),
        )

        summary = build_detail_snapshot(draft, (report,))
        history = build_history_snapshot((report,))
        self.assertTrue(any("[EN] index.md" in line for line in summary.lines))
        self.assertTrue(any("missing key" in line for line in summary.lines))
        self.assertTrue(any("翻译文件：1 个" in line for line in history.lines))

    def test_language_switch_binding_is_registered(self):
        bindings = {binding[0]: binding[1] for binding in ZhihuInteractiveShell.BINDINGS}
        self.assertEqual(bindings["ctrl+g"], "change_language")


@unittest.skipIf(not HAS_TEXTUAL, "textual dependency not installed")
class TuiWorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def test_recent_results_and_retry_flow(self):
        app = ZhihuInteractiveShell(draft_executor=_mixed_executor)
        async with app.run_test(size=(100, 34)) as pilot:
            await pilot.pause()

            await pilot.press("ctrl+y")
            await pilot.pause()
            self.assertEqual(
                app.query_one(SummaryCard).query_one(".card-title", Static).content,
                "还没有可重试的结果",
            )

            app.query_one("#url-input", ArchiveInput).load_text(
                "https://www.zhihu.com/question/123/answer/456 "
                "https://zhuanlan.zhihu.com/p/789"
            )
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("ctrl+r")
            await pilot.pause()
            await pilot.pause()

            summary_body = app.query_one(SummaryCard).query_one(".card-body", Static).content
            history_body = app.query_one(HistoryCard).query_one(".card-body", Static).content
            detail_body = app.query_one(DetailCard).query_one(".card-body", Static).content
            self.assertIn("失败 1 个", summary_body)
            self.assertIn("entries/answer/index.md", history_body)
            self.assertIn("retry failed", history_body)
            self.assertIn("日志尾部：retry failed", detail_body)

            await pilot.press("ctrl+y")
            await pilot.pause()
            retry_title = app.query_one(SummaryCard).query_one(".card-title", Static).content
            queue_body = app.query_one(QueueCard).query_one(".card-body", Static).content
            self.assertEqual(retry_title, "失败项重试草案")
            self.assertIn("专栏 #789", queue_body)
            self.assertNotIn("回答 #456", queue_body)

    async def test_multiline_textarea_submit_builds_draft(self):
        app = ZhihuInteractiveShell(draft_executor=_mixed_executor)
        async with app.run_test(size=(100, 34)) as pilot:
            await pilot.pause()
            app.query_one("#url-input", ArchiveInput).load_text(
                "你对下一代Transformer架构的预测是什么？ - 第欧根尼的回答 - 知乎\n"
                "https://www.zhihu.com/question/1904728228213548260/answer/2018626185983215533"
            )
            await pilot.press("enter")
            await pilot.pause()
            summary_title = app.query_one(SummaryCard).query_one(".card-title", Static).content
            summary_body = app.query_one(SummaryCard).query_one(".card-body", Static).content
            self.assertEqual(summary_title, "已识别归档草案")
            self.assertIn("回答 #2018626185983215533", summary_body)


if __name__ == "__main__":
    unittest.main()
