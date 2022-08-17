from __future__ import annotations
from abc import ABCMeta, abstractmethod
from copy import copy
from random import randint
from typing import Callable
from typing_extensions import Self
from datapack import Byte, Compound, Selector, ISelector, Int, Command, Function, Objective, StorageNbt, Value
from id import gen_id
from library.on_install import OnInstall

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

class ObjectiveIterator:
  unique:ObjectiveIterator
  main: ObjectiveIterator
  def __init__(self) -> None:
    self.index = -1
    self.objs: list[Objective] = []

  def rewind(self,index:int):
    assert -1 <= index < len(self.objs)
    self.index = index

  def __next__(self):
    self.index += 1
    if self.index == len(self.objs):
      obj = Objective(gen_id(prefix='txbt:'))
      OnInstall.install_func += obj.Add()
      OnInstall.uninstall_func += obj.Remove()
      self.objs.append(obj)
      return obj
    else:
      return self.objs[self.index]

ObjectiveIterator.unique = ObjectiveIterator()

_scopes_path = 'scopes'
_flags_path = 'flags'
_data_path = 'data'
_result_path = 'result'
_ticking_tag = 'txbt.tick'

class IEvent(metaclass=ABCMeta):
  _storage = StorageNbt("txbt:")
  scopes = _storage[_scopes_path]
  _result = _storage[_result_path,Byte]
  _data:Compound
  _flags:Compound
  id:str

  intidata = Function('txbt', 'init_unsafe', description='''txbtで生成されたストレージの内容を空にする。
データパックを再生成した際に実行することで、不要なデータを一掃できる。
イベントの実行中に起動すると壊れるので実行するときは気を付けること。''')
  intidata += _storage[_data_path].remove()
  intidata += _storage[_flags_path].remove()
  intidata += _storage[_scopes_path].remove()

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
  def state_server(self):
    return IEvent._flags[self.id,Byte]

  @property
  def tag_entity(self):
    return 'txbt:' + self.id

  @property
  @abstractmethod
  def isInfinite(self) -> bool:pass

  def _export_server(self, func: Function,abort:Function,init:Function, resultless:bool) -> Function:
    self.id = IEvent.nextId()
    _abort = Function(commands=[self.state_server.remove()])
    abort += self.state_server.isMatch(Byte(-1)) + _abort.call()
    func += self.state_server.set(Byte(-1))
    exit = self.main_server_with_state(func,_abort,init,resultless)
    exit += self.state_server.remove()
    return exit

  def main_server_with_state(self,func:Function,abort:Function,init:Function,resultless:bool) -> Function:
    exit, result = self.main_server(func, abort, init, resultless)
    if result is not None:
      if not resultless:
        exit += IEvent._result.set(result)
    return exit

  @abstractmethod
  def main_server(self,func:Function,abort:Function,init:Function,resultless:bool) -> tuple[Function,Byte|Value[Byte]|None]:
    pass

  def export_server(self,enter_path:str):
    id = IEvent.nextId()

    IEvent._data = IEvent._storage[_data_path][id]
    IEvent._flags = IEvent._storage[_flags_path][id]

    enter_namespace,enter_name = splitMcpath(enter_path,True)

    main = Function(enter_namespace,enter_name+"start")
    main.description = """イベントを初期化して開始する"""

    abort = Function(enter_namespace,enter_name+"abort")

    init = Function(enter_namespace,enter_name+"init")
    init.description = """イベントを初期化する"""

    _init = Function()

    _main = Function()
    _main += _init.call()

    abort.description = """イベントを中断する"""
    exit = self._export_server(_main, abort, _init, True)

    main += self.state_server.notMatch(Byte(-1)) + _main.call()
    init += self.state_server.notMatch(Byte(-1)) + _init.call()

    exit += IEvent._data.remove()
    exit += IEvent._flags.remove()
 
  def _export_entity(self, func: Function, abort: Function, tick: Function, init: Function, selector:ISelector, resultless: bool) -> Function:
    self.id = IEvent.nextId()
    _abort = Function(commands=[Command.Tag.Remove(Selector.S(),self.tag_entity)])
    abort += Selector.S(tag=self.tag_entity).IfEntity() + _abort.call()
    func += Command.Tag.Add(Selector.S(), self.tag_entity)
    _tick = Function()
    tick += Selector.S(tag=self.tag_entity).IfEntity() + _tick.call()
    exit = self.main_entity_with_state(func, _abort, _tick, init, selector, resultless)
    exit += Command.Tag.Remove(Selector.S(), self.tag_entity)
    return exit

  def main_entity_with_state(self, func: Function, abort: Function, tick: Function, init: Function, selector: ISelector, resultless: bool) -> Function:
    exit, result = self.main_entity(func, abort, tick, init, selector, resultless)
    if result is not None:
      if not resultless:
        exit += IEvent._result.set(result)
    return exit

  @abstractmethod
  def main_entity(self, func: Function, abort: Function, tick: Function, init: Function, selector: ISelector, resultless: bool) -> tuple[Function, Byte | Value[Byte] | None]:
    pass

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
  def __init__(self,*commands:Command|str) -> None:
    self.commands = [command if isinstance(command,Command) else Command(command) for command in commands]
    super().__init__()

  def _export_server(self, func: Function, abort: Function, init: Function, resultless: bool) -> Function:
    self.id = IEvent.nextId()
    func.append(*self.commands[:-1])
    if resultless:
      func += self.commands[-1]
    else:
      func += IEvent._result.storeResult(1) + self.commands[-1]
    func += self.state_server.remove()
    return func

  def main_server(self, func: Function,abort:Function,init:Function,resultless:bool) -> tuple[Function, Byte | Value[Byte] | None]:
    raise NotImplementedError

  def _export_entity(self, func: Function, abort: Function, tick: Function, init: Function, selector: ISelector, resultless: bool) -> Function:
    self.id = IEvent.nextId()
    func.append(*self.commands[:-1])
    if resultless:
      func += self.commands[-1]
    else:
      func += IEvent._result.storeResult(1) + self.commands[-1]
    func += self.state_server.remove()
    return func

  def main_entity(self, func: Function, abort: Function, tick: Function, init: Function, selector: ISelector, resultless: bool) -> tuple[Function, Byte | Value[Byte] | None]:
    raise NotImplementedError

  @property
  def isInfinite(self) -> bool: return False

