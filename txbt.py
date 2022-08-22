from __future__ import annotations
from abc import ABCMeta, abstractmethod
from copy import copy
from enum import Enum, auto
from random import randint
from typing_extensions import Self
from datapack import Byte, Command, Compound, ConditionSubCommand, FunctionTag, ICommand, OhMyDat, Scoreboard, ISelector, Function, Objective, StorageNbt, Value
from id import gen_id
from library.on_install import OnInstall
from mcpath import McPath


# class TxBtDat(IDatapackLibrary):
#   using = False

#   @classmethod
#   def install(cls, datapack_path: Path, datapack_id: str) -> None:
#     FunctionTag.load.append(ExistFunction('txbt_dat','sys/load'))
#     if not (datapack_path/'data/txbt_dat').exists():
#       print("installing txbt_dat")
#       cp = subprocess.run(['git', 'clone', 'https://github.com/txkodo/txbt_dat.git'],cwd=datapack_path/'data', encoding='utf-8', stderr=subprocess.PIPE)
#       if cp.returncode != 0:
#         raise ImportError(cp.stderr)
#       cls.rmtree(datapack_path/'data/txbt_dat/.git')

#   @classmethod
#   def uninstall(cls,datapack_path:Path) -> None:
#     if (datapack_path/'data/txbt_dat').exists():
#       print("uninstalling txbt_dat")
#       cls.rmtree(datapack_path/'data/txbt_dat')

#   @classmethod
#   def Please(cls):
#     cls.using = True
#     return Command('function #txbt_dat:please')

#   _storage = StorageNbt('txbt_dat:')
#   _data = _storage['_',List[List[List[List[List[List[List[List[Compound]]]]]]]]][-4][-4][-4][-4][-4][-4][-4][-4]
#   _scoreboard = Scoreboard(Objective('TxBtDatID'),Selector.Player('_'))

#   @property
#   @classmethod
#   def data(cls):
#     """エンティティごとのデータが格納されているstorage (Compound)"""
#     cls.using = True
#     return cls._data

def splitMcpath(mcpath:str,isdir:bool=False):
  """
    foo:bar -> foo bar/*
    foo: -> foo *
    :bar -> minecraft bar/*
    bar -> minecraft bar/*
    : -> minecraft *
  """

  enter_namespace,enter_name = mcpath.split(':') if ':' in mcpath else ("",mcpath)
  if not enter_namespace:enter_namespace = 'minecraft'
  if isdir and enter_name:enter_name += '/'
  return enter_namespace,enter_name

class ScoreboardIterator:
  unique:ScoreboardIterator
  main: ScoreboardIterator
  def __init__(self) -> None:
    self.index = -1
    self.head = -1
    self.scores: list[Scoreboard] = []

  def rewind(self,index:int):
    assert -1 <= index < len(self.scores)
    self.index = index

  def toHead(self):
    self.index = self.head

  def reset(self):
    self.index = -1
    self.head = -1

  def __next__(self):
    self.index += 1
    self.head = max(self.head,self.index)
    if self.index == len(self.scores):
      match IEvent.mode:
        case _ExportMode.ENTITY:
          obj = Objective(gen_id(prefix='txbt:'))
          score = obj.score(ISelector.S())
          OnInstall.install_func += obj.Add()
          OnInstall.uninstall_func += obj.Remove()
        case _ExportMode.SERVER:
          score = IEvent.objective.score(ISelector.Player(IEvent.nextId()))
      self.scores.append(score)
      return score
    else:
      return self.scores[self.index]

ScoreboardIterator.unique = ScoreboardIterator()

_data_path = 'data'
_flags_path = 'flags'
_result_path = 'result'
_temp_flag_path = 'tmp'
_ticking_tag = 'txbt.tick'

class _ExportMode(Enum):
  ENTITY = auto()
  SERVER = auto()

