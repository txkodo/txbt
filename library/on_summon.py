"""
新しく生成されたエンティティに対して発動するファンクションタグ #minecraft:summon を追加する
summonコマンド呼び出し直後(コマンドによって生成されたエンティティ)と、毎チックのはじめ(自然スポーンしたエンティティ)に対し実行する
"""
from library.on_install import OnInstall
from datapack import Command, ICommand, Function, FunctionTag, Selector

_summoned_tag = '__summon__'

OnSummon = FunctionTag('#minecraft:summon')
"""
召喚時トリガーのファンクションタグ
実行者は召喚されたエンティティ
"""

_general = Function()
OnSummon.append(_general)
_general += Command.Tag.Add(Selector.S(), _summoned_tag)

def accessor(cmd:ICommand):
  f = Function()
  f += cmd
  f += Selector.E(tag={_summoned_tag:False}).As().At(Selector.S()) + OnSummon.call()
  return f.Call()

Command.Summon.default_accessor = accessor

_tick = Function()
FunctionTag.tick.append(_tick)

_tick += Selector.E(tag={_summoned_tag:False}).As().At(Selector.S()) + OnSummon.call()

OnInstall.uninstall_func += Command.Tag.Remove(Selector.E(), _summoned_tag)
