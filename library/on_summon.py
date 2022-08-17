"""
新しく生成されたエンティティに対して発動するファンクションタグ #minecraft:summon を追加する
summonコマンド呼び出し直後(コマンドによって生成されたエンティティ)と、毎チックのはじめ(自然スポーンしたエンティティ)に対し実行する
"""

from datapack import Command, Selector, Function, FunctionTag, INbt, List, Position, Str, Value

_summoned_tag = '__summon__'
_on_summon_tag = '__on_summon__'

summon = FunctionTag('minecraft','summon')
"""
召喚時トリガーのファンクションタグ
実行者は召喚されたエンティティ
"""

_general = Function()
summon.append(_general)

_general += Command.Tag.Add(Selector.S(), _summoned_tag)
_general += Command.Tag.Remove(Selector.S(), _on_summon_tag)

def Summon(type: str, pos: Position.IPosition, **nbt: Value[INbt]):
  """
  summonコマンドを上書きする
  """
  f = Function()
  if 'Tags' in nbt:
    tags = nbt['Tags']
    value: list[Value[Str]] = tags.value
    value.append(Str(_on_summon_tag))
  else:
    nbt['Tags'] = List[Str]([Str(_on_summon_tag)])

  f += Command.Summon(type, pos, **nbt)
  f += Selector.E(tag=_on_summon_tag, limit=1).As().At(Selector.S()) + summon.call()
  return f.call()

Command.Summon = Summon

_tick = Function()
FunctionTag.tick.append(_tick)

_tick += Selector.E(tag='!'+_summoned_tag).As().At(Selector.S()) + summon.call()