class IEvent(metaclass=ABCMeta):
  objective = Objective('txbt')
  _objective_tick = Objective('txbt.tick')

  OnInstall.install_func += objective.Add()
  OnInstall.install_func += _objective_tick.Add()

  OnInstall.uninstall_func += objective.Remove()
  OnInstall.uninstall_func += _objective_tick.Remove()

  mode:_ExportMode
  _storage = StorageNbt("txbt:")
  scopes = _storage[_data_path]
  _result = _storage[_result_path,Byte]
  _temp_flag = _storage[_temp_flag_path,Byte]
  _flags:Compound
  _abort:Function
  id:str

  intidata = Function('txbt:init_unsafe', description='''txbtで生成されたストレージの内容を空にする。
データパックを再生成した際に実行することで、不要なデータを一掃できる。
イベントの実行中に起動すると壊れるので実行するときは気を付けること。''')
  intidata += _storage[_flags_path].remove()
  intidata += _storage[_data_path].remove()

  _id_upper  = tuple(map(chr,range(ord('A'),ord('Z')+1)))
  _id_lower  = tuple(map(chr,range(ord('a'),ord('z')+1)))
  _id_number = tuple(map(chr,range(ord('0'),ord('9')+1)))
  _id_chars = _id_upper+_id_lower+_id_number
  _id_charsmax = len(_id_chars) - 1

  @staticmethod
  def nextId():
    """8桁のIDを生成する [0-9a-zA-Z]"""
    return ''.join(IEvent._id_chars[randint(0,IEvent._id_charsmax)] for _ in range(8))

  def __init__(self) -> None:
    pass

  @property
  def _state_server(self):
    return IEvent._flags[self.id,Byte]

  @property
  def _tag_entity(self):
    return 'txbt-' + self.id
  
  def getId(self):
    self.id = IEvent.nextId()

  @property
  def activate(self):
    match IEvent.mode:
      case _ExportMode.SERVER:
        return self._state_server.set(Byte(-1))
      case _ExportMode.ENTITY:
        return Command.Tag.Add(ISelector.S(),self._tag_entity)
  
  def getScore(self):
    return next(ScoreboardIterator.main)

  @property
  def deactivate(self):
    match IEvent.mode:
      case _ExportMode.SERVER:
        return self._state_server.remove()
      case _ExportMode.ENTITY:
        return Command.Tag.Remove(ISelector.S(), self._tag_entity)

  @property
  def isActive(self):
    match IEvent.mode:
      case _ExportMode.SERVER:
        return self._state_server.isMatch(Byte(-1))
      case _ExportMode.ENTITY:
        return ISelector.S(tag=self._tag_entity).IfEntity()

  @property
  def notActive(self):
    match IEvent.mode:
      case _ExportMode.SERVER:
        return self._state_server.notMatch(Byte(-1))
      case _ExportMode.ENTITY:
        return ISelector.S(tag=self._tag_entity).UnlessEntity()

  def setReturn(self,result:Value[Byte]):
    return IEvent._result.set(result)

  @property
  def storeReturn(self):
    return IEvent._result.storeResult(1)

  @property
  def succeed(self):
    return self.setReturn(Byte(1))

  @property
  def fail(self):
    return self.setReturn(Byte(0))

  @property
  def isFailed(self):
    return IEvent._result.isMatch(Byte(0))

  @property
  def isSucceeded(self):
    return IEvent._result.isMatch(Byte(1))
  
  untick = Function()
  untick += _objective_tick.score(ISelector.S()).Remove(1)
  untick += _objective_tick.score(ISelector.S()).IfMatch(0) + Command.Tag.Remove(ISelector.S(), _ticking_tag)

  def useTickTag(self,enter:Function,exit:Function,abort:Function):
    assert IEvent.mode is _ExportMode.ENTITY
    enter += Command.Tag.Add(ISelector.S(), _ticking_tag)
    enter += IEvent._objective_tick.score(ISelector.S()).Add(1)

    exit += IEvent.untick.Call()
    abort += IEvent.untick.Call()

  @property
  def hasTickTag(self):
    assert IEvent.mode is _ExportMode.ENTITY
    return ISelector.S(tag=_ticking_tag).IfEntity()

  @property
  @abstractmethod
  def isInfinite(self) -> bool:pass

  def _export(self, func: Function ,abort:Function, tick:Function, init:Function, resultless:bool) -> Function:
    self.getId()

    self._abort = Function()
    self._abort += self.deactivate
    abort += self.isActive + self._abort.Call()

    _tick = Function()
    tick += self.isActive + _tick.Call()

    func += self.activate

    exit = self.main(func,self._abort,_tick,init,resultless)
    exit += self.deactivate
    return exit

  def main(self,func:Function,abort:Function,tick: Function,init:Function,resultless:bool) -> Function:
    match IEvent.mode:
      case _ExportMode.ENTITY:
        return self.main_entity(func, abort, tick, init, resultless)
      case _ExportMode.SERVER:
        return self.main_server(func, abort, tick, init, resultless)

  def main_entity(self,func:Function,abort:Function,tick: Function,init:Function,resultless:bool) -> Function:
    raise NotImplementedError

  def main_server(self,func:Function,abort:Function,tick: Function,init:Function,resultless:bool) -> Function:
    raise NotImplementedError

  def export_server(self,enter_path:str|McPath):
    IEvent.mode = _ExportMode.SERVER
    ScoreboardIterator.main = ScoreboardIterator()

    enter_path = McPath(enter_path)

    eventid = IEvent.nextId()

    IEvent._flags = IEvent._storage[_flags_path][eventid]

    main = Function(enter_path/'start')
    main.description = """イベントを初期化して開始する"""

    abort = Function(enter_path/'abort')

    init = Function(enter_path/'init')
    init.description = """イベントを初期化する"""

    _init = Function()

    _main = Function()
    _main += _init.Call()

    tick = Function()
    FunctionTag.tick.append(tick)

    abort.description = """イベントを中断する"""
    exit = self._export(_main, abort, tick, _init, True)

    main += self.notActive + _main.Call()
    init += self.notActive + _init.Call()

    exit += IEvent._flags.remove()

  def export_entity(self,enter_path:str|McPath,objectiveIterator:ScoreboardIterator):
    IEvent.mode = _ExportMode.ENTITY
    ScoreboardIterator.main = objectiveIterator

    enter_path = McPath(enter_path)

    main = Function(enter_path/"start")
    main.description = """イベントを初期化して開始する
該当エンティティとして実行すること"""

    abort = Function(enter_path/"abort")

    init = Function(enter_path/"init")
    init.description = """イベントを初期化する
該当エンティティとして実行すること"""

    _init = Function()

    _main = Function()
    _main += _init.Call()

    tick = Function()
    FunctionTag.tick.append(tick)
    _tick = Function()

    tick += ISelector.E(tag=_ticking_tag).As().At(ISelector.S()) + _tick.Call()

    abort.description = """イベントを中断する
該当エンティティとして実行すること"""
    self._export(_main, abort, _tick, _init, True)

    main += self.notActive + _main.Call()
    init += self.notActive + _init.Call()

    del ScoreboardIterator.main

  def copy(self:Self) -> Self:
    if isinstance(self, IComposit):
      c = copy(self)
      c.subs = [*self.subs]
    else:
      c = copy(self)
    return c

  def __add__(self,other:IEvent):
    subs = [self,other]
    if isinstance(self,Traverse):
      subs[:1] = self.subs
    if isinstance(other,Traverse):
      subs[-1:] = other.subs
    return Traverse(*subs)

  def __and__(self,other:IEvent):
    subs = [self,other]
    if isinstance(self,ParallelTraverse):
      subs[:1] = self.subs
    if isinstance(other,ParallelTraverse):
      subs[-1:] = other.subs
    return ParallelTraverse(*subs)

  def __or__(self,other:IEvent):
    subs = [self,other]
    if isinstance(self,ParallelFirst):
      subs[:1] = self.subs
    if isinstance(other,ParallelFirst):
      subs[-1:] = other.subs
    return ParallelFirst(*subs)

  def __invert__(self):
    return self.invert()

  def invert(self):
    return Invert(self)

  def infinit(self):
    return Infinit(self)

  def always_success(self):
    return Success(self)

  def always_failure(self):
    return Failure(self)

