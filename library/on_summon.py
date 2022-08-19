"""
新しく生成されたエンティティに対して発動するファンクションタグ #minecraft:summon を追加する
summonコマンド呼び出し直後(コマンドによって生成されたエンティティ)と、毎チックのはじめ(自然スポーンしたエンティティ)に対し実行する
"""

from typing import Any
from datapack import Command, ICommand, Selector, Function, FunctionTag, INbt, List, Position, Str, Value

_summoned_tag = '__summon__'
_on_summon_tag = '__on_summon__'

summon = FunctionTag('minecraft:summon')
"""
召喚時トリガーのファンクションタグ
実行者は召喚されたエンティティ
"""

_general = Function()
summon.append(_general)

_general += Command.Tag.Add(Selector.S(), _summoned_tag)
_general += Command.Tag.Remove(Selector.S(), _on_summon_tag)

SummonOld = Command.Summon

class Summon(ICommand):
  """
  summonコマンドを上書きする
  """
  def __new__(cls,type: str, pos: Position.IPosition, **nbt: Value[INbt]) -> ICommand:
    f = Function()
    if 'Tags' in nbt:
      tags = nbt['Tags']
      value: list[Value[Str]] = tags.value
      value.append(Str(_on_summon_tag))
    else:
      nbt['Tags'] = List[Str]([Str(_on_summon_tag)])

    f += SummonOld(type, pos, **nbt)
    f += Selector.E(tag=_on_summon_tag, limit=1).As().At(Selector.S()) + summon.call()
    return f.call()
  
  def __init__(self,*_:Any,**__:Any) -> None:
    super().__init__()

Command.Summon = Summon #type:ignore

_tick = Function()
FunctionTag.tick.append(_tick)

_tick += Selector.E(tag='!'+_summoned_tag).As().At(Selector.S()) + summon.call()
