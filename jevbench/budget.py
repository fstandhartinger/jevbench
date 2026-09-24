"""Durable, locked reservations. Unsettled calls stay charged after interruption."""
import json,math,os,time,uuid
from contextlib import contextmanager

if os.name == 'nt':
 import msvcrt
else:
 import fcntl

@contextmanager
def _locked(f,shared=False):
 if os.name == 'nt':
  # Windows has no shared byte-range locks; serializing readers preserves safety.
  f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_LOCK,1)
  try:yield
  finally:
   f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
 else:
  fcntl.flock(f,fcntl.LOCK_SH if shared else fcntl.LOCK_EX)
  try:yield
  finally:fcntl.flock(f,fcntl.LOCK_UN)

class BudgetExceeded(RuntimeError):pass
def finite(x):
 x=float(x)
 if not math.isfinite(x) or x<0:raise BudgetExceeded('Cost/cap must be finite and nonnegative')
 return x
class PriceTable:
 def __init__(self,input_per_million=None,output_per_million=None,name=''):
  self.input_per_million=input_per_million;self.output_per_million=output_per_million;self.name=name
 @property
 def known(self):return self.input_per_million is not None and self.output_per_million is not None
 def estimate(self,max_input_tokens,max_output_tokens):
  if not self.known:raise BudgetExceeded('Unknown price needs explicit reservation')
  return finite(max_input_tokens)*finite(self.input_per_million)/1e6+finite(max_output_tokens)*finite(self.output_per_million)/1e6
class Ledger:
 def __init__(self,path,cap_usd=15):
  self.path=str(path);self.cap_usd=finite(cap_usd);os.makedirs(os.path.dirname(os.path.abspath(path)),exist_ok=True)
 def _read(self,f):
  f.seek(0);rows=[json.loads(l)for l in f if l.strip()];reserved={};settled={}
  for r in rows:
   if r['event']=='reserve':reserved[r['reservation_id']]=finite(r['reserved_usd'])
   if r['event']=='settle':
    rid=r['reservation_id']
    if rid in settled or rid not in reserved:raise BudgetExceeded('Invalid settlement history')
    settled[rid]=finite(r['charged_usd'])
  return rows,reserved,settled
 @staticmethod
 def _charge(reserved,settled):return sum(settled.get(k,v)for k,v in reserved.items())
 @staticmethod
 def _append(f,row):
  f.seek(0,2);f.write(json.dumps(row,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
 @property
 def charged(self):
  with open(self.path,'a+')as f:
   with _locked(f,shared=True):_,r,s=self._read(f);return self._charge(r,s)
 def reserve(self,amount_usd,meta=None):
  amount=finite(amount_usd)
  with open(self.path,'a+')as f:
   with _locked(f):
    rows,r,s=self._read(f)
    caps=[x['cap_usd']for x in rows if x['event']=='cap'];cap=min(caps+[self.cap_usd])
    if not caps:self._append(f,{'event':'cap','cap_usd':cap,'ts':time.time()})
    if self._charge(r,s)+amount>cap+1e-12:raise BudgetExceeded('Shared job budget exhausted; request not sent')
    rid=uuid.uuid4().hex;self._append(f,{'event':'reserve','reservation_id':rid,'reserved_usd':amount,'ts':time.time(),'meta':meta or {}});return rid
 def settle(self,reservation_id,actual_usd,meta=None):
  actual=finite(actual_usd)
  with open(self.path,'a+')as f:
   with _locked(f):
    _,r,s=self._read(f)
    if reservation_id not in r or reservation_id in s:raise BudgetExceeded('Missing or duplicate reservation')
    self._append(f,{'event':'settle','reservation_id':reservation_id,'charged_usd':actual,'ts':time.time(),'meta':meta or {}})
    if actual>r[reservation_id]+1e-12:raise BudgetExceeded('Actual charge exceeded reserved maximum; halt and audit')
