from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from tests.test_aggregate_meta import valid_chapter
from tools.aggregate_meta import emit_evidence, validate_chapters
from tools.qc import Report, check_evidence_independence, check_research_quality
from tools.research_quality import build_quality_scorecard
from tools.source_identity import independent_source_groups


def recorded_chapter() -> dict:
    chapter = valid_chapter()
    chapter['research_questions'] = [{
        'question_id': 'Q1', 'question': '规模多大？', 'status': 'answered',
        'evidence_ids': ['E1', 'E2'],
    }]
    chapter['search_log'] = [{
        'question_id': 'Q1', 'query': '目标市场规模 不同口径 反例', 'intent': 'counter',
        'outcome': 'no_new_evidence', 'source_ids': [], 'reason': '本轮没有找到不同统计口径。',
    }]
    for point in chapter['data_points']:
        point['provenance'] = [{
            'source_id': point['source_ids'][0], 'locator': '第 3 页，市场规模表',
            'excerpt': '目标市场规模为 10 亿元。', 'access_date': '2026-09-10',
        }]
    return chapter


class IndependenceRegressionTests(unittest.TestCase):
    def check_chapter(self, chapter: dict, depth: str = '标准') -> Report:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'data').mkdir()
            (root / 'data/chapter_meta.json').write_text(json.dumps([chapter]))
            report = Report()
            check_evidence_independence(report, root, depth, strict=True)
            return report

    def test_same_url_different_group_is_one_source_in_qc_and_matrix(self):
        chapter = valid_chapter()
        chapter['sources'][1]['url'] = chapter['sources'][0]['url'] + '?utm_source=reprint#table'
        self.assertTrue(self.check_chapter(chapter).errors)
        row = emit_evidence([chapter])[0]
        self.assertEqual(row['independent_source_count'], '1')
        self.assertEqual(row['strong_source_count'], '1')
        self.assertEqual(row['sufficiency'], '有限')

    def test_bibliography_only_source_does_not_support_numeric_claim(self):
        chapter = valid_chapter()
        chapter['claims'][0]['supporting_evidence_ids'] = ['E1']
        errors = self.check_chapter(chapter).errors
        self.assertTrue(any('数值声明' in error for error in errors))

    def test_opposing_source_does_not_support_numeric_claim(self):
        chapter = valid_chapter()
        chapter['claims'][0]['supporting_evidence_ids'] = ['E1']
        chapter['claims'][0]['opposing_evidence_ids'] = ['E2']
        self.assertTrue(any('数值声明' in e for e in self.check_chapter(chapter).errors))

    def test_unlinked_strong_source_does_not_upgrade_weak_evidence(self):
        chapter = valid_chapter()
        chapter['sources'][0]['tier'] = 'D'
        chapter['claims'][0]['supporting_evidence_ids'] = ['E1']
        self.assertTrue(any('C/D' in e for e in self.check_chapter(chapter).errors))

    def test_numeric_claim_still_needs_two_sources_in_fast_mode(self):
        chapter = valid_chapter()
        chapter['claims'][0]['supporting_evidence_ids'] = ['E1']
        self.assertTrue(any('数值声明' in e for e in self.check_chapter(chapter, '快速').errors))

    def test_independent_evidence_passes(self):
        self.assertFalse(self.check_chapter(valid_chapter()).errors)

    def test_origin_and_producer_links_form_transitive_groups(self):
        sources = [
            {'url': 'https://original.example/a', 'organization': 'A'},
            {'url': 'https://reprint.example/b', 'origin_url': 'https://original.example/a', 'organization': 'B'},
            {'url': 'https://reprint.example/c', 'organization': 'B'},
            {'url': 'https://independent.example/d', 'organization': 'C'},
        ]
        for ordered in (sources, sources[::-1]):
            self.assertEqual(sorted(map(len, independent_source_groups(ordered))), [1, 3])

    def test_arxiv_aliases_cannot_gain_independence(self):
        self.assertEqual(len(independent_source_groups([
            {'url': 'https://arxiv.org/abs/2501.12345v1', 'independence_group': 'A'},
            {'url': 'https://arxiv.org/pdf/2501.12345v2.pdf', 'independence_group': 'B'},
        ])), 1)

    def test_unknown_sources_do_not_increase_count(self):
        self.assertEqual(independent_source_groups([{'source_id': 'S1'}, {'source_id': 'S2'}]), [])


