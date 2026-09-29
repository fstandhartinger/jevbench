import json,math,multiprocessing,tempfile,time,unittest
from pathlib import Path
from jevbench.tasks import Task,load_jsonl
from jevbench.budget import Ledger,BudgetExceeded
from jevbench.scoring import score_task,validate_probs,InvalidDistribution
from jevbench.summarize import summarize,public_export,agreement
from jevbench.adapters import GradioSpaceAdapter,LocalOpenJevAdapter,OpenAICompatAdapter,SystemOneListAdapter,TypeSafeAdapter
from jevbench.adapters.base import DecisionResult
from jevbench.runner import Runner

class SlowLedger(Ledger):
 def _read(self,f):
  state=super()._read(f);time.sleep(.2);return state

def reserve_concurrently(path,start,outcomes):
 start.wait()
 try:SlowLedger(path,1).reserve(.6);outcomes.put('reserved')
 except BudgetExceeded:outcomes.put('rejected')

def task(id='x',split='private',group=None):return Task(id,'intent','PRIVATE TEXT SENTINEL',{'type':'choice','instructions':'Which?','criteria':{'a':'A','b':'B'}},['a','b'],'b',split,group)
class Protocol(unittest.TestCase):
 def test_budget_crash_and_replay(self):
  with tempfile.TemporaryDirectory()as d:
   p=d+'/ledger';l=Ledger(p,1);r=l.reserve(.8)
   with self.assertRaises(BudgetExceeded):Ledger(p,20).reserve(.3)
   l.settle(r,.1);self.assertAlmostEqual(l.charged,.1)
   with self.assertRaises(BudgetExceeded):l.settle(r,.1)
   self.assertIsNotNone(l.reserve(.8))
 def test_budget_nonfinite(self):
  with tempfile.TemporaryDirectory()as d:
   for v in [float('nan'),float('inf'),-1]:
    with self.assertRaises(BudgetExceeded):Ledger(d+'/l',1).reserve(v)
 def test_budget_concurrent_reservations_share_cap(self):
  with tempfile.TemporaryDirectory()as d:
   ctx=multiprocessing.get_context('spawn');start=ctx.Event();outcomes=ctx.Queue()
   workers=[ctx.Process(target=reserve_concurrently,args=(d+'/ledger',start,outcomes))for _ in range(2)]
   for worker in workers:worker.start()
   start.set()
   for worker in workers:worker.join(10);self.assertFalse(worker.is_alive());self.assertEqual(worker.exitcode,0)
   self.assertEqual(sorted(outcomes.get(timeout=1)for _ in workers),['rejected','reserved'])
 def test_invalid_probabilities(self):
  for p in [{'a':True,'b':0},{'a':math.nan,'b':.5},{'a':.3,'b':.3},{'a':1},{'a':1,'b':0,'c':0}]:
   with self.assertRaises(InvalidDistribution):validate_probs(p,['a','b'])
 def test_rounded_sum_is_renormalized_but_reported(self):
  t=task()
  s=score_task({'a':.25,'b':.745},t)  # sums to 0.995: three-decimal rounding, not a malformed answer
  self.assertTrue(s['valid']);self.assertFalse(s['strict_valid']);self.assertTrue(s['renormalized'])
  self.assertAlmostEqual(sum(s['probs'].values()),1);self.assertTrue(s['correct'])
  bad=score_task({'a':.2,'b':.5},t)   # sums to 0.7: outside the band, still wrong
  self.assertFalse(bad['valid']);self.assertFalse(bad['correct'])
 def test_ordinal_argmax_not_round_mean(self):
  t=Task('ord','ordinal','s',{'type':'score','instructions':'q','criteria':['zero','one','two']},['0','1','2'],0,'public')
  s=score_task({'0':.4,'1':.2,'2':.4},t);self.assertTrue(s['strict_valid']);self.assertEqual(s['predicted'],'0');self.assertTrue(s['correct']);self.assertAlmostEqual(s['ordinal_ev'],1)
 def test_no_private_export_even_injected_summary(self):
  t=task();export=public_export({'leak':t.state,'id':t.id},[t],[])
  self.assertNotIn('PRIVATE TEXT SENTINEL',json.dumps(export));self.assertNotIn('leak',export);self.assertIsNone(export['accuracy']);self.assertIsNone(export['latency']['p95_s'])
 def test_brier_ece_and_failure_denominator(self):
  ts=[task('a'),task('b')];rows=[{'task_id':'a','ok':True,'valid':True,'correct':True,'predicted':'b','probs':{'a':.25,'b':.75},'status':'ok','latency_s':1,'cost_usd':0},{'task_id':'b','ok':False,'valid':False,'correct':False,'status':'failed','latency_s':3,'cost_usd':None}]
  s=summarize(ts,rows);self.assertEqual(s['accuracy'],.5);self.assertEqual(s['schema_validity'],.5);self.assertAlmostEqual(s['brier_mean'],.125);self.assertAlmostEqual(s['ece']['ece'],.25);self.assertEqual(s['latency']['p50_s'],2);self.assertIsNone(s['price_per_1000_decisions_usd'])
 def test_agreement_is_not_both_correct(self):
  ts=[task('a',group='g'),task('b',group='g')];rs=[{'task_id':x,'valid':True,'correct':False,'predicted':'a'}for x in ['a','b']];s=agreement(ts,rs);self.assertEqual(s['agreement'],1);self.assertEqual(s['both_correct_rate_all_pairs'],0)
 def test_noul_rubric_reaches_llm(self):
  t=Task('n','policy','s',{'type':'noul','instructions':'q','criteria':{'true':'PASS RUBRIC','false':'FAIL RUBRIC'}},['no','yes'],'yes','public');a=OpenAICompatAdapter('http://localhost','model');body=json.dumps(a.build_request(t));self.assertIn('PASS RUBRIC',body);self.assertIn('FAIL RUBRIC',body);self.assertEqual(a.build_request(t)['max_tokens'],4096)
 def test_rate_limit_stops(self):
  class A:
   name='fake';price_input_per_m=price_output_per_m=0
   def reserve_estimate(self,t):return 0
   def run(self,t):return DecisionResult('fake',False,status=429,error='limit')
  with tempfile.TemporaryDirectory()as d:
   r=Runner(A(),Ledger(d+'/ledger',1),d+'/raw').run_all([task('a'),task('b')],results_path=d+'/results');self.assertEqual(len(r),1);self.assertEqual(len(Path(d+'/results').read_text().splitlines()),1)
 def test_native_flavours_send_the_same_rubric(self):
  t=Task('c','intent','s',{'type':'choice','instructions':'Which?','criteria':{'a':'ALPHA RUBRIC','b':'BETA RUBRIC'}},['a','b'],'a','public')
  for a in [TypeSafeAdapter(model='m'),SystemOneListAdapter('http://localhost'),GradioSpaceAdapter('http://localhost'),LocalOpenJevAdapter('/tmp/none')]:
   body=json.dumps(a.build_request(t));self.assertIn('ALPHA RUBRIC',body,a.name);self.assertIn('BETA RUBRIC',body,a.name)
 def test_gradio_refuses_delimiter_collision(self):
  t=Task('c','intent','s',{'type':'choice','instructions':'Which?','criteria':{'a,b':'X','c':'Y'}},['a,b','c'],'c','public')
  r=GradioSpaceAdapter('http://localhost').run(t);self.assertFalse(r.ok);self.assertIn('delimiter',r.error)
 def test_list_flavour_rejects_wrong_answer_shape(self):
  import jevbench.adapters.systemone_list as sl
  t=task();a=sl.SystemOneListAdapter('http://localhost')
  for payload in [{'answers':[]},{'answers':[{'id':'decision','type':'noul','noul':.5}]},{'answers':[{'id':'decision','type':'choice','choice':'zzz','probabilities':{'a':.5,'b':.5}}]}]:
   sl.http_post_json=lambda *a,_p=payload,**k:(200,_p,.1)
   r=a.run(t);self.assertFalse(r.ok,payload)
  sl.http_post_json=lambda *a,**k:(200,{'answers':[{'id':'decision','type':'choice','choice':'b','probabilities':{'a':.25,'b':.75}}],'model':'e2b-full'},.1)
  r=a.run(t);self.assertTrue(r.ok);self.assertEqual(r.model,'e2b-full');self.assertEqual(r.probs['b'],.75)
 def test_local_adapter_has_no_tariff(self):
  a=LocalOpenJevAdapter('/tmp/none');self.assertIsNone(a.price_input_per_m);self.assertEqual(a.reserve_estimate(task()),0)
 def test_public_suite_pairs(self):
  ts=load_jsonl('datasets/public/original.jsonl');self.assertEqual(len(ts),72);self.assertEqual(len({t.id for t in ts}),72)
  for t in ts:t.validate()
  groups={t.group for t in ts}
  for g in groups:self.assertEqual(len({str(t.expected)for t in ts if t.group==g}),1)