class Wait(IEvent):
  """指定tick待機して成功"""
  def __init__(self,tick:int) -> None:
    assert 0 < tick
    self.tick = tick
    super().__init__()

  def main_server_with_state(self, func: Function, abort: Function, init: Function, resultless: bool) -> Function:
    exit = Function()
    abort += exit.clear_schedule()
    func += self.state_server.storeSuccess(-1) + exit.schedule(self.tick)
    if not resultless:
      exit += IEvent._result.set(Byte(1))
    return exit

  def main_server(self, func: Function, abort: Function, init: Function, resultless: bool) -> tuple[Function, Byte | Value[Byte] | None]:
    raise NotImplementedError

  def main_entity_with_state(self, func: Function, abort: Function, tick: Function, init: Function, selector: ISelector, resultless: bool) -> Function:
    self.id = IEvent.nextId()
    func += Command.Tag.Add(Selector.S(), _ticking_tag)
    abort += Command.Tag.Remove(Selector.S(), _ticking_tag)
    exit = Function()
    if self.tick == 1:
      exit.call()
    else:
      obj = next(ObjectiveIterator.main)
      init += obj.Add()
      OnInstall.uninstall_func += obj.Remove()
      score = obj.score(Selector.S())
      func += score.Set(self.tick)
      tick += score.Remove(1)
      tick += score.IfMatch(0) + exit.call()
      exit += score.Reset()
    if not resultless:
      exit += IEvent._result.set(Byte(1))
    exit += Command.Tag.Remove(Selector.S(), _ticking_tag)
    return exit

  def main_entity(self, func: Function, abort: Function, tick: Function, init: Function, selector: ISelector, resultless: bool) -> tuple[Function, Byte | Value[Byte] | None]:
    raise NotImplementedError

  @property
  def isInfinite(self) -> bool: return False

class WaitFunctionCall(IEvent):
  """ファンクションが実行されるまで待機して成功"""
  _funcmap:dict[str,Function] = {}

  def __init__(self,func:Function) -> None:
    super().__init__()
    self.trigger = func

  def main_server(self, func: Function,abort:Function,init:Function,resultless:bool) -> tuple[Function, Byte | Value[Byte] | None]:
    exit = Function()
    self.trigger += self.state_server.isMatch(Byte(-1)) + exit.call()
    return exit,Byte(1)

  def main_entity(self, func: Function, abort: Function, tick: Function, init: Function, selector: ISelector, resultless: bool) -> tuple[Function, Byte | Value[Byte] | None]:
    exit = Function()
    self.trigger += selector.merge(Selector.E(tag=self.tag_entity)).As().At(Selector.S()) + exit.call()
    func += Command.Tag.Add(Selector.S(), _ticking_tag)
    abort += Command.Tag.Remove(Selector.S(), _ticking_tag)
    exit += Command.Tag.Remove(Selector.S(), _ticking_tag)
    return exit, Byte(1)

  @property
  def isInfinite(self) -> bool: return False

