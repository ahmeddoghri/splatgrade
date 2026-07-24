import tempfile
import unittest
from pathlib import Path

from splatgrade.core import DEMO, analyze, parse_ply


class SplatGradeTests(unittest.TestCase):
    def test_demo_finds_artifact_classes(self):
        result = analyze(DEMO)
        self.assertEqual(result["gaussian_count"], 36)
        self.assertEqual(len(result["giant_splats"]), 2)
        self.assertEqual(len(result["duplicate_pairs"]), 3)
        self.assertEqual(len(result["low_opacity_splats"]), 4)
        self.assertEqual(len(result["floaters"]), 2)

    def test_demo_grade_is_reproducible(self):
        result = analyze(DEMO)
        self.assertEqual(result["quality_score"], 49)
        self.assertEqual(result["grade"], "D")

    def test_ascii_ply_parser(self):
        content = """ply
format ascii 1.0
element vertex 1
property float x
property float y
property float z
property float scale
property float opacity
end_header
1 2 3 0.2 0.8
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scene.ply"
            path.write_text(content)
            points = parse_ply(path)
        self.assertEqual(points[0]["scale"], [0.2, 0.2, 0.2])

    def test_empty_scene_fails(self):
        with self.assertRaisesRegex(ValueError, "empty"):
            analyze({"gaussians": []})


if __name__ == "__main__":
    unittest.main()