class Run(IEvent):
  def __init__(self,*commands:ICommand) -> None:
    self.commands = commands
    super().__init__()

  def _export(self, func: Function, abort: Function, tick: Function, init: Function, resultless: bool) -> Function:
    self.getId()
    self._abort = Function()
    func.extend(self.commands[:-1])
    if resultless:
      func += self.commands[-1]
    else:
      func += IEvent._result.storeResult(1) + self.commands[-1]
    return func

  @property
  def isInfinite(self) -> bool: return False

class Wait(IEvent):
  """指定tick待機して成功"""
  def __init__(self,tick:int) -> None:
    assert 0 < tick
    self.tick = tick
    super().__init__()

  def main_server(self, func: Function, abort: Function, tick: Function, init: Function, resultless: bool) -> Function:
    exit = Function()
    abort += exit.clear_schedule()
    func += exit.schedule(self.tick)
    if not resultless:
      exit += self.succeed
    return exit

  def main_entity(self, func: Function, abort: Function, tick: Function, init: Function, resultless: bool) -> Function:
    exit = Function()
    self.useTickTag(func,exit,abort)
    if self.tick == 1:
      exit.Call()
    else:
      score = self.getScore()
      func += score.Set(self.tick)
      tick += score.Remove(1)
      tick += score.IfMatch(0) + exit.Call()
      exit += score.Reset()
    if not resultless:
      exit += self.succeed
    return exit

  @property
  def isInfinite(self) -> bool: return False

