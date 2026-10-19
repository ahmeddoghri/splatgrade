"""Real 3DGS exporters write binary PLY, so the gate has to read it."""
import struct
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from splatgrade.core import DEMO, analyze, parse_ply

FIXTURES = Path(__file__).parent / "fixtures"


class BinaryPlyTest(unittest.TestCase):
    def test_binary_and_ascii_of_the_same_scene_grade_identically(self):
        binary = analyze({**DEMO, "gaussians": parse_ply(FIXTURES / "scene_binary.ply")})
        ascii_ = analyze({**DEMO, "gaussians": parse_ply(FIXTURES / "scene_ascii.ply")})
        self.assertEqual(binary["grade"], ascii_["grade"])
        self.assertEqual(binary["quality_score"], ascii_["quality_score"])
        self.assertEqual(binary["giant_splats"], ascii_["giant_splats"])

    def test_the_binary_fixture_has_a_real_3dgs_property_layout(self):
        header = (FIXTURES / "scene_binary.ply").read_bytes().split(b"end_header")[0].decode()
        for name in ("f_dc_0", "opacity", "scale_0", "rot_0", "nx"):
            self.assertIn(f"property float {name}", header)
        self.assertIn("format binary_little_endian 1.0", header)

    def test_a_truncated_binary_body_is_rejected_rather_than_silently_short(self):
        data = (FIXTURES / "scene_binary.ply").read_bytes()
        with TemporaryDirectory() as directory:
            path = Path(directory) / "truncated.ply"
            path.write_bytes(data[: len(data) - 40])
            with self.assertRaises(ValueError) as caught:
                parse_ply(path)
        self.assertIn("truncated", str(caught.exception))

    def test_an_unsupported_property_type_is_named_not_guessed(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "weird.ply"
            path.write_bytes(
                b"ply\nformat binary_little_endian 1.0\nelement vertex 1\n"
                b"property float x\nproperty float y\nproperty float z\n"
                b"property float128 w\nend_header\n" + struct.pack("<4f", 0, 0, 0, 0)
            )
            with self.assertRaises(ValueError) as caught:
                parse_ply(path)
        self.assertIn("float128", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