class WaitWhile(IEvent):
  """コマンドが成功しなくなるまで待機して失敗を返す"""
  _funcmap:dict[str,Function] = {}

  def __init__(self,condition:Command) -> None:
    super().__init__()
    self.condition = condition

  def main_server(self, func: Function,abort:Function,init:Function,resultless:bool) -> tuple[Function, Byte | Value[Byte] | None]:
    enter = Function()
    exit = Function()

    data = IEvent._data[self.id]

    abort += enter.clear_schedule()
    abort += data.remove()

    func += enter.call()

    rlt = data["_",Byte]
    enter += rlt.storeSuccess(1) + self.condition
    enter += rlt.isMatch(Byte(0)) + exit.call()
    enter += rlt.isMatch(Byte(1)) + enter.schedule(1)

    exit += data.remove()
    return exit,Byte(0)

  def main_entity(self, func: Function, abort: Function, tick: Function, init: Function, selector: ISelector, resultless: bool) -> tuple[Function, Byte | Value[Byte] | None]:

    func += Command.Tag.Add(Selector.S(), _ticking_tag)
    abort += Command.Tag.Remove(Selector.S(), _ticking_tag)

    enter = Function()
    exit = Function()

    abort += enter.clear_schedule()
    func += enter.call()

    enter += IEvent._result.storeResult(1) + self.condition

    enter += IEvent._result.isMatch(Byte(0)) + exit.call()
    enter += Selector.S(tag=self.tag_entity).IfEntity() + IEvent._result.isMatch(Byte(1)) + enter.schedule(1)
    
    exit += Command.Tag.Remove(Selector.S(), _ticking_tag)
    return exit,Byte(0)

  @property
  def isInfinite(self) -> bool: return False

class WaitUntil(IEvent):
  """コマンドが成功するまで待機して成功を返す"""
  _funcmap:dict[str,Function] = {}

  def __init__(self,condition:Command) -> None:
    super().__init__()
    self.condition = condition

  def main_server(self, func: Function, abort: Function, init: Function, resultless: bool) -> tuple[Function, Byte | Value[Byte] | None]:
    enter = Function()
    exit = Function()

    data = IEvent._data[self.id]
    abort += enter.clear_schedule()
    abort += data.remove()

    func += enter.call()

    rlt = data["_",Byte]
    enter += rlt.storeSuccess(1) + self.condition
    enter += rlt.isMatch(Byte(1)) + exit.call()
    enter += rlt.isMatch(Byte(0)) + enter.schedule(1)

    exit += data.remove()
    return exit,Byte(1)

  def main_entity(self, func: Function, abort: Function, tick: Function, init: Function, selector: ISelector, resultless: bool) -> tuple[Function, Byte | Value[Byte] | None]:

    func += Command.Tag.Add(Selector.S(), _ticking_tag)
    abort += Command.Tag.Remove(Selector.S(), _ticking_tag)

    enter = Function()
    exit = Function()

    abort += enter.clear_schedule()
    func += enter.call()

    enter += IEvent._result.storeResult(1) + self.condition

    enter += IEvent._result.isMatch(Byte(1)) + exit.call()
    enter += Selector.S(tag=self.tag_entity).IfEntity() + IEvent._result.isMatch(Byte(0)) + enter.schedule(1)
    exit += Command.Tag.Remove(Selector.S(), _ticking_tag)
    return exit, Byte(0)

  @property
  def isInfinite(self) -> bool: return False



class IDecorator(IEvent,metaclass=ABCMeta):
  def __init__(self,sub:IEvent) -> None:
    self.sub = sub
    super().__init__()


class LoopWhile(IDecorator):
  """子イベントが失敗するまで実行を繰り返して失敗"""

  def main_server(self, func: Function, abort: Function, init: Function, resultless: bool) -> tuple[Function, Byte | Value[Byte] | None]:
    if self.sub.isInfinite:
      # 子イベントがinfiniteの場合繰り返す必要なし
      return self.sub._export_server(func, abort, init, True), None

    exit = Function()
    enter = Function()

    func += enter.call()

    func = self.sub._export_server(enter,abort,init,False)
    func += IEvent._result.isMatch(Byte(0)) + exit.call()
    func += self.state_server.isMatch(Byte(-1)) + IEvent._result.isMatch(Byte(1)) + enter.call()

    return exit,Byte(0)

  def main_entity(self, func: Function, abort: Function, tick: Function, init: Function, selector: ISelector, resultless: bool) -> tuple[Function, Byte | Value[Byte] | None]:

    if self.sub.isInfinite:
      # 子イベントがinfiniteの場合繰り返す必要なし
      return self.sub._export_entity(func, abort, tick, init, selector,True), None

    exit = Function()
    enter = Function()

    func += enter.call()

    func = self.sub._export_entity(func, abort, tick, init, selector, False)
    func += IEvent._result.isMatch(Byte(0)) + exit.call()
    func += Selector.S(tag=self.tag_entity).IfEntity() + IEvent._result.isMatch(Byte(1)) + enter.call()

    return exit, Byte(0)


  @property
  def isInfinite(self) -> bool: return self.sub.isInfinite