class WaitFunctionCall(IEvent):
  """ファンクションが実行されるまで待機して成功"""
  _funcmap:dict[str,Function] = {}

  def __init__(self,func:Function) -> None:
    super().__init__()
    self.trigger = func

  def main_server(self, func: Function, abort: Function, tick: Function, init: Function, resultless: bool) -> Function:
    exit = Function()
    self.trigger += self.isActive + exit.Call()
    exit += self.succeed
    return exit

  def main_entity(self, func: Function, abort: Function, tick: Function, init: Function, resultless: bool) -> Function:
    exit = Function()
    # TODO: selectorをentity_type等で絞っておくことで検索効率を上げる
    self.trigger += ISelector.E(tag=self._tag_entity).As().At(ISelector.S()) + exit.Call()
    exit += self.succeed
    return exit

  @property
  def isInfinite(self) -> bool: return False

class WaitWhile(IEvent):
  """コマンドが成功しなくなるまで待機して失敗を返す"""
  _funcmap:dict[str,Function] = {}

  def __init__(self,condition:ICommand|ConditionSubCommand,pre_commands:list[ICommand]=[],post_commands:list[ICommand]=[]) -> None:
    """
    コマンドが成功しなくなるまで待機して失敗を返す

    condition : 成功かどうかを確かめるコマンドor条件サブコマンド

    pre_commands : condition実行前に実行するコマンド(任意)

    post_commands : condition実行後に実行するコマンド(任意)
    """
    super().__init__()
    self.condition = condition
    self.pre = pre_commands
    self.post = post_commands

  def main_server(self, func: Function, abort: Function, tick: Function, init: Function, resultless: bool) -> Function:
    enter = Function()
    exit = Function()

    abort += enter.clear_schedule()
    func += enter.Call()

    enter.append(*self.pre)
    enter += IEvent._temp_flag.storeSuccess(1) + self.condition
    enter.append(*self.post)
    enter += IEvent._temp_flag.isMatch(Byte(0)) + exit.Call()
    enter += self.isActive + enter.schedule(1)

    if not resultless:
      exit += self.fail
    return exit

  def main_entity(self, func: Function, abort: Function, tick: Function, init: Function, resultless: bool) -> Function:
    exit = Function()
    self.useTickTag(func,exit,abort)

    enter = Function()

    abort += enter.clear_schedule()
    func += enter.Call()

    enter += IEvent._temp_flag.storeSuccess(1) + self.condition
    enter += IEvent._temp_flag.isMatch(Byte(0)) + exit.Call()
    enter += self.isActive + enter.schedule(1)

    if not resultless:
      exit += self.fail
    return exit

  @property
  def isInfinite(self) -> bool: return False

