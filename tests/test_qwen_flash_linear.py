import json
import unittest
from unittest.mock import patch

from jevbench.adapters.qwen_flash_linear import QwenFlashLinearAdapter
from jevbench.tasks import Task


def task(kind='choice', criteria=None, labels=None):
    if criteria is None and kind=='choice':
        criteria={'a':'Alpha','b':'Beta'}
    return Task(id='private-id-must-not-leak',family='f',state={'text':'Evidence'},
                question={'type':kind,'instructions':'Decide this.','criteria':criteria},
                labels=labels or ['a','b'],expected='gold-must-not-leak',split='private',
                provenance={'rationale':'rationale-must-not-leak'})


class QwenFlashLinearTests(unittest.TestCase):
    def test_complete_rubric_without_gold(self):
        request=QwenFlashLinearAdapter.build_request(task())
        self.assertEqual(request['options'],['a: Alpha','b: Beta'])
        self.assertEqual(request['question'],'State:\n{"text": "Evidence"}\n\nQuestion type: choice\nInstructions:\nDecide this.')
        self.assertNotIn('must-not-leak',json.dumps(request))

    def test_noul_and_score_mapping(self):
        request=QwenFlashLinearAdapter.build_request(task('noul',{'true':'True rubric','false':'False rubric'},['no','yes']))
        self.assertEqual(request['options'],['no: False rubric','yes: True rubric'])
        request=QwenFlashLinearAdapter.build_request(task('noul',None,['no','yes']))
        self.assertEqual(request['options'],['no','yes'])
        request=QwenFlashLinearAdapter.build_request(task('score',['low','medium','high'],['0','1','2']))
        self.assertEqual(request['options'],['0: low','1: medium','2: high'])

    def test_preserves_native_probabilities_and_raw_response(self):
        raw={'input_tokens':82,'selected_index':2,'options':[{'index':1,'probability':.2},{'index':2,'probability':.8}]}
        with patch('jevbench.adapters.qwen_flash_linear.http_post_json',return_value=(200,raw,.12)) as post:
            result=QwenFlashLinearAdapter(key_env='').run(task())
        self.assertTrue(result.ok)
        self.assertEqual(result.probs,{'a':.2,'b':.8})
        self.assertEqual(result.raw,raw)
        self.assertEqual(result.usage,{'input_tokens':82,'output_tokens':1})
        self.assertEqual(result.latency_s,.12)
        self.assertNotIn('Authorization',post.call_args.args[2])

    def test_does_not_repair_probability_sum(self):
        raw={'options':[{'index':1,'probability':.2},{'index':2,'probability':.2}]}
        with patch('jevbench.adapters.qwen_flash_linear.http_post_json',return_value=(200,raw,.1)):
            result=QwenFlashLinearAdapter().run(task())
        self.assertEqual(result.probs,{'a':.2,'b':.2})

    def test_invalid_response_fails(self):
        for raw in [{'options':[]}, {'options':[{'index':2,'probability':.2},{'index':1,'probability':.8}]},
                    {'options':[{'index':1,'probability':float('nan')},{'index':2,'probability':.8}]},
                    {'options':[{'index':1,'probability':True},{'index':2,'probability':.8}]},
                    {'options':[{'index':1,'probability':-1},{'index':2,'probability':2}]}]:
            with self.subTest(raw=raw),patch('jevbench.adapters.qwen_flash_linear.http_post_json',return_value=(200,raw,.1)):
                self.assertFalse(QwenFlashLinearAdapter().run(task()).ok)

    def test_no_retries_or_candidate_truncation(self):
        with patch('jevbench.adapters.qwen_flash_linear.http_post_json',return_value=(429,{'error':'rate limited'},.1)) as post:
            result=QwenFlashLinearAdapter().run(task())
            self.assertEqual(result.status,429)
            self.assertEqual(post.call_count,1)
        with patch('jevbench.adapters.qwen_flash_linear.http_post_json') as post:
            many=task(criteria={str(i):str(i) for i in range(87)},labels=[str(i) for i in range(87)])
            self.assertFalse(QwenFlashLinearAdapter().run(many).ok)
            post.assert_not_called()

    def test_missing_requested_key_fails(self):
        with patch.dict('os.environ',{},clear=True),patch('jevbench.adapters.qwen_flash_linear.http_post_json') as post:
            result=QwenFlashLinearAdapter(key_env='MISSING_KEY').run(task())
            self.assertFalse(result.ok)
            post.assert_not_called()

if __name__=='__main__':unittest.main()