class LoopUntil(IDecorator):
  """子イベントが成功するまで実行を繰り返して成功"""

  def main_server(self, func: Function, abort: Function, init: Function, resultless: bool) -> tuple[Function, Byte | Value[Byte] | None]:

    if self.sub.isInfinite:
      # 子イベントがinfiniteの場合繰り返す必要なし
      return self.sub._export_server(func, abort, init, True),None

    exit = Function()
    enter = Function()

    func += enter.call()

    func = self.sub._export_server(enter,abort,init,False)
    func += IEvent._result.isMatch(Byte(1)) + exit.call()
    func += self.state_server.isMatch(Byte(-1)) + IEvent._result.isMatch(Byte(0)) + enter.call()

    return exit,Byte(1)

  def main_entity(self, func: Function, abort: Function, tick: Function, init: Function, selector: ISelector, resultless: bool) -> tuple[Function, Byte | Value[Byte] | None]:

    if self.sub.isInfinite:
      # 子イベントがinfiniteの場合繰り返す必要なし
      return self.sub._export_entity(func, abort, tick, init, selector, True), None

    exit = Function()
    enter = Function()

    func += enter.call()

    func = self.sub._export_entity(func, abort, tick, init, selector, False)
    func += IEvent._result.isMatch(Byte(1)) + exit.call()
    func += Selector.S(tag=self.tag_entity).IfEntity() + IEvent._result.isMatch(Byte(0)) + enter.call()

    return exit, Byte(0)

  @property
  def isInfinite(self) -> bool: return self.sub.isInfinite

class LoopInfinit(IDecorator):
  """子イベントを無限に繰り返す"""

  def main_server(self, func: Function, abort: Function, init: Function, resultless: bool) -> tuple[Function, Byte | Value[Byte] | None]:
    exit = Function()
    enter = Function()

    func += enter.call()
    func = self.sub._export_server(enter,abort,init,True)
    func += enter.call()
    return exit,None

  def main_entity(self, func: Function, abort: Function, tick: Function, init: Function, selector: ISelector, resultless: bool) -> tuple[Function, Byte | Value[Byte] | None]:
    exit = Function()
    enter = Function()

    func += enter.call()
    func = self.sub._export_entity(func, abort, tick, init, selector, True)
    func += enter.call()
    return exit,None

  @property
  def isInfinite(self) -> bool: return True

class IWrapper(IDecorator):
  """子イベントの実行をラップするだけでそれ自体はイベントにならないデコレータ"""
  def _export_server(self, func: Function, abort: Function, init: Function,resultless:bool) -> Function:
    exit = self.sub._export_server(func, abort, init, resultless)
    self.id = self.sub.id
    return exit

  def _export_entity(self, func: Function, abort: Function, tick: Function, init: Function, selector: ISelector, resultless: bool) -> Function:
    exit = self.sub._export_entity(func, abort, tick, init, selector, True)
    self.id = self.sub.id
    return exit

  def main_server(self, func: Function, abort: Function, init: Function, resultless: bool) -> tuple[Function, Byte | Value[Byte] | None]:
    raise NotImplementedError

  def main_entity(self, func: Function, abort: Function, tick: Function, init: Function, selector: ISelector, resultless: bool) -> tuple[Function, Byte | Value[Byte] | None]:
    raise NotImplementedError

  @property
  def isInfinite(self) -> bool: return self.sub.isInfinite

class Invert(IWrapper):
  """
  子要素の実行結果を反転するデコレータ

  `~`演算子と等価
  """
  def _export_server(self, func: Function, abort: Function, init: Function,resultless:bool) -> Function:
    if resultless:
      return super()._export_server(func, abort, init, True)
    else:
      exit = super()._export_server(func, abort, init, False)
      exit += IEvent._result.storeSuccess(1) + IEvent._result.isMatch(Byte(0))
      return exit

  def _export_entity(self, func: Function, abort: Function, tick: Function, init: Function, selector: ISelector, resultless: bool) -> Function:
    if resultless:
      return super()._export_entity(func, abort, tick, init, selector, True)
    else:
      exit = super()._export_entity(func, abort, tick, init, selector, False)
      exit += IEvent._result.storeSuccess(1) + IEvent._result.isMatch(Byte(0))
      return exit

class Infinit(IWrapper):
  """
  実行が終わっても終了しないデコレータ
  """
  def _export_server(self, func: Function, abort: Function, init: Function, resultless:bool) -> Function:
    super()._export_server(func, abort, init, True)
    return Function()

  def _export_entity(self, func: Function, abort: Function, tick: Function, init: Function, selector: ISelector, resultless: bool) -> Function:
    super()._export_entity(func, abort, tick, init, selector, True)
    return Function()

  @property
  def isInfinite(self) -> bool: return True

class Success(IWrapper):
  """
  子要素が終了すると必ず成功を返すデコレータ
  """
  def _export_server(self, func: Function, abort: Function, init: Function, resultless:bool) -> Function:
    exit = super()._export_server(func, abort, init, True)
    if not resultless:
      exit += IEvent._result.set(Byte(1))
    return exit

  def _export_entity(self, func: Function, abort: Function, tick: Function, init: Function, selector: ISelector, resultless: bool) -> Function:
    exit = super()._export_entity(func, abort, tick, init, selector, True)
    if not resultless:
      exit += IEvent._result.set(Byte(1))
    return exit