class WaitUntil(IEvent):
  """コマンドが成功するまで待機して成功を返す"""
  _funcmap:dict[str,Function] = {}

  def __init__(self,condition:ICommand|ConditionSubCommand,pre_commands:list[ICommand]=[],post_commands:list[ICommand]=[]) -> None:
    """
    コマンドが成功するまで待機して成功を返す

    `condition` : 成功かどうかを確かめるコマンドor条件サブコマンド

    `pre_commands` : condition実行前に実行するコマンド(任意)

    `post_commands` : condition実行後に実行するコマンド(任意)
    """
    super().__init__()
    self.condition = condition
    self.pre = pre_commands
    self.post = post_commands

  def main_server(self, func: Function, abort: Function, tick: Function, init: Function, resultless: bool) -> Function:
    enter = Function()
    exit = Function()

    abort += enter.clear_schedule()
    func += enter.Call()

    enter.append(*self.pre)
    enter += IEvent._temp_flag.storeSuccess(1) + self.condition
    enter.append(*self.post)
    enter += IEvent._temp_flag.isMatch(Byte(1)) + exit.Call()
    enter += self.isActive + enter.schedule(1)

    if not resultless:
      exit += self.fail
    return exit

  def main_entity(self, func: Function, abort: Function, tick: Function, init: Function, resultless: bool) -> Function:
    exit = Function()
    self.useTickTag(func,exit,abort)

    enter = Function()

    abort += enter.clear_schedule()
    func += enter.Call()

    enter += IEvent._temp_flag.storeSuccess(1) + self.condition
    enter += IEvent._temp_flag.isMatch(Byte(1)) + exit.Call()
    enter += self.isActive + enter.schedule(1)

    if not resultless:
      exit += self.fail
    return exit

  @property
  def isInfinite(self) -> bool: return False



class IDecorator(IEvent,metaclass=ABCMeta):
  def __init__(self,sub:IEvent) -> None:
    self.sub = sub
    super().__init__()


class LoopWhile(IDecorator):
  """子イベントが失敗するまで実行を繰り返して失敗"""

  def main(self, func: Function, abort: Function, tick: Function, init: Function, resultless: bool) -> Function:
    if self.sub.isInfinite:
      # 子イベントがinfiniteの場合繰り返す必要なし
      return self.sub._export(func, abort, tick, init, True)

    exit = Function()
    enter = Function()

    func += enter.Call()

    func = self.sub._export(enter, abort, tick, init,False)
    func += self.isFailed + exit.Call()
    func += self.isActive + enter.Call()

    return exit

  @property
  def isInfinite(self) -> bool: return self.sub.isInfinite

class LoopUntil(IDecorator):
  """子イベントが成功するまで実行を繰り返して成功"""

  def main(self, func: Function, abort: Function, tick: Function, init: Function, resultless: bool) -> Function:
    if self.sub.isInfinite:
      # 子イベントがinfiniteの場合繰り返す必要なし
      return self.sub._export(func, abort, tick, init, True)

    exit = Function()
    enter = Function()

    func += enter.Call()

    func = self.sub._export(enter, abort, tick, init,False)
    func += self.isSucceeded + exit.Call()
    func += self.isActive + enter.Call()
    return exit

  @property
  def isInfinite(self) -> bool: return self.sub.isInfinite

class LoopInfinit(IDecorator):
  """子イベントを無限に繰り返す"""

  def main(self, func: Function, abort: Function, tick: Function, init: Function, resultless: bool) -> Function:
    exit = Function()
    enter = Function()

    func += enter.Call()
    func = self.sub._export(enter,abort,tick,init,True)
    func += enter.Call()
    return exit

  @property
  def isInfinite(self) -> bool: return True

