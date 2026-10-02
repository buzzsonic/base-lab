import importlib.util
import pathlib
import unittest

SCRIPT = pathlib.Path(__file__).parents[1] / "scripts" / "summarize_exploratory_labels.py"
SPEC = importlib.util.spec_from_file_location("summarize_exploratory_labels", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)

class ExploratorySummaryTest(unittest.TestCase):
    def test_counts_keep_unavailable_separate(self):
        rows = [{"fomo_status": value} for value in ("TRUE", "FALSE", "UNAVAILABLE")]
        for row in rows:
            for label in MODULE.LABELS[1:]: row[f"{label}_status"] = "FALSE"
        result = MODULE.label_counts(rows)[0]
        self.assertEqual((1, 1, 1), (result["true"], result["false"], result["unavailable"]))

    def test_overlap_is_nonexclusive(self):
        row = {f"{label}_status": "FALSE" for label in MODULE.LABELS}
        row["fomo_status"] = row["late_status"] = "TRUE"
        self.assertEqual([{"true_label_pattern": "fomo+late", "episodes": 1}], MODULE.overlap_rows([row]))

if __name__ == "__main__": unittest.main()