class Failure(IWrapper):
  """
  子要素が終了すると必ず失敗を返すデコレータ
  """
  def _export_server(self, func: Function, abort: Function, init: Function, resultless:bool) -> Function:
    exit = super()._export_server(func, abort, init, True)
    if not resultless:
      exit += IEvent._result.set(Byte(0))
    return exit

  def _export_entity(self, func: Function, abort: Function, tick: Function, init: Function, selector: ISelector, resultless: bool) -> Function:
    exit = super()._export_entity(func, abort, tick, init, selector, True)
    if not resultless:
      exit += IEvent._result.set(Byte(0))
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

  def _export_server(self, func: Function, abort: Function, init: Function, resultless: bool) -> Function:
    exit = super()._export_server(func, abort, init, resultless)
    if self.init:
      init += self.init.call()
    if self.abort:
      abort += self.abort.call()
    return exit

  def _export_entity(self, func: Function, abort: Function, tick: Function, init: Function, selector: ISelector, resultless: bool) -> Function:
    exit = super()._export_entity(func, abort, tick, init, selector, True)
    if self.init:
      init += self.init.call()
    if self.abort:
      abort += self.abort.call()
    return exit

class Scope(IWrapper):
  """
  イベント専用の変数空間を提供する

  コンストラクタに(Compound -> IEvent)となる関数を渡すか、関数デコレータとして使用する
  """
  def __init__(self, gen: Callable[[Compound],IEvent]) -> None:
    self.gen = gen
    super(IEvent).__init__()

  def _export_server(self, func: Function, abort: Function, init: Function, resultless: bool) -> Function:
    scope = IEvent.scopes[IEvent.nextId()]
    self.sub = self.gen(scope)
    func += scope.remove()
    return super()._export_server(func, abort, init, resultless)

  def _export_entity(self, func: Function, abort: Function, tick: Function, init: Function, selector: ISelector, resultless: bool) -> Function:
    scope = IEvent.scopes[IEvent.nextId()]
    self.sub = self.gen(scope)
    func += scope.remove()
    return super()._export_entity(func, abort, tick, init, selector, True)

  @property
  def isInfinite(self) -> bool:
    return False

class IComposit(IEvent,metaclass=ABCMeta):
  def __init__(self,*subs:IEvent) -> None:
    self.subs = [*subs]
    super().__init__()

  def _export_server(self, func: Function, abort: Function, init: Function, resultless: bool) -> Function:
    if not self.subs:
      raise IndexError("cannot export empty composit")
    return super()._export_server(func, abort, init, resultless)

  def _export_entity(self, func: Function, abort: Function, tick: Function, init: Function, selector: ISelector, resultless: bool) -> Function:
    if not self.subs:
      raise IndexError("cannot export empty composit")
    return super()._export_entity(func, abort, tick, init, selector, True)

class Traverse(IComposit):
  """成否にかかわらず最後まで順番に実行し、最後の結果を返す
  `+`演算子と等価
  """
  def __init__(self, *subs: IEvent) -> None:
    super().__init__(*subs)

  def main_server(self, func: Function,abort:Function,init:Function, resultless:bool) -> tuple[Function, Byte | Value[Byte] | None]:
    for sub in self.subs[:-1]:
      if sub.isInfinite:
        return sub._export_server(func,abort,init,True),None
      func = sub._export_server(func,abort,init,True)

    sub = self.subs[-1]
    if sub.isInfinite:
      return sub._export_server(func, abort, init, True), None
    func = sub._export_server(func,abort,init,resultless)

    return func,None

  def main_entity(self, func: Function, abort: Function, tick: Function, init: Function, selector: ISelector, resultless: bool) -> tuple[Function, Byte | Value[Byte] | None]:
    min_index = ObjectiveIterator.main.index
    max_index = min_index
    for sub in self.subs[:-1]:
      if sub.isInfinite:
        func = sub._export_entity(func, abort, tick, init, selector, True)
        max_index = max(max_index,ObjectiveIterator.main.index)
        ObjectiveIterator.main.rewind(max_index)
        return func, None
      func = sub._export_entity(func, abort, tick, init, selector, True)
      max_index = max(max_index,ObjectiveIterator.main.index)
      ObjectiveIterator.main.rewind(min_index)

    sub = self.subs[-1]
    if sub.isInfinite:
      func = sub._export_entity(func, abort, tick, init, selector, True)
      max_index = max(max_index,ObjectiveIterator.main.index)
      ObjectiveIterator.main.rewind(max_index)
      return func, None
    func = sub._export_entity(func, abort, tick, init, selector, resultless)

    max_index = max(max_index,ObjectiveIterator.main.index)
    ObjectiveIterator.main.rewind(max_index)

    return func, None



  @property
  def isInfinite(self) -> bool: return any(i.isInfinite for i in self.subs)