if __name__=='__main__':unittest.main()


class LabelOnlyScoring(unittest.TestCase):
    """v1.1: a label-only system (Needle 3) is scored on its label, never given
    a distribution, and an abstention counts wrong."""

    def _task(self):
        from jevbench.tasks import Task
        return Task("t", "fact", "Status: paid.", {"type": "noul", "instructions": "Paid?"},
                    ["no", "yes"], "yes", "public")

    def test_right_wrong_abstain(self):
        from jevbench.scoring import score_label
        t = self._task()
        self.assertTrue(score_label("yes", t)["correct"])
        self.assertFalse(score_label("no", t)["correct"])
        r = score_label(None, t)
        self.assertFalse(r["correct"]); self.assertFalse(r["valid"]); self.assertIsNone(r["probs"])
        self.assertFalse(score_label("maybe", t)["valid"])

    def test_needle_label_mapping(self):
        from jevbench.adapters.needle_local import NeedleLocalAdapter as N
        t = self._task()
        self.assertEqual(N.to_label(True, t), "yes")
        self.assertEqual(N.to_label(False, t), "no")
        self.assertIsNone(N.to_label(3, t))
        tool = N.build_tool(t)
        self.assertEqual(tool["parameters"]["properties"]["decision"]["type"], "boolean")
