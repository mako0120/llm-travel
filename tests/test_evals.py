import contextlib
import io
import json
import unittest

from evals import run


class EvalTests(unittest.TestCase):
    def test_all_fixed_synthetic_suites_pass(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(run.main(), 0)
        report = json.loads(output.getvalue())
        self.assertEqual((report["cases"], report["passed"]), (20, 20))
        self.assertTrue(all(suite["scope"] for suite in report["suites"]))