class IWrapper(IDecorator):
  """子イベントの実行をラップするだけでそれ自体はイベントにならないデコレータ"""
  def _export(self, func: Function, abort: Function, tick: Function, init: Function, resultless:bool) -> Function:
    exit = self.sub._export(func, abort, tick, init, resultless)
    self.id = self.sub.id
    self._abort = self.sub._abort
    return exit

  @property
  def isInfinite(self) -> bool: return self.sub.isInfinite

class Invert(IWrapper):
  """
  子要素の実行結果を反転するデコレータ

  `~`演算子と等価
  """
  def _export(self, func: Function, abort: Function, tick: Function, init: Function, resultless:bool) -> Function:
    if resultless:
      return super()._export(func, abort, tick, init, True)
    else:
      exit = super()._export(func, abort, tick, init, False)
      exit += self.storeReturn + self.isFailed
      return exit

class Infinit(IWrapper):
  """
  実行が終わっても終了しないデコレータ
  """
  def _export(self, func: Function, abort: Function, tick: Function, init: Function, resultless:bool) -> Function:
    super()._export(func, abort, tick, init, True)
    return Function()
    
  @property
  def isInfinite(self) -> bool: return True

class Success(IWrapper):
  """
  子要素が終了すると必ず成功を返すデコレータ
  """
  def _export(self, func: Function, abort: Function, tick: Function, init: Function, resultless:bool) -> Function:
    exit = super()._export(func, abort, tick, init, False)
    exit += self.succeed
    return exit

class Failure(IWrapper):
  """
  子要素が終了すると必ず失敗を返すデコレータ
  """
  def _export(self, func: Function, abort: Function, tick: Function, init: Function, resultless:bool) -> Function:
    exit = super()._export(func, abort, tick, init, False)
    exit += self.fail
    return exit

class InitAbort(IWrapper):
  """
  init / abort 時に任意のファンクションを実行するデコレータ

  ##### init: イベント初期化ファンクション(init.mcfunctionから呼ばれる)\n
  ##### abort: イベント中断ファンクション(イベントが中断される時に呼ばれる)\n
  """
  def __init__(self, sub: IEvent,init:Function|None = None,abort:Function|None = None) -> None:
    self.init = init
    self.abort = abort
    super().__init__(sub)

  def _export(self, func: Function, abort: Function, tick: Function, init: Function, resultless:bool) -> Function:
    if self.init:
      init += self.init.Call()
    exit = super()._export(func, abort, tick, init, False)
    if self.abort:
      self.sub._abort += self.abort.Call()
    return exit

# class Scope(IWrapper):
#   """
#   イベント専用の変数空間を提供する

#   コンストラクタに(Compound -> IEvent)となる関数を渡すか、関数デコレータとして使用する
#   """
#   def __init__(self, gen: Callable[[Compound],IEvent]) -> None:
#     self.gen = gen
#     super(IEvent).__init__()

#   def _export(self, func: Function, abort: Function, tick: Function, init: Function, resultless:bool) -> Function:
#     match IEvent.mode:
#       case _ExportMode.ENTITY:
#         return self._export_entity(func, abort, tick, init, resultless)
#       case _ExportMode.SERVER:
#         return self._export_server(func, abort, tick, init, resultless)

#   def _export_server(self, func: Function, abort: Function, tick: Function, init: Function, resultless:bool) -> Function:
#     scope = IEvent.scopes[IEvent.nextId()]
#     self.sub = self.gen(scope)
#     func += scope.remove()
#     return super()._export(func, abort, tick, init, resultless)

#   def _export_entity(self, func: Function, abort: Function, tick: Function, init: Function, resultless:bool) -> Function:
#     raise NotImplementedError

#   @property
#   def isInfinite(self) -> bool:
#     return False

