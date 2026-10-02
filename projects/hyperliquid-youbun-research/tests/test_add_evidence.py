import pathlib,unittest
class T(unittest.TestCase):
 def test_schema_excludes_outcomes(self):
  text=(pathlib.Path(__file__).parents[1]/'scripts'/'build_add_evidence.py').read_text(); self.assertNotIn("'net_pnl'",text); self.assertNotIn("'mfe'",text)
if __name__=='__main__':unittest.main()
