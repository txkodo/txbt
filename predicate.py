from pathlib import Path
from typing import Any, Literal
from datapack import IPredicate, Objective
from mcpath import McPath


class ExistPredicate(IPredicate):
  """
  すでに存在するpredicateを表すクラス

  他のデータパックのpredicateを使用する際等に用いる
  """
  def __init__(self, path: str|McPath ) -> None:
    super().__init__(path)

  def export(self,datapack_path:Path):
    pass

class EntityScores(IPredicate):
  def __init__(self,scores:dict[Objective,int|tuple[int|None,int|None]],entity:Literal['this','direct_killer','killer','killer_player']='this',path:str|McPath|None=None) -> None:
    super().__init__(path)
    self.entity = entity
    self.scores = scores

  def export_dict(self) -> dict[str,Any]:

    def value(value:int|tuple[int|None,int|None]):
      if isinstance(value,int):
        return value
      result:dict[str,int] = {}
      if isinstance(value[0],int):
        result['min'] = value[0]
      if isinstance(value[1],int):
        result['max'] = value[1]
      return result

    return {
      'condition':'entity_scores',
      'entity':self.entity,
      'scores':{ k.id: value(v) for k,v in self.scores.items()}
      }