class IComposit(IEvent,metaclass=ABCMeta):
  def __init__(self,*subs:IEvent) -> None:
    self.subs = [*subs]
    super().__init__()

  def _export(self, func: Function, abort: Function, tick: Function, init: Function, resultless: bool) -> Function:
    if not self.subs:
      raise IndexError("cannot export empty composit")
    return super()._export(func, abort, tick, init, resultless)

class Traverse(IComposit):
  """成否にかかわらず最後まで順番に実行し、最後の結果を返す
  `+`演算子と等価
  """
  def __init__(self, *subs: IEvent) -> None:
    super().__init__(*subs)

  def main(self, func: Function, abort: Function, tick: Function, init: Function, resultless: bool) -> Function:
    index = ScoreboardIterator.main.index
    for sub in self.subs[:-1]:
      if sub.isInfinite:
        func = sub._export(func,abort,tick,init,True)
        ScoreboardIterator.main.toHead()
        return func
      func = sub._export(func,abort,tick,init,True)
      ScoreboardIterator.main.rewind(index)

    sub = self.subs[-1]
    if sub.isInfinite:
      func = sub._export(func,abort,tick,init,True)
      ScoreboardIterator.main.toHead()
      return func

    func = sub._export(func,abort,tick,init,resultless)
    ScoreboardIterator.main.toHead()
    return func

  @property
  def isInfinite(self) -> bool: return any(i.isInfinite for i in self.subs)


class All(IComposit):
  """
  成功し続ける限り順番に実行する
  """
  def __init__(self, *subs: IEvent) -> None:
    super().__init__(*subs)

  def main(self, func: Function, abort: Function, tick: Function, init: Function, resultless: bool) -> Function:
    index = ScoreboardIterator.main.index
    fail = Function()
    exit = Function()
    for sub in self.subs[:-1]:
      if sub.isInfinite:
        func = sub._export(func, abort, tick,init, True)
        ScoreboardIterator.main.toHead()
        return func
      func = sub._export(func,abort,tick,init,False)
      ScoreboardIterator.main.rewind(index)
      next = Function()
      func += self.isFailed + fail.Call()
      func += self.isActive + next.Call()
      func = next

    sub = self.subs[-1]
    if sub.isInfinite:
      func = sub._export(func,abort,tick,init,True)
      ScoreboardIterator.main.toHead()
      return func
    func = sub._export(func,abort,tick,init,resultless)

    if not resultless:
      fail += self.fail

    fail += exit.Call()
    func += exit.Call()
    ScoreboardIterator.main.toHead()
    return exit

  @property
  def isInfinite(self) -> bool: return self.subs[0].isInfinite

class Any(IComposit):
  """
  失敗し続ける限り順番に実行する
  """
  def __init__(self, *subs: IEvent) -> None:
    super().__init__(*subs)

  def main(self, func: Function, abort: Function, tick: Function, init: Function, resultless: bool) -> Function:
    index = ScoreboardIterator.main.index
    succeed = Function()
    exit = Function()
    for sub in self.subs[:-1]:
      if sub.isInfinite:
        func = sub._export(func, abort, tick,init, True)
        ScoreboardIterator.main.toHead()
        return func
      func = sub._export(func,abort,tick,init,False)
      ScoreboardIterator.main.rewind(index)
      next = Function()
      func += self.isSucceeded + succeed.Call()
      func += self.isActive + next.Call()
      func = next

    sub = self.subs[-1]
    if sub.isInfinite:
      func = sub._export(func,abort,tick,init,True)
      ScoreboardIterator.main.toHead()
      return func
    func = sub._export(func,abort,tick,init,resultless)

    if not resultless:
      succeed += self.succeed

    succeed += exit.Call()
    func += exit.Call()
    ScoreboardIterator.main.toHead()
    return exit

  @property
  def isInfinite(self) -> bool: return self.subs[0].isInfinite