class All(IComposit):
  """
  成功し続ける限り順番に実行する
  """
  def __init__(self, *subs: IEvent) -> None:
    super().__init__(*subs)

  def main_server_with_state(self, func: Function, abort: Function, init: Function, resultless: bool) -> Function:
    fail = Function()
    exit = Function()
    for sub in self.subs[:-1]:
      if sub.isInfinite:
        return sub._export_server(func, abort, init, True)
      func = sub._export_server(func,abort,init,False)
      next = Function()
      func += IEvent._result.isMatch(Byte(0)) + fail.call()
      func += self.state_server.isMatch(Byte(-1)) + IEvent._result.isMatch(Byte(1)) + next.call()
      func = next

    sub = self.subs[-1]
    if sub.isInfinite:
      return sub._export_server(func,abort,init,True)
    func = sub._export_server(func,abort,init,resultless)

    if not resultless:
      fail += IEvent._result.set(Byte(0))

    fail += exit.call()
    func += exit.call()
    return exit

  def main_server(self, func: Function, abort: Function, init: Function, resultless: bool) -> tuple[Function, Byte | Value[Byte] | None]:
    raise NotImplementedError

  def main_entity_with_state(self, func: Function, abort: Function, tick: Function, init: Function, selector: ISelector, resultless: bool) -> Function:
    min_index = ObjectiveIterator.main.index
    max_index = min_index

    fail = Function()
    exit = Function()

    for sub in self.subs[:-1]:
      if sub.isInfinite:
        func = sub._export_entity(func, abort, tick, init, selector, True)
        max_index = max(max_index, ObjectiveIterator.main.index)
        ObjectiveIterator.main.rewind(max_index)
        return func
      func = sub._export_entity(func, abort, tick, init, selector, False)
      max_index = max(max_index, ObjectiveIterator.main.index)
      ObjectiveIterator.main.rewind(min_index)
      next = Function()
      func += IEvent._result.isMatch(Byte(0)) + fail.call()
      func += Selector.S(tag=self.tag_entity).IfEntity() + IEvent._result.isMatch(Byte(1)) + next.call()
      func = next

    sub = self.subs[-1]
    if sub.isInfinite:
      func = sub._export_entity(func, abort, tick, init, selector, True)
      max_index = max(max_index, ObjectiveIterator.main.index)
      ObjectiveIterator.main.rewind(max_index)
      return func
    func = sub._export_entity(func, abort, tick, init, selector, resultless)

    if not resultless:
      fail += IEvent._result.set(Byte(0))

    fail += exit.call()
    func += exit.call()
    max_index = max(max_index, ObjectiveIterator.main.index)
    ObjectiveIterator.main.rewind(max_index)
    return exit

  def main_entity(self, func: Function, abort: Function, tick: Function, init: Function, selector: ISelector, resultless: bool) -> tuple[Function, Byte | Value[Byte] | None]:
    raise NotImplementedError

  @property
  def isInfinite(self) -> bool: return self.subs[0].isInfinite

class Any(IComposit):
  """
  失敗し続ける限り順番に実行する
  """
  def __init__(self, *subs: IEvent) -> None:
    super().__init__(*subs)

  def main_server_with_state(self, func: Function, abort: Function, init: Function, resultless: bool) -> Function:
    success = Function()
    exit = Function()

    for sub in self.subs[:-1]:
      if sub.isInfinite:
        return sub._export_server(func, abort, init, True)
      func = sub._export_server(func,abort,init,False)
      next = Function()
      func += IEvent._result.isMatch(Byte(1)) + success.call()
      func += IEvent._result.isMatch(Byte(0)) + next.call()
      func = next

    sub = self.subs[-1]
    if sub.isInfinite:
      return sub._export_server(func, abort, init, True)
    func = sub._export_server(func,abort,init,resultless)

    if not resultless:
      success += IEvent._result.set(Byte(1))
    func += exit.call()
    success += exit.call()
    return exit

  def main_server(self, func: Function, abort: Function, init: Function, resultless: bool) -> tuple[Function, Byte | Value[Byte] | None]:
    raise NotImplementedError

  def main_entity_with_state(self, func: Function, abort: Function, tick: Function, init: Function, selector: ISelector, resultless: bool) -> Function:
    min_index = ObjectiveIterator.main.index
    max_index = min_index

    success = Function()
    exit = Function()
    for sub in self.subs[:-1]:
      if sub.isInfinite:
        func = sub._export_entity(func, abort, tick, init, selector, True)
        max_index = max(max_index, ObjectiveIterator.main.index)
        ObjectiveIterator.main.rewind(max_index)
        return func
      func = sub._export_entity(func, abort, tick, init, selector, False)
      max_index = max(max_index, ObjectiveIterator.main.index)
      ObjectiveIterator.main.rewind(min_index)
      next = Function()
      func += IEvent._result.isMatch(Byte(1)) + success.call()
      func += Selector.S(tag=self.tag_entity).IfEntity() + IEvent._result.isMatch(Byte(0)) + next.call()
      func = next

    sub = self.subs[-1]
    if sub.isInfinite:
      func = sub._export_entity(func, abort, tick, init, selector, True)
      max_index = max(max_index, ObjectiveIterator.main.index)
      ObjectiveIterator.main.rewind(max_index)
      return func
    func = sub._export_entity(func, abort, tick, init, selector, resultless)
    max_index = max(max_index, ObjectiveIterator.main.index)
    ObjectiveIterator.main.rewind(max_index)

    if not resultless:
      success += IEvent._result.set(Byte(1))

    success += exit.call()
    func += exit.call()
    return exit

  def main_entity(self, func: Function, abort: Function, tick: Function, init: Function, selector: ISelector, resultless: bool) -> tuple[Function, Byte | Value[Byte] | None]:
    raise NotImplementedError

  @property
  def isInfinite(self) -> bool: return self.subs[0].isInfinite

