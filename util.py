from decimal import Decimal
from random import randint


def float_to_str(f:float):
  return format(Decimal.from_float(f),'f')

_id_upper  = tuple(map(chr,range(ord('A'),ord('Z')+1)))
_id_lower  = tuple(map(chr,range(ord('a'),ord('z')+1)))
_id_number = tuple(map(chr,range(ord('0'),ord('9')+1)))

def gen_id(length:int=8,prefix:str='',suffix:str='',upper:bool=True,lower:bool=True,number:bool=True):
  """{length=8}桁のIDを生成する [0-9a-zA-Z]"""
  chars:list[str] = []
  if upper :chars.extend(_id_upper)
  if lower :chars.extend(_id_lower)
  if number:chars.extend(_id_number)
  maxidx = len(chars) - 1
  return prefix + ''.join(chars[randint(0,maxidx)] for _ in range(length)) + suffix