class ParallelTraverse(IComposit):
  """
  すべての子要素を並行して実行し、必ず成功を返す
  `&`演算子と等価
  """
  def main(self, func: Function, abort: Function, tick: Function, init: Function, resultless: bool) -> Function:
    exit = Function()
    
    if self.isInfinite:
      for sub in self.subs:
        end = sub._export(func, abort, tick, init, True)
      return exit

    score = self.getScore()
    abort += score.Reset()

    func += score.Set(len(self.subs))

    for sub in self.subs:
      end = sub._export(func, abort, tick, init, True)
      end += score.Remove(1)
      end += score.IfMatch(0) + exit.Call()

    if not resultless:
      exit += self.succeed
    exit += score.Reset()
    return exit

  @property
  def isInfinite(self) -> bool: return any(sub.isInfinite for sub in self.subs)

class ParallelFirst(IComposit):
  """
  すべての子要素を並行して実行し、どれかが終了したら成功

  最初に終了した子要素の結果をそのまま返す
  
  `|`演算子と等価
  """

  def main(self, func: Function, abort: Function, tick: Function, init: Function, resultless: bool) -> Function:
    exit = Function()

    abt = Function()
    for sub in self.subs:
      f = Function()
      func += self.isActive + f.Call()
      end = sub._export(func,abt,tick,init,resultless)
      if not sub.isInfinite:
        end += exit.Call()

    abort += abt.Call()

    if not self.isInfinite:
      exit += abt.Call()

    return exit

  @property
  def isInfinite(self) -> bool: return all(sub.isInfinite for sub in self.subs)

class ParallelAny(IComposit):
  """
  すべての子要素を並行して実行し、1つでも成功したら他すべて中断して成功、すべて失敗したら失敗
  """

  def main_entity(self, func: Function, abort: Function, tick: Function, init: Function, resultless: bool) -> Function:
    exit = Function()
    failure = Function()
    success = Function()

    count = self.getScore()

    if not self.isInfinite:
      func += count.Set(len([sub for sub in self.subs if not sub.isInfinite]))

    abt = Function()
    for sub in self.subs:
      f = Function()
      func += ISelector.S(tag=self._tag_entity).IfEntity() + f.Call()
      end = sub._export(f,abt,init,tick,False)
      if not sub.isInfinite:
        end += count.Remove(1)
        end += self.isSucceeded + success.Call()
        end += self.isActive + count.IfMatch(0) + failure.Call()

    abort += abt.Call()

    if self.isInfinite:
      return exit

    success += abt.Call()
    success += exit.Call()

    failure += exit.Call()

    return exit

  @property
  def isInfinite(self) -> bool: return all(sub.isInfinite for sub in self.subs)


class ParallelAll(IComposit):
  """
  すべての子要素を並行して実行し、1つでも失敗したら他すべて中断して失敗、すべて成功したら成功
  """

  def main_entity(self, func: Function, abort: Function, tick: Function, init: Function, resultless: bool) -> Function:
    exit = Function()
    failure = Function()
    success = Function()

    count = self.getScore()

    if not self.isInfinite:
      func += count.Set(len([sub for sub in self.subs if not sub.isInfinite]))

    abt = Function()
    for sub in self.subs:
      f = Function()
      func += ISelector.S(tag=self._tag_entity).IfEntity() + f.Call()
      end = sub._export(f,abt,init,tick,False)
      if not sub.isInfinite:
        end += count.Remove(1)
        end += self.isFailed + failure.Call()
        end += self.isActive + count.IfMatch(0) + success.Call()

    abort += abt.Call()

    if self.isInfinite:
      return exit

    success += exit.Call()

    failure += abt.Call()
    failure += exit.Call()

    return exit

  @property
  def isInfinite(self) -> bool: return all(sub.isInfinite for sub in self.subs)

def getGlobalScope():
  """
  サーバーイベント用の変数空間を提供する

  エンティティイベントで使うと変数がすべてのエンティティで共有される
  """
  return IEvent.scopes[IEvent.nextId()]

def getEntityScope():
  """
  エンティティイベント用の変数空間を提供する

  各エンティティの各イベントごとの変数空間となっているので衝突しない

  サーバーイベントで使うと壊れるので使わないこと
  """
  return OhMyDat.getData()['kdbt'][IEvent.nextId()]