class ParallelTraverse(IComposit):
  """
  すべての子要素を並行して実行し、必ず成功を返す
  `&`演算子と等価
  """

  def main_server_with_state(self, func: Function, abort: Function, init: Function, resultless: bool):
    exit = Function()

    data = IEvent._data[self.id]
    abort += data.remove()

    if self.isInfinite:
      for sub in self.subs:
        end = sub._export_server(func, abort, init, True)
      return exit

    count = data["count",Int]
    func += count.set(Int(len(self.subs)))

    for sub in self.subs:
      end = sub._export_server(func,abort,init,True)
      end += count.storeResult(0.99999) + count.getValue()
      end += count.isMatch(Int(0)) + exit.call()

    if not resultless:
      exit +=  IEvent._result.set(Byte(1))
    exit += data.remove()
    return exit

  def main_server(self, func: Function, abort: Function, init: Function, resultless: bool) -> tuple[Function, Byte | Value[Byte] | None]:
    raise NotImplementedError

  def main_entity_with_state(self, func: Function, abort: Function, tick: Function, init: Function, selector: ISelector, resultless: bool) -> Function:
    exit = Function()

    if self.isInfinite:
      for sub in self.subs:
        end = sub._export_entity(func, abort, tick, init, selector, True)
      return exit
    
    score = next(ObjectiveIterator.main).score(Selector.S())
    func += score.Set(len(self.subs))

    for sub in self.subs:
      end = sub._export_entity(func, abort, tick, init, selector, True)
      end += score.Remove(1)
      end += score.IfMatch(0) + exit.call()

    if not resultless:
      exit += IEvent._result.set(Byte(1))
    return exit

  def main_entity(self, func: Function, abort: Function, tick: Function, init: Function, selector: ISelector, resultless: bool) -> tuple[Function, Byte | Value[Byte] | None]:
    raise NotImplementedError

  @property
  def isInfinite(self) -> bool: return any(sub.isInfinite for sub in self.subs)

class ParallelFirst(IComposit):
  """
  すべての子要素を並行して実行し、どれかが終了したら成功

  最初に終了した子要素の結果をそのまま返す
  
  `|`演算子と等価
  """

  def main_server_with_state(self, func: Function, abort: Function, init: Function, resultless: bool):
    exit = Function()

    abt = Function()
    for sub in self.subs:
      f = Function()
      func += self.state_server.isMatch(Byte(-1)) + f.call()
      end = sub._export_server(func,abt,init,resultless)
      if not sub.isInfinite:
        end += exit.call()

    abort += abt.call()

    if not self.isInfinite:
      exit += abt.call()

    return exit

  def main_server(self, func: Function, abort: Function, init: Function, resultless: bool) -> tuple[Function, Byte | Value[Byte] | None]:
    raise NotImplementedError

  def main_entity_with_state(self, func: Function, abort: Function, tick: Function, init: Function, selector: ISelector, resultless: bool) -> Function:
    exit = Function()

    abt = Function()
    for sub in self.subs:
      f = Function()
      func += Selector.S(tag=self.tag_entity).IfEntity() + f.call()
      end = sub._export_entity(func, abt, tick, init, selector, resultless)
      if not sub.isInfinite:
        end += exit.call()

    abort += abt.call()

    if not self.isInfinite:
      exit += abt.call()

    return exit

  def main_entity(self, func: Function, abort: Function, tick: Function, init: Function, selector: ISelector, resultless: bool) -> tuple[Function, Byte | Value[Byte] | None]:
    raise NotImplementedError

  @property
  def isInfinite(self) -> bool: return all(sub.isInfinite for sub in self.subs)

