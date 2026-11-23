from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

import httpx

from tools.paper_enrich import (
    ApiClient,
    extract_identifiers,
    normalize_title,
    title_similarity,
    verify_paper_list,
    verify_row,
    write_outputs,
    MISMATCH,
    NETWORK_ERROR,
    NOT_FOUND,
    SKIPPED,
    VERIFIED,
)


def crossref_item(title: str, year: int, doi: str = "10.1/x") -> dict:
    return {
        "title": [title],
        "author": [{"family": "Doe", "given": "Jane"}],
        "issued": {"date-parts": [[year]]},
        "container-title": ["Nature"],
        "DOI": doi,
    }


def crossref_response(items: list[dict], status: int = 200) -> httpx.Response:
    return httpx.Response(status, json={"message": {"items": items}})


def make_client(handler) -> ApiClient:
    return ApiClient(transport=httpx.MockTransport(handler))


class TitleUtilTests(unittest.TestCase):
    def test_normalize_and_similarity(self) -> None:
        self.assertEqual(normalize_title("Hello, World! (2024)"), "helloworld2024")
        self.assertGreater(title_similarity("Agent Dojo: A Dynamic Environment", "agent dojo: a dynamic environment"), 0.99)
        self.assertLess(title_similarity("Completely Different Topic", "Agent Dojo: A Dynamic Environment"), 0.4)

    def test_extract_identifiers(self) -> None:
        doi, arxiv = extract_identifiers({"doi": "10.48550/arXiv.2403.02691", "url": ""})
        self.assertEqual((doi, arxiv), ("", "2403.02691"))
        doi, arxiv = extract_identifiers({"doi": "", "url": "https://arxiv.org/abs/2406.13352v2"})
        self.assertEqual((doi, arxiv), ("", "2406.13352"))
        doi, arxiv = extract_identifiers({"doi": "10.1145/3579856", "url": ""})
        self.assertEqual((doi, arxiv), ("10.1145/3579856", ""))
        doi, arxiv = extract_identifiers({"doi": "", "url": "https://doi.org/10.1145/3579856.3591234"})
        self.assertEqual((doi, arxiv), ("10.1145/3579856.3591234", ""))


class VerifyRowTests(unittest.TestCase):
    def test_doi_hit_verified(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert "works/10.1234/known-paper" in str(request.url), str(request.url)
            return httpx.Response(200, json={"message": crossref_item("Known Paper", 2024, "10.1234/known-paper")})

        result = verify_row(
            {"title": "Known Paper", "doi": "10.1234/known-paper", "publish_date": "2024-05"},
            1, make_client(handler),
        )
        self.assertEqual(result.status, VERIFIED)
        self.assertEqual(result.match.title, "Known Paper")
        self.assertEqual(result.match.year, "2024")

    def test_arxiv_id_hit_verified_with_year_drift(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            xml = (
                '<feed xmlns="http://www.w3.org/2005/Atom"><entry>'
                "<title>Paper on Agents</title><published>2023-01-15T00:00:00Z</published>"
                "<author><name>A. Author</name></author>"
                "</entry></feed>"
            )
            return httpx.Response(200, text=xml)

        result = verify_row(
            {"title": "Paper on Agents", "url": "https://arxiv.org/abs/2401.00001",
             "publish_date": "2024"},
            1, make_client(handler),
        )
        self.assertEqual(result.status, VERIFIED)
        self.assertIn("arXiv→会议常见", result.reason)

    def test_title_search_hit_verified(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert "query.bibliographic" in str(request.url)
            return crossref_response([crossref_item("The Exact Title We Search", 2023)])

        result = verify_row({"title": "The Exact Title We Search"}, 1, make_client(handler))
        self.assertEqual(result.status, VERIFIED)
        self.assertEqual(result.match.venue, "Nature")

    def test_no_match_not_found(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return crossref_response([])

        result = verify_row({"title": "Something Unheard Of"}, 1, make_client(handler), use_s2=False)
        self.assertEqual(result.status, NOT_FOUND)
        self.assertIn("人工核对", result.reason)

    def test_network_errors_only(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("boom", request=request)

        result = verify_row({"title": "Any Title"}, 1, make_client(handler), use_s2=False)
        self.assertEqual(result.status, NETWORK_ERROR)

    def test_low_similarity_mismatch(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return crossref_response([crossref_item("A Totally Different Paper Title Exists Here", 2024)])

        result = verify_row({"title": "Agent Security Landscape 2026"}, 1, make_client(handler), use_s2=False)
        self.assertEqual(result.status, MISMATCH)

    def test_year_conflict_mismatch(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return crossref_response([crossref_item("Same Title Text Exactly", 2015)])

        result = verify_row(
            {"title": "Same Title Text Exactly", "publish_date": "2024-01"}, 1, make_client(handler), use_s2=False
        )
        self.assertEqual(result.status, MISMATCH)
        self.assertIn("年份相差过大", result.reason)

    def test_skipped_without_title_or_ids(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError("should not call network")

        result = verify_row({"title": "", "doi": "", "url": ""}, 1, make_client(handler))
        self.assertEqual(result.status, SKIPPED)

    def test_doi_404_falls_back_to_title_search(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if str(request.url).endswith("10.9%2Fmissing") or str(request.url).endswith("10.9/missing"):
                return httpx.Response(404, json={"message": {}})
            return crossref_response([crossref_item("Fallback Title Found", 2022)])

        result = verify_row(
            {"title": "Fallback Title Found", "doi": "10.9/missing"}, 1, make_client(handler)
        )
        self.assertEqual(result.status, VERIFIED)


class WriteOutputsTests(unittest.TestCase):
    def test_write_outputs_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rows = [
                {"title": "Good Paper", "doi": "", "url": ""},
                {"title": "Ghost Paper", "doi": "", "url": ""},
            ]
            results = [
                verify_row(rows[0], 1, make_client(lambda request: crossref_response(
                    [crossref_item("Good Paper", 2024)]))),
                verify_row(rows[1], 2, make_client(lambda request: crossref_response([])), use_s2=False),
            ]
            enriched, manifest = write_outputs(root, rows, results)
            self.assertTrue(enriched.exists() and manifest.exists())
            with enriched.open(encoding="utf-8") as handle:
                out_rows = list(csv.DictReader(handle))
            self.assertEqual(out_rows[0]["verification_status"], VERIFIED)
            self.assertEqual(out_rows[1]["verification_status"], NOT_FOUND)
            data = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(data["total"], 2)
            self.assertEqual(data["by_status"][VERIFIED], 1)
            self.assertEqual(data["by_status"][NOT_FOUND], 1)

    def test_verify_paper_list_end_to_end(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if "query.bibliographic" in str(request.url):
                return crossref_response([crossref_item("Batch Title", 2024)])
            raise AssertionError(f"unexpected url {request.url}")

        rows = [{"title": "Batch Title"}, {"title": "Batch Title"}]
        results = verify_paper_list(rows, make_client(handler), use_s2=False)
        self.assertEqual([r.status for r in results], [VERIFIED, VERIFIED])


if __name__ == "__main__":
    unittest.main()