class ResearchQualityTests(unittest.TestCase):
    def test_legacy_v2_is_valid_but_missing_records_are_not_perfect_score(self):
        chapter = valid_chapter()
        self.assertFalse(validate_chapters([chapter])[1].errors)
        score = build_quality_scorecard([chapter])
        self.assertIsNone(score['metrics']['question_answer_coverage']['ratio'])
        self.assertEqual(score['metrics']['evidence_provenance_coverage']['ratio'], 0)
        self.assertTrue(score['findings'])

    def test_counter_search_without_opposing_findings_is_valid(self):
        chapter = recorded_chapter()
        self.assertFalse(validate_chapters([chapter])[1].errors)
        score = build_quality_scorecard([chapter])
        self.assertEqual(score['findings'], [])
        self.assertEqual(score['metrics']['counter_search_coverage']['ratio'], 1)
        self.assertEqual(score['evaluation_kind'], 'metadata_coverage_not_factual_accuracy')

    def test_blocked_counter_search_does_not_count_as_reviewed(self):
        chapter = recorded_chapter()
        chapter['search_log'][0]['outcome'] = 'blocked'
        score = build_quality_scorecard([chapter])
        self.assertEqual(score['metrics']['counter_search_coverage']['ratio'], 0)

    def test_each_evidence_source_needs_its_own_locator(self):
        chapter = recorded_chapter()
        chapter['data_points'][0]['source_ids'].append('S2')
        score = build_quality_scorecard([chapter])
        self.assertEqual(score['metrics']['evidence_provenance_coverage']['ratio'], .5)

    def test_optional_records_reject_bad_types_and_dangling_ids(self):
        changes = [
            ('research_questions', None),
            ('search_log', [None]),
        ]
        for key, value in changes:
            with self.subTest(key=key):
                chapter = recorded_chapter()
                chapter[key] = value
                self.assertTrue(validate_chapters([chapter])[1].errors)
        chapter = recorded_chapter()
        chapter['research_questions'][0]['evidence_ids'] = ['missing']
        chapter['search_log'][0]['question_id'] = 'missing'
        chapter['data_points'][0]['provenance'][0]['source_id'] = 'S2'
        self.assertEqual(len(validate_chapters([chapter])[1].errors), 3)

    def test_fake_complete_question_and_empty_successful_search_rejected(self):
        chapter = recorded_chapter()
        chapter['research_questions'][0]['evidence_ids'] = []
        chapter['search_log'][0]['outcome'] = 'new_evidence'
        self.assertEqual(len(validate_chapters([chapter])[1].errors), 2)

    def test_unanswered_requires_gap_and_provenance_requires_real_date(self):
        chapter = recorded_chapter()
        chapter['research_questions'][0]['status'] = 'unanswered'
        chapter['data_points'][0]['provenance'][0]['access_date'] = '2026-02-30'
        self.assertEqual(len(validate_chapters([chapter])[1].errors), 2)

    def test_malformed_refs_rejected_and_shared_polarity_reviewed(self):
        for value in ('E1', ['E1', 'E1'], [None], [{'id': 'E1'}]):
            with self.subTest(value=value):
                chapter = valid_chapter()
                chapter['claims'][0]['supporting_evidence_ids'] = value
                self.assertTrue(validate_chapters([chapter])[1].errors)
        chapter = valid_chapter()
        chapter['chapter_conclusion']['opposing_evidence_ids'] = ['E1']
        validation = validate_chapters([chapter])[1]
        self.assertFalse(validation.errors)
        self.assertTrue(validation.warnings)
        self.assertTrue(validate_chapters([])[1].errors)

    def test_totals_use_denominators_not_chapter_average(self):
        first, second = recorded_chapter(), recorded_chapter()
        second['chapter_id'] = 'ch02'
        extra = copy.deepcopy(second['research_questions'][0])
        extra.update(question_id='Q2', status='unanswered', evidence_ids=[], gap_reason='未公开')
        second['research_questions'].append(extra)
        metric = build_quality_scorecard([first, second])['metrics']['question_answer_coverage']
        self.assertEqual(metric, {'covered': 2, 'total': 3, 'ratio': .6667})

    def test_qc_revalidates_and_replaces_stale_scorecard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'data').mkdir()
            meta = root / 'data/chapter_meta.json'
            meta.write_text(json.dumps([recorded_chapter()]))
            report = Report()
            self.assertTrue(check_research_quality(report, root, True))
            self.assertFalse(report.errors)
            meta.write_text('[]')
            report = Report()
            self.assertFalse(check_research_quality(report, root, True))
            self.assertTrue(report.errors)
            score = json.loads((root / 'data/quality_scorecard.json').read_text())
            self.assertEqual(score['status'], 'invalid_metadata')
            self.assertNotIn('metrics', score)


if __name__ == '__main__':
    unittest.main()