class ParallelAny(IComposit):
  """
  すべての子要素を並行して実行し、1つでも成功したら他すべて中断して成功、すべて失敗したら失敗
  """

  def main_server_with_state(self, func: Function, abort: Function, init: Function, resultless: bool):
    exit = Function()
    failure = Function()
    success = Function()
    data = IEvent._data[self.id]

    count = next(ObjectiveIterator.main).score(Selector.S())
    abort += data.remove()

    if not self.isInfinite:
      func += count.Set(len([sub for sub in self.subs if not sub.isInfinite]))

    abt = Function()
    for sub in self.subs:
      f = Function()
      func += Selector.S(tag=self.tag_entity).IfEntity() + f.call()
      end = sub._export_server(f,abt,init,False)
      if not sub.isInfinite:
        end += count.Remove(1)
        end += IEvent._result.isMatch(Byte(1)) + success.call()
        end += count.IfMatch(0) + IEvent._result.isMatch(Byte(0)) + failure.call()

    abort += abt.call()

    if self.isInfinite:
      return exit

    success += abt.call()

    if not resultless:
      failure += IEvent._result.set(Byte(0))
      success += IEvent._result.set(Byte(1))

    failure += exit.call()
    success += exit.call()

    exit += data.remove()
    return exit

  def main_server(self, func: Function, abort: Function, init: Function, resultless: bool) -> tuple[Function, Byte | Value[Byte] | None]:
    raise NotImplementedError

  def main_entity_with_state(self, func: Function, abort: Function, tick: Function, init: Function, selector: ISelector, resultless: bool) -> Function:
    exit = Function()
    failure = Function()
    success = Function()
    count = next(ObjectiveIterator.main).score(Selector.S())

    if not self.isInfinite:
      func += count.Set(len([sub for sub in self.subs if not sub.isInfinite]))

    abt = Function()
    for sub in self.subs:
      f = Function()
      func += Selector.S(tag=self.tag_entity).IfEntity() + f.call()
      end = sub._export_server(f, abt, init, False)
      if not sub.isInfinite:
        end += count.Remove(1)
        end += IEvent._result.isMatch(Byte(1)) + success.call()
        end += count.IfMatch(0) + IEvent._result.isMatch(Byte(0)) + failure.call()

    abort += abt.call()

    if self.isInfinite:
      return exit

    success += abt.call()

    if not resultless:
      failure += IEvent._result.set(Byte(0))
      success += IEvent._result.set(Byte(1))

    failure += exit.call()
    success += exit.call()
    return exit

  def main_entity(self, func: Function, abort: Function, tick: Function, init: Function, selector: ISelector, resultless: bool) -> tuple[Function, Byte | Value[Byte] | None]:
    raise NotImplementedError

  @property
  def isInfinite(self) -> bool: return all(sub.isInfinite for sub in self.subs)


class ParallelAll(IComposit):
  """
  すべての子要素を並行して実行し、1つでも失敗したら他すべて中断して失敗、すべて成功したら成功
  """

  def main_server_with_state(self, func: Function, abort: Function, init: Function, resultless: bool):
    exit = Function()
    success = Function()
    failure = Function()
    data = IEvent._data[self.id]
    count = data["count",Int]
    abort += data.remove()

    if not self.isInfinite:
      func += count.set(Int(len([sub for sub in self.subs if not sub.isInfinite])))

    abt = Function()
    for sub in self.subs:
      f = Function()
      func += self.state_server.isMatch(Byte(-1)) + f.call()
      end = sub._export_server(func,abt,init,False)
      if not sub.isInfinite:
        end += count.storeResult(0.99999) + count.getValue()
        end += IEvent._result.isMatch(Byte(0)) + failure.call()
        end += count.isMatch(Int(0)) + IEvent._result.isMatch(Byte(1)) + success.call()

    abort += abt.call()
    if self.isInfinite:
      return exit

    failure += abt.call()

    if not resultless:
      success += IEvent._result.set(Byte(1))
      failure += IEvent._result.set(Byte(0))
    success += exit.call()
    failure += exit.call()

    exit += data.remove()
    return exit

  @property
  def isInfinite(self) -> bool: return all(sub.isInfinite for sub in self.subs)

  def main_server(self, func: Function, abort: Function, init: Function, resultless: bool) -> tuple[Function, Byte | Value[Byte] | None]:
    raise NotImplementedError

  def main_entity_with_state(self, func: Function, abort: Function, tick: Function, init: Function, selector: ISelector, resultless: bool) -> Function:
    exit = Function()
    success = Function()
    failure = Function()
    count = next(ObjectiveIterator.main).score(Selector.S())

    if not self.isInfinite:
      func += count.Set(len([sub for sub in self.subs if not sub.isInfinite]))

    abt = Function()
    for sub in self.subs:
      f = Function()
      func += Selector.S(tag=self.tag_entity).IfEntity() + f.call()
      end = sub._export_server(func, abt, init, False)
      if not sub.isInfinite:
        end += count.Remove(1)
        end += IEvent._result.isMatch(Byte(0)) + failure.call()
        end += count.IfMatch(0) + IEvent._result.isMatch(Byte(1)) + success.call()

    abort += abt.call()
    if self.isInfinite:
      return exit

    failure += abt.call()

    if not resultless:
      success += IEvent._result.set(Byte(1))
      failure += IEvent._result.set(Byte(0))
    success += exit.call()
    failure += exit.call()

    return exit

  def main_entity(self, func: Function, abort: Function, tick: Function, init: Function, selector: ISelector, resultless: bool) -> tuple[Function, Byte | Value[Byte] | None]:
    raise NotImplementedError
