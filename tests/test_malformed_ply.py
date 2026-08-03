import tempfile
import unittest
from pathlib import Path

from splatgrade.core import DEMO, analyze, parse_ply


def _write(directory: str, content: str) -> Path:
    path = Path(directory) / "scene.ply"
    path.write_text(content)
    return path


class MalformedPlyTest(unittest.TestCase):
    """Two real defects in parse_ply, both undermining a quality gate meant
    to catch bad scene data: (1) a bare "element" header line (no name)
    indexed parts[1] directly and crashed with an uncaught IndexError; (2) a
    vertex row with fewer fields than declared properties silently zipped
    short, leaving missing fields (e.g. opacity) at their default value
    instead of being flagged as corrupt."""

    def test_bare_element_header_line_does_not_crash(self):
        content = "ply\nformat ascii 1.0\nelement\nend_header\n"
        with tempfile.TemporaryDirectory() as directory:
            path = _write(directory, content)
            with self.assertRaises(ValueError):
                parse_ply(path)

    def test_truncated_vertex_row_is_rejected_not_defaulted(self):
        content = (
            "ply\nformat ascii 1.0\nelement vertex 1\n"
            "property float x\nproperty float y\nproperty float z\nproperty float opacity\n"
            "end_header\n0.0 0.0 0.0\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = _write(directory, content)
            with self.assertRaisesRegex(ValueError, "fewer fields"):
                parse_ply(path)

    def test_complete_row_still_parses(self):
        content = (
            "ply\nformat ascii 1.0\nelement vertex 1\n"
            "property float x\nproperty float y\nproperty float z\nproperty float opacity\n"
            "end_header\n0.0 0.0 0.0 0.5\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = _write(directory, content)
            points = parse_ply(path)
        self.assertEqual(points[0]["opacity"], 0.5)

    def test_demo_output_unaffected(self):
        result = analyze(DEMO)
        self.assertEqual(result["quality_score"], 49)
        self.assertEqual(result["grade"], "D")
        self.assertEqual(len(result["giant_splats"]), 2)
        self.assertEqual(len(result["duplicate_pairs"]), 3)
        self.assertEqual(len(result["low_opacity_splats"]), 4)
        self.assertEqual(len(result["floaters"]), 2)


if __name__ == "__main__":
    unittest.main()
