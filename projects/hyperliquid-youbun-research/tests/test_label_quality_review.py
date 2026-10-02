import importlib.util,pathlib,unittest
P=pathlib.Path(__file__).parents[1]/"scripts"/"review_label_quality.py"; S=importlib.util.spec_from_file_location("review",P); M=importlib.util.module_from_spec(S); S.loader.exec_module(M)
class T(unittest.TestCase):
 def test_select_keeps_all_true_and_both_side_false(self):
  rows=[]
  for i,side in enumerate(("LONG","SHORT","LONG")):
   r={"episode_id":str(i),"account_alias":f"A{i}","side":side}; r.update({f"{x}_status":"FALSE" for x in M.LABELS}); rows.append(r)
  rows[2]["fomo_status"]="TRUE"; out=M.select(rows); self.assertEqual({"0","1","2"},{r["episode_id"] for r in out})
if __name__=="__main__": unittest.main()
