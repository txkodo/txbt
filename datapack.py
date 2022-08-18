from __future__ import annotations
from abc import ABCMeta, abstractmethod
from decimal import Decimal
from typing import Any, Callable, Generic, Literal, Protocol, TypeAlias, TypeGuard, TypeVar, final, get_args, overload, Union, runtime_checkable
from typing_extensions import Self
from enum import Enum, auto
import os
import json
from pathlib import Path
from random import randint
import re
import shutil
import subprocess

from mcpath import McPath

def _float_to_str(f:float):
  return format(Decimal.from_float(f),'f')

_id_upper  = tuple(map(chr,range(ord('A'),ord('Z')+1)))
_id_lower  = tuple(map(chr,range(ord('a'),ord('z')+1)))
_id_number = tuple(map(chr,range(ord('0'),ord('9')+1)))

def _gen_id(length:int=8,prefix:str='',suffix:str='',upper:bool=True,lower:bool=True,number:bool=True):
  """{length=8}桁のIDを生成する [0-9a-zA-Z]"""
  chars:list[str] = []
  if upper :chars.extend(_id_upper)
  if lower :chars.extend(_id_lower)
  if number:chars.extend(_id_number)
  maxidx = len(chars) - 1
  return prefix + ''.join(chars[randint(0,maxidx)] for _ in range(length)) + suffix

class Position:
  class IPosition(metaclass=ABCMeta):
    prefix:str
    x:float
    y:float
    z:float
    def __init__(self,x:float,y:float,z:float) -> None:
      self.x = x
      self.y = y
      self.z = z

    def __str__(self):
      return self.expression()

    @classmethod
    def origin(cls):
      return cls(0,0,0)
    
    def tuple(self):
      return (self.x,self.y,self.z)

    def expression(self):
      def expr(value:float):
        v = "" if self.prefix and value == 0 else str(value)
        return self.prefix + v
      return f'{expr(self.x)} {expr(self.y)} {expr(self.z)}'

    def Positioned(self):
      return SubCommand(f"positioned {self.expression()}")

    def IfBlock(self,block:Block):
      return ConditionSubCommand(f"if block {self.expression()} {block.expression()}")

    def UnlessBlock(self,block:Block):
      return ConditionSubCommand(f"unless block {self.expression()} {block.expression()}")
    
    def Facing(self):
      return SubCommand(f"facing {self.expression()}")

    def Nbt(self):
      return BlockNbt(self)
    
    def __add__(self,diff:tuple[float,float,float]):
      return self.__class__(self.x+diff[0],self.y+diff[1],self.z+diff[2])

    def __iadd__(self,diff:tuple[float,float,float]):
      self.x+=diff[0]
      self.y+=diff[1]
      self.z+=diff[2]
      return self

    def __sub__(self,diff:tuple[float,float,float]):
      return self.__class__(self.x-diff[0],self.y-diff[1],self.z-diff[2])

    def __isub__(self,diff:tuple[float,float,float]):
      self.x-=diff[0]
      self.y-=diff[1]
      self.z-=diff[2]
      return self

    def __neg__(self):
      return self.__class__(-self.x,-self.y,-self.z)

  class Local(IPosition):
    """^x ^y ^z"""
    prefix = "^"

  class World(IPosition):
    """x y z"""
    prefix = ""

  class Relative(IPosition):
    """~x ~y ~z"""
    prefix = "~"



class SubCommand:
  """ at / positioned / in / as / rotated / store ..."""
  def __init__(self,content:str|None=None) -> None:
    self.subcommands:list[str] = []
    if content is not None:
      self.subcommands.append( content )

  @overload
  def __add__(self,other:ConditionSubCommand) -> ConditionSubCommand:pass
  
  @overload
  def __add__(self,other:SubCommand) -> SubCommand:pass

  @overload
  def __add__(self,other:Command) -> Command:pass
  
  def __add__(self,other:SubCommand|Command):
    if isinstance(other,ConditionSubCommand):
      result = ConditionSubCommand()
      result.subcommands.extend(self.subcommands)
      result.subcommands.extend(other.subcommands)
      return result
    elif isinstance(other,SubCommand):
      result = SubCommand()
      result.subcommands.extend(self.subcommands)
      result.subcommands.extend(other.subcommands)
      return result
    elif isinstance(other,_FunctionCommand):
      result = _FunctionCommand(other.holder)
      result.subcommands.extend(self.subcommands)
      result.subcommands.extend(other.subcommands)
      return result
    else:
      result = Command(other.content)
      result.subcommands.extend(self.subcommands)
      result.subcommands.extend(other.subcommands)
      return result

  def __iadd__(self,other:SubCommand):
    self.subcommands.extend(other.subcommands)
    return self

  def As(self,entity:ISelector):
    """ execute as @ """
    return self + Execute.As(entity)

  def At(self,entity:ISelector):
    """ execute at @ """
    return self + Execute.At(entity)

  def Positioned(self,pos:Position.IPosition):
    """ execute positioned ~ ~ ~ """
    return self + Execute.Positioned(pos)

  def PositionedAs(self,entity:ISelector):
    """ execute positioned as @ """
    return self + Execute.PositionedAs(entity)

  def Align(self,axes:Literal['x','y','z','xy','yz','xz','xyz']):
    """ execute align xyz """
    return self + Execute.Align(axes)
    
  def Facing(self,pos:Position.IPosition):
    """ execute facing ~ ~ ~ """
    return self + Execute.Facing(pos)

  def FacingEntity(self,entity:ISelector):
    """ execute facing entity @ """
    return self + Execute.FacingEntity(entity)

  def Rotated(self,yaw:float,pitch:float):
    """ execute rotated ~ ~ """
    return self + Execute.Rotated(yaw,pitch)

  def RotatedAs(self,target:ISelector):
    """ execute rotated as @ """
    return self + Execute.RotatedAs(target)

  def In(self,dimension:str):
    """ execute in {dimension} """
    return self + Execute.In(dimension)

  def Anchored(self,anchor:Literal['feet','eyes']):
    """ execute anchored feet|eyes """
    return self + Execute.Anchored(anchor)

  def IfBlock(self,pos:Position.IPosition,block:Block):
    """ execute if block ~ ~ ~ {block} """
    return self + Execute.IfBlock(pos,block)

  def UnlessBlock(self,pos:Position.IPosition,block:Block):
    """ execute unless block ~ ~ ~ {block} """
    return self + Execute.UnlessBlock(pos,block)

  def IfBlocks(self,begin:Position.IPosition,end:Position.IPosition,destination:Position.IPosition,method:Literal['all','masked']):
    """ execute if blocks ~ ~ ~ ~ ~ ~ ~ ~ ~ {method} """
    return self + Execute.IfBlocks(begin,end,destination,method)

  def UnlessBlocks(self,begin:Position.IPosition,end:Position.IPosition,destination:Position.IPosition,method:Literal['all','masked']):
    """ execute unless blocks ~ ~ ~ ~ ~ ~ ~ ~ ~ {method} """
    return self + Execute.UnlessBlocks(begin,end,destination,method)

  def IfEntity(self,entity:ISelector):
    """ execute if entity {entity} """
    return self + Execute.IfEntity(entity)

  def UnlessEntity(self,entity:ISelector):
    """ execute unless entity {entity} """
    return self + Execute.UnlessEntity(entity)

  def IfScore(self,target:Scoreboard,source:Scoreboard,operator:Literal['<','<=','=','>=','>']):
    """ execute if score {entity} {operator} {source} """
    return self + Execute.IfScore(target,source,operator)

  def IfScoreMatch(self,target:Scoreboard,start:int,stop:int|None=None):
    """ execute if score {entity} matches {start}..{stop} """
    return self + Execute.IfScoreMatch(target,start,stop)

  def UnlessScore(self,target:Scoreboard,source:Scoreboard,operator:Literal['<','<=','=','>=','>']):
    """ execute unless score {entity} {operator} {source} """
    return self + Execute.UnlessScore(target,source,operator)  

  def UnlessScoreMatch(self,target:Scoreboard,start:int,stop:int|None=None):
    """ execute unless score {entity} matches {start}..{stop} """
    return self + Execute.UnlessScoreMatch(target,start,stop)

  def StoreResultNbt(self,nbt:Byte|Short|Int|Long|Float|Double,scale:float=1):
    """ execute store result {nbt} {scale} """
    return self + Execute.StoreResultNbt(nbt,scale)

  def StoreSuccessNbt(self,nbt:Byte|Short|Int|Long|Float|Double,scale:float=1):
    """ execute store success {nbt} {scale} """
    return self + Execute.StoreSuccessNbt(nbt,scale)

  def StoreResultScore(self,score:Scoreboard):
    """ execute store result score {score} """
    return self + Execute.StoreResultScore(score)

  def StoreSuccessScore(self,score:Scoreboard):
    """ execute store success score {score} """
    return self + Execute.StoreSuccessScore(score)

  def StoreResultBossbar(self,id:str,case:Literal['value','max']):
    """ execute store result bossbar {id} value|max {score} """
    return self + Execute.StoreResultBossbar(id,case)

  def StoreSuccessBossbar(self,id:str,case:Literal['value','max']):
    """ execute store success bossbar {id} value|max {score} """
    return self + Execute.StoreSuccessBossbar(id,case)

  def Run(self,command:Command|str):
    """ execute run {command} """
    return self + Execute.Run(command)


class Command:
  """ any minecraft command """
  def __init__(self,content:str) -> None:
    self.subcommands:list[str] = []
    self.content = content

  def export(self) -> str:
    result = self._command
    if self.subcommands:
      return "execute " + " ".join(self.subcommands) + " run " + result
    else:
      return result

  @property
  def _command(self) -> str:
    return self.content

  @staticmethod
  def Reload():
    return Command(f'reload')

  @staticmethod
  def Function(path:McPath|str,istag:bool=False):
    if istag:
      return Command(f'function {McPath(path).tag_str}')
    else:
      return Command(f'function {McPath(path).str}')

  @staticmethod
  def Say(content:str):
    return Command(f'say {content}')

  @staticmethod
  def Tellraw(entity:ISelector,*value:jsontext):
    v = "" if len(value) == 0 else evaljsontext(value[0] if len(value) == 1 else list(value))
    return Command(f'tellraw {entity.expression()} {json.dumps(v)}')

  @staticmethod
  def Summon(type:str,pos:Position.IPosition,**nbt:Value[INbt]):
    if nbt:
      return Command(f'summon {type} {pos.expression()} {Compound(nbt).str()}')
    return Command(f'summon {type} {pos.expression()}')

  @staticmethod
  def Kill(selector:ISelector):
    return Command(f'kill {selector.expression()}')
  
  class Tag:
    @staticmethod
    def List(entity:ISelector):
      return Command(f'tag {entity.expression()} list')

    @staticmethod
    def Add(entity:ISelector,tag:str):
      return Command(f'tag {entity.expression()} add {tag}')

    @staticmethod
    def Remove(entity:ISelector,tag:str):
      return Command(f'tag {entity.expression()} remove {tag}')

  @staticmethod
  def CallFunc(function:str):
    return Command(f'function {function}')

  @staticmethod
  def SetBlock(block:Block,pos:Position.IPosition,mode:Literal['destroy','keep','replace']|None=None):
    if mode:
      return Command(f'setblock {pos.expression()} {block.expression()} {mode}')
    return Command(f'setblock {pos.expression()} {block.expression()}')
  
  @staticmethod
  def Fill(start:Position.IPosition,end:Position.IPosition,block:Block,mode:Literal['destroy','hollow','keep','outline','replace']|None=None,oldblock:Block|None=None)->Command:
    if mode == 'replace':
      if oldblock is None:
        raise ValueError('fill mode "replace" needs argument "oldblock"')
      return Command(f'fill {start.expression()} {end.expression()} {block.expression()} replace {oldblock.expression()}')
    if oldblock is not None:
      raise ValueError(f'''fill mode "{mode}" doesn't needs argument "oldblock"''')
    return Command(f'fill {start.expression()} {end.expression()} {block.expression()} {mode}')

  @staticmethod
  def Clone(
      start:Position.IPosition,
      end:Position.IPosition,
      target:Position.IPosition,
      maskmode:Literal['replace','masked','filtered']|None=None,
      clonemode:Literal['normal','force','move']|None=None,
      filterblock:Block|None=None
    ):
    clonemode_suffix = '' if clonemode is None else ' '+clonemode
    if maskmode == 'filtered':
      if filterblock is None:
        raise ValueError('clone mode "replace" needs argument "filterblock"')
      return Command(f'clone {start.expression()} {end.expression()} {target.expression()} filtered {filterblock.expression()}' + clonemode_suffix)

    if filterblock is not None:
      raise ValueError(f'''clone mode "{maskmode}" doesn't needs argument "filterblock"''')
    if maskmode is None:
      if clonemode is not None:
        raise ValueError(f'"clonemode" argument needs to be used with "maskmode" argument')
      return Command(f'clone {start.expression()} {end.expression()} {target.expression()}')
    return Command(f'clone {start.expression()} {end.expression()} {target.expression()} {maskmode}'+clonemode_suffix)

  @staticmethod
  def Give(item:Item,count:int):
    return Command(f'give {item.expression()} {count}')

  @staticmethod
  def Clear(entity:ISelector,item:Item|None=None,maxcount:int|None=None):
    cmd = f'clear {entity.expression()}'
    if item:
      cmd += f' {item.expression()}'
      if maxcount:
        cmd += f' {maxcount}'
    return Command(cmd)
  
  @overload
  @staticmethod
  def Particle(id:str,pos:Position.IPosition,dx:float,dy:float,dz:float,speed:float,count:int)->Command:pass
  @overload
  @staticmethod
  def Particle(id:str,pos:Position.IPosition,dx:float,dy:float,dz:float,speed:float,count:int,mode:Literal['force','normal'])->Command:pass
  @overload
  @staticmethod
  def Particle(id:str,pos:Position.IPosition,dx:float,dy:float,dz:float,speed:float,count:int,mode:Literal['force','normal'],entity:ISelector)->Command:pass
  @staticmethod
  def Particle(id:str,pos:Position.IPosition,dx:float,dy:float,dz:float,speed:float,count:int,mode:Literal['force','normal']|None=None,entity:ISelector|None=None):
    cmd = f'particke {id} {pos.expression()} {dx} {dy} {dz} {speed} {count}'
    if mode:
      cmd += ' '+mode
    if entity:
      cmd += ' '+entity.expression()
    return Command(cmd)
  
  @overload
  @staticmethod
  def ColorParticle(id:Literal['entity_effect','ambient_entity_effect'],pos:Position.IPosition,colorcode:str)->Command:pass
  @overload
  @staticmethod
  def ColorParticle(id:Literal['entity_effect','ambient_entity_effect'],pos:Position.IPosition,colorcode:str,mode:Literal['force','normal'])->Command:pass
  @overload
  @staticmethod
  def ColorParticle(id:Literal['entity_effect','ambient_entity_effect'],pos:Position.IPosition,colorcode:str,mode:Literal['force','normal'],entity:ISelector)->Command:pass
  @staticmethod
  def ColorParticle(id:Literal['entity_effect','ambient_entity_effect'],pos:Position.IPosition,colorcode:str,mode:Literal['force','normal']|None=None,entity:ISelector|None=None):
    """
    colorcode:
      "#000000"
    """
    return Command.Particle(id,pos,int(colorcode[1:3])/100,int(colorcode[3:5])/100,int(colorcode[5:7])/100,1,0,mode,entity) #type:ignore




class ConditionSubCommand(SubCommand,Command):
  """ if / unless """
  def export(self) -> str:
    assert self.subcommands
    return "execute " + " ".join(self.subcommands)

class _FunctionCommand(Command):
  """ function command """
  def __init__(self,holder:Function) -> None:
    super().__init__('')
    self.holder = holder

  @property
  def _command(self) -> str:
    raise NotImplementedError

class _FunctionTagCommand(Command):
  """ function tag command """
  def __init__(self,holder:FunctionTag) -> None:
    self.holder = holder
    super().__init__(f'function {holder.expression}')

class _ScheduleCommand(Command):
  """ function minecraft command """
  def __init__(self,holder:Function,tick:int,append:bool) -> None:
    super().__init__('')
    self.holder = holder
    self.tick = tick
    self.append = append

  @property
  def _command(self) -> str:
    return f'schedule function {self.holder.expression} {self.tick}t {"append" if self.append else "replace"}'

class _ScheduleClearCommand(Command):
  """ function minecraft command """
  def __init__(self,holder:Function) -> None:
    super().__init__('')
    self.holder = holder

  @property
  def _command(self) -> str:
    return f'schedule clear {self.holder.expression}'

class FunctionTag:
  tick:FunctionTag
  load:FunctionTag
  functiontags:list[FunctionTag] = []
  def __init__(self,path:str|McPath,export_if_empty:bool=True) -> None:
    FunctionTag.functiontags.append(self)
    self.path = McPath(path)
    self.export_if_empty = export_if_empty
    self.functions:list[Function|str|McPath] = []

  @property
  def expression(self) -> str:
    return self.path.tag_str

  def call(self) -> Command:
    return _FunctionTagCommand(self)

  @property
  def expression_without_hash(self) -> str:
    return self.path.str

  def append(self,function:Function|str|McPath):
    if isinstance(function,Function):
      function.tagged = True
    self.functions.append(function)

  def check_call_relation(self):
    """呼び出し先のファンクションにタグから呼ばれることを伝える"""
    for f in self.functions:
      if isinstance(f,Function):
        f.tagged = True
        f.within.add(self)

  def export(self,path:Path) -> None:
    path = self.path.function_tag(path)
    values:list[str] = []
    for f in self.functions:
      if isinstance(f,Function) and f.callstate is _FuncState.EXPORT:
        """中身のある呼び出し先だけ呼び出す"""
        values.append(f.expression)

    paths:list[Path] = []
    if self.export_if_empty or values:
      _path = path
      while not _path.exists():
        paths.append(_path)
        _path = _path.parent
      Datapack.created_paths.extend(reversed(paths))

      path.parent.mkdir(parents=True,exist_ok=True)
      path.write_text(json.dumps({"values":values}),encoding='utf8')

FunctionTag.tick = FunctionTag('minecraft:tick',False)
FunctionTag.load = FunctionTag('minecraft:load',False)

class IDatapackLibrary:
  """
  データパックライブラリ用クラス

  このクラスを継承すると出力先データパックに自動で導入される
  """
  using = True

  @classmethod
  def install(cls,datapack_path:Path,datapack_id:str) -> None:
    """
    ライブラリを導入

    データパック出力時に cls.using == True なら呼ばれる

    導入済みでも呼ばれる

    datapack_path : saves/{worldname}/datapacks/{datapack}

    datapack_id : 出力データパックのID
    """
    raise NotImplementedError

  @staticmethod
  def rmtree(path:Path):
    """ アクセス拒否を解消したshutil.rmtree """
    def onerror(func:Callable[[Path],None], path:Path, exc_info:Any):
      """
      Error handler for ``shutil.rmtree``.

      If the error is due to an access error (read only file)
      it attempts to add write permission and then retries.

      If the error is for another reason it re-raises the error.

      Usage : ``shutil.rmtree(path, onerror=onerror)``
      """
      import stat
      if not os.access(path, os.W_OK):
          # Is the error an access error ?
          os.chmod(path, stat.S_IWUSR)
          func(path)
      else:
          raise
    shutil.rmtree(path,onerror=onerror)
  
  @classmethod
  def uninstall(cls,datapack_path:Path) -> None:
    """
    ライブラリを削除

    未導入でも呼ばれる

    datapack_path : saves/{worldname}/datapacks/{datapack}
    """
    raise NotImplementedError

class _DatapackMeta(type):
  _default_path= McPath('minecraft:txbt')

  @property
  def default_path(cls):
    return cls._default_path

  @default_path.setter
  def default_path(cls,value:McPath|str):
    cls._default_path = McPath(value)

  _description:str|None=None
  @property
  def description(cls):
    return cls._description

  @description.setter
  def description(cls,value:None|str):
    cls._description = value
  
  export_imp_doc = True

class FunctionAccessModifier(Enum):
  WITHIN = "within"
  PRIVATE = "private"
  INTERNAL = "internal"
  PUBLIC = "public"
  API = "api"

class Datapack(metaclass=_DatapackMeta):
  """
  データパック出力時の設定

  attrs
  ---
  default_namespace:
    匿名ファンクションの出力先の名前空間

  default_folder:
    匿名ファンクションの出力先のディレクトリ階層

  description:
    データパックの説明 (pack.mcmetaのdescriptionの内容)

  export_imp_doc:
    [IMP-Doc](https://github.com/ChenCMD/datapack-helper-plus-JP/wiki/IMP-Doc) を出力するか否か
  """
  created_paths:list[Path] = []

  @staticmethod
  def export(
    path:str|Path,
    id:str,
    default_namespace:str|None=None,
    default_folder:str|None=None,
    description:str|None=None,
    export_imp_doc:bool|None=None
    ):
    """
    データパックを指定パスに出力する

    必ず一番最後に呼ぶこと

    params
    ---
    path: Path
      データパックのパス ...\\saves\\\\{world_name}\\datapacks\\\\{datapack_name}

    id: Str
      データパックのID(半角英数)

    default_namespace: str = '_'
      自動生成されるファンクションの格納先の名前空間

      例 : '_', 'foo'

    default_folder: str = ''
      自動生成されるファンクションの格納先のディレクトリ階層 空文字列の場合は名前空間直下に生成

      例 : '', 'foo/', 'foo/bar/'
    
    description: str|None = None
      データパックのpack.mcmetaのdescriptionの内容

    export_imp_doc:
      [IMP-Doc](https://github.com/ChenCMD/datapack-helper-plus-JP/wiki/IMP-Doc) を出力するか否か
    """

    path = Path(path)

    if default_namespace is not None: Datapack.default_namespace = default_namespace
    if default_folder is not None: Datapack.default_folder = default_folder
    if description is not None: Datapack.description = description
    if export_imp_doc is not None: Datapack.export_imp_doc = export_imp_doc

    pydptxt = (path/"pydp.txt")
    if pydptxt.exists():
      for s in reversed(pydptxt.read_text().split('\n')):
        p = (path / s)
        if not p.exists():
          continue
        if p.is_file():
          p.unlink()
        elif p.is_dir() and not any(p.iterdir()):
          p.rmdir()


    for library in IDatapackLibrary.__subclasses__():
      if library.using:
        library.install(path,id)
      else:
        library.uninstall(path)


    if not path.exists():
      Datapack.created_paths.append(path)
      path.mkdir(parents=True)

    mcmeta = path/"pack.mcmeta"
    if not mcmeta.exists() or Datapack.description is not None:
      description = "pydp auto generated datapack" if Datapack.description is None else Datapack.description
      mcmeta.write_text(f"""{{
  "pack":{{
    "pack_format":10,
    "description":{description}
  }}
}}""")

    for f in FunctionTag.functiontags:
      # function.taggedをTrueにする
      f.check_call_relation()

    for f in Function.functions:
      # 呼び出し構造の解決
      f.check_call_relation()

    for f in Function.functions:
      # 書き出しか埋め込みかを決定する
      f.define_state()

    for f in Function.functions:
      # 埋め込みが再帰しないように解決
      f.recursivecheck()

    for f in FunctionTag.functiontags:
      # ファンクションタグ出力
      f.export(path)

    for f in Function.functions:
      # ファンクション出力
      f.export(path)

    pathstrs:list[str] = []
    for p in Datapack.created_paths:
      relpath = p.relative_to(path)
      pathstrs.append(str(relpath))
    pydptxt.write_text('\n'.join(pathstrs))


class _FuncState(Enum):
  NEEDLESS = auto()
  FLATTEN = auto()
  SINGLE = auto()
  EXPORT = auto()


class Function:
  """
  新規作成するmcfunctionをあらわすクラス

  既存のmcfunctionを使う場合はExistFunctionクラスを使うこと

  `Function += Command`でコマンドを追加できる。

  マイクラ上では`function {namespace}:{name}`となる。

  `namespace`,`name`を省略するとデフォルトの名前空間のデフォルトのフォルダ内に`"{自動生成id}.mcfunction"`が生成される。
  ただし、最適化によってmcfunctionファイルが生成されない場合がある。

  デフォルトの名前空間とデフォルトのフォルダはFunction.exportAll()の引数で設定可能。

  params
  ---
  namespace: Optional[str] = None
    ファンクション名前空間

    省略するとデフォルトの名前空間となる (Function.exportAll()の引数で設定可能) 

    例: `"minecraft"` `"mynamespace"`

  name: Optional[str] = None
    ファンクションのパス 空白や'/'で終わる場合はファンクション名が`".mcfunction"`となる

    省略するとデフォルトのフォルダ内の`{自動生成id}.mcfunction`となる (Function.exportAll()の引数で設定可能) 

    例: `""` `"myfync"` `"dir/myfunc"` `"dir/subdir/"`
  
  access_modifier: Optional[FunctionAccessModifier]
    [IMP-Doc](https://github.com/ChenCMD/datapack-helper-plus-JP/wiki/IMP-Doc)のファンクションアクセス修飾子を指定

    Datapack.export_imp_doc == False の場合機能しない

    デフォルト: 匿名ファンクションの場合 WITHIN, 名前付きの場合 API
  
  description: Optional[str]
    functionの説明文 複数行可能

    [IMP-Doc](https://github.com/ChenCMD/datapack-helper-plus-JP/wiki/IMP-Doc)に記載する

    Datapack.export_imp_doc == False の場合機能しない
  
  delete_on_regenerate:
    データパック再生成時にファンクションを削除するかどうか
    基本的にTrue

  commands: list[Command] = []
    コマンドのリスト

    += で後からコマンドを追加できるので基本的には与えなくてよい

  example
  ---

  ```python
  func1 = Function('minecraft','test/func')
  func1 += MC.Say('hello')

  func2 = Function()

  func1 += func2.call()
  ```

  """

  functions:list[Function] = []

  @classmethod
  def nextPath(cls) -> str:
    """無名ファンクションのパスを生成する"""
    return _gen_id(upper=False,length=24)

  callstate:_FuncState
  default_access_modifier:FunctionAccessModifier = FunctionAccessModifier.API

  @overload
  def __init__(self,path:str|McPath,access_modifier:FunctionAccessModifier|None=None,description:str|None=None,delete_on_regenerate:bool=True,*_,commands:None|list[Command]=None) -> None:pass
  @overload
  def __init__(self,path:str|McPath,*_,commands:None|list[Command]=None) -> None:pass
  @overload
  def __init__(self,*_,commands:None|list[Command]=None) -> None:pass
  def __init__(self,path:str|McPath|None=None,access_modifier:FunctionAccessModifier|None=None,description:str|None=None,delete_on_regenerate:bool=True,*_,commands:None|list[Command]=None) -> None:


    self.delete_on_regenerate = delete_on_regenerate
    
    self.functions.append(self)
    self.commands:list[Command] = [*commands] if commands else []
    self._path = None if path is None else McPath(path)
    self._children:set[Function] = set()

    self._hasname = self._path is not None
    self._scheduled = False
    self.tagged = False
    self.subcommanded = False
    self.used = False
    self.visited = False

    self.description = description

    self.calls:set[Function] = set()

    self.within:set[Function|FunctionTag] = set()
  
    if access_modifier is None:
      if self._hasname:
        access_modifier = Function.default_access_modifier
      else:
        access_modifier = FunctionAccessModifier.WITHIN
    self.access_modifier = access_modifier

  def set_path(self,path:str|McPath):
    self._path = McPath(path)
    self._hasname = True

  @property
  def path(self) -> McPath:
    if self._path is None:
      self._path = Datapack.default_path/self.nextPath()
    return self._path

  def __iadd__(self,value:str|Command):
    match value:
      case str():
        self.append(Command(value))
      case Command():
        self.append(value)
    return self

  def append(self,*commands:Command):
    for command in commands:
      if isinstance(command,_FunctionCommand):
        self._children.add(command.holder)
    self.commands.extend(commands)

  @property
  def expression(self) -> str:
    return self.path.str

  def call(self) -> Command:
    return _FunctionCommand(self)

  def schedule(self,tick:int,append:bool=True) -> Command:
    self._scheduled = True
    return _ScheduleCommand(self,tick,append)

  def clear_schedule(self) -> Command:
    self._scheduled = True
    return _ScheduleClearCommand(self)

  def _isempty(self):
    for cmd in self.commands:
      if not (isinstance(cmd,_FunctionCommand) and cmd.holder._isempty()):
        return False
    return True

  def _issingle(self):
    return len(self.commands) == 1

  def _ismultiple(self):
    return len(self.commands) > 1

  def check_call_relation(self):
    """呼び出し先一覧を整理"""
    for cmd in self.commands:
      if isinstance(cmd,_FunctionCommand):
        if cmd.subcommands:
          cmd.holder.subcommanded = True
        cmd.holder.used = True
        self.calls.add(cmd.holder)
        cmd.holder.within.add(self)

  def define_state(self) -> None:
    """関数を埋め込むか書き出すか決定する"""
    if self._hasname:
      self.callstate = _FuncState.EXPORT
    elif self._isempty():
      self.callstate = _FuncState.NEEDLESS
    elif self._scheduled or self.tagged:
      self.callstate = _FuncState.EXPORT
    elif not self.subcommanded:
      self.callstate = _FuncState.FLATTEN
    elif self._issingle():
      self.callstate = _FuncState.SINGLE
    else:
      self.callstate = _FuncState.EXPORT

  def recursivecheck(self,parents:set[Function]=set()):
    """埋め込み再帰が行われている場合、ファイル出力に切り替える"""
    if self.visited: return
    parents = parents|{self}

    for cmd in self.commands:
      if isinstance(cmd,_FunctionCommand):
        func = cmd.holder
        if func in parents:
          func.callstate = _FuncState.EXPORT
        if func.callstate is _FuncState.FLATTEN or func.callstate is _FuncState.SINGLE:
          func.recursivecheck(parents)

    self.visited = True

  def export_commands(self,path:Path,commands:list[str],subcommand:list[str]):
    match self.callstate:
      case _FuncState.NEEDLESS:
        pass
      case _FuncState.FLATTEN:
        assert not subcommand
        for cmd in self.commands:
          if isinstance(cmd,_FunctionCommand):
            cmd.holder.export_commands(path,commands,cmd.subcommands)
          else:
            commands.append(cmd.export())
      case _FuncState.SINGLE:
        assert len(self.commands) == 1
        cmd = self.commands[0]
        if isinstance(cmd,_FunctionCommand):
          cmd.holder.export_commands(path,commands,subcommand + cmd.subcommands)
        else:
          s = cmd.subcommands
          cmd.subcommands = subcommand + cmd.subcommands
          commands.append(cmd.export())
          cmd.subcommands = s
      case _FuncState.EXPORT:
        cmds:list[str] = []
        for cmd in self.commands:
          if isinstance(cmd,_FunctionCommand):
            cmd.holder.export_commands(path,cmds,cmd.subcommands)
          else:
            cmds.append(cmd.export())
        self.export_function(path,cmds)
        c = Command(f"function {self.expression}")
        c.subcommands = [*subcommand]
        commands.append(c.export())

  def export_function(self,path:Path,commands:list[str]):
    path = self.path.function(path)

    paths:list[Path] = []
    _path = path
    while not _path.exists():
      paths.append(_path)
      _path = _path.parent

    if self.delete_on_regenerate:
      Datapack.created_paths.extend(reversed(paths))

    path.parent.mkdir(parents=True,exist_ok=True)

    if Datapack.export_imp_doc:
      commands.insert(0,self._imp_doc())

    result = "\n".join(commands)

    path.write_text(result,encoding='utf8')

  def _imp_doc(self):
    description = ''
    if self.description:
      description = '\n' + '\n# \n'.join( f"# {x}" for x in self.description.split('\n'))

    withinstr = ''
    if self.access_modifier is FunctionAccessModifier.WITHIN:
      withins:list[str] = []
      for file in self.within:
        match file:
          case Function():
            withins.append(f'function {file.expression}')
          case FunctionTag():
            withins.append(f'tag/function {file.expression_without_hash}')
      withinstr = '\n' + '\n'.join(f'#   {x}' for x in withins)

    return f"""#> {self.expression}{description}
# @{self.access_modifier.value}""" + withinstr

  def export(self,path:Path) -> None:
    if self.callstate is _FuncState.EXPORT:
      self.export_commands(path,[],[])






















class Execute:
  """
  コマンド/サブコマンド生成メソッドをまとめたstaticクラス

  大体のコマンドはここから呼び出せる

  コマンドを追加する場合もここに
  """

  @staticmethod
  def As(entity:ISelector):
    return entity.As()

  @staticmethod
  def At(entity:ISelector):
    return entity.At()

  @staticmethod
  def Positioned(pos:Position.IPosition):
    return pos.Positioned()

  @staticmethod
  def PositionedAs(entity:ISelector):
    return entity.PositionedAs()

  @staticmethod
  def Align(axes:Literal['x','y','z','xy','yz','xz','xyz']):
    return SubCommand('align '+axes)

  @staticmethod
  def Facing(pos:Position.IPosition):
    return pos.Facing()

  @staticmethod
  def FacingEntity(entity:ISelector):
    return entity.FacingEntity()

  @staticmethod
  def Rotated(yaw:float,pitch:float):
    return SubCommand(f'rotated {_float_to_str(yaw)} {_float_to_str(pitch)}')

  @staticmethod
  def RotatedAs(entity:ISelector):
    return entity.RotatedAs()

  @staticmethod
  def In(dimension:str):
    return SubCommand(f'in {dimension}')

  @staticmethod
  def Anchored(anchor:Literal['feet','eyes']):
    return SubCommand(f'anchored {anchor}')

  @staticmethod
  def IfEntity(entity:ISelector):
    return entity.IfEntity()

  @staticmethod
  def UnlessEntity(entity:ISelector):
    return entity.UnlessEntity()

  @staticmethod
  def IfBlock(pos:Position.IPosition,block:Block):
    return ConditionSubCommand(f"if block {pos.expression()} {block.expression()}")

  @staticmethod
  def UnlessBlock(pos:Position.IPosition,block:Block):
    return pos.UnlessBlock(block)

  @staticmethod
  def IfBlocks(begin:Position.IPosition,end:Position.IPosition,destination:Position.IPosition,method:Literal['all','masked']):
    return ConditionSubCommand(f'if blocks {begin.expression()} {end.expression()} {destination.expression()} {method}')

  @staticmethod
  def UnlessBlocks(begin:Position.IPosition,end:Position.IPosition,destination:Position.IPosition,method:Literal['all','masked']):
    return ConditionSubCommand(f'unless blocks {begin.expression()} {end.expression()} {destination.expression()} {method}')

  @staticmethod
  def IfScore(target:Scoreboard,source:Scoreboard,operator:Literal['<','<=','=','>=','>']):
    return ConditionSubCommand(f'if score {target.expression()} {operator} {target.expression()}')

  @staticmethod
  def IfScoreMatch(target:Scoreboard,start:int,stop:int|None=None):
    if stop is None:
      return ConditionSubCommand(f'if score {target.expression()} matches {start}')
    else:
      return ConditionSubCommand(f'if score {target.expression()} matches {start}..{stop}')

  @staticmethod
  def UnlessScore(target:Scoreboard,source:Scoreboard,operator:Literal['<','<=','=','>=','>']):
    return ConditionSubCommand(f'if score {target.expression()} {operator} {source.expression()}')

  @staticmethod
  def UnlessScoreMatch(target:Scoreboard,start:int,stop:int|None=None):
    if stop is None:
      return ConditionSubCommand(f'unless score {target.expression()} match {start}')
    else:
      return ConditionSubCommand(f'unless score {target.expression()} match {start}..{stop}')

  @staticmethod
  def StoreResultNbt(nbt:Byte|Short|Int|Long|Float|Double,scale:float=1):
    return nbt.storeResult(scale)

  @staticmethod
  def StoreSuccessNbt(nbt:Byte|Short|Int|Long|Float|Double,scale:float=1):
    return nbt.storeSuccess(scale)

  @staticmethod
  def StoreResultScore(scoreboard:Scoreboard):
    return SubCommand(f'store result score {scoreboard.expression()}')
  
  @staticmethod
  def StoreSuccessScore(scoreboard:Scoreboard):
    return SubCommand(f'store success score {scoreboard.expression()}')
  
  @staticmethod
  def StoreResultBossbar(id:str,case:Literal['value','max']):
    return SubCommand(f'store result bossbar {id} {case}')

  @staticmethod
  def StoreSuccessBossbar(id:str,case:Literal['value','max']):
    return SubCommand(f'store success bossbar {id} {case}')
  
  @staticmethod
  def Run(command:Command|str):
    if isinstance(command,str):
      return Command(command)
    return command




























class NbtPath:
  class INbtPath:
    def __init__(self,parent:NbtPath.INbtPath) -> None:
      self._parent = parent

    @abstractmethod
    def match(self,value:Value[NBT]) -> NbtPath.INbtPath:
      """
      パスが指定された値を持つかどうかを調べるためのパス
      """

    @abstractmethod
    def filter(self,value:Value[Compound]) -> NbtPath.INbtPath:
      """
      パスをdictの内容で絞るためのパス
      """

    @final
    def str(self)->str:
      return f"{self.typestr} {self.holderstr} {self.pathstr}"

    def get(self,scale:float|None=None):
      if scale is None:
        return Command(f'data get {self.str()}')
      return Command(f'data get {self.str()} {_float_to_str(scale)}')

    def store(self,mode:Literal['result','success'],type:Literal['byte','short','int','long','float','double'],scale:float=1):
      return SubCommand(f'store {mode} {self.str()} {type} {_float_to_str(scale or 1.0)}')

    @property
    def to_jsontext(self) -> jsontextvalue:
      return {"nbt":self.pathstr,self.typestr:self.holderstr}
    
    @property
    def typestr(self) -> str:
      return self._parent.typestr

    @property
    def holderstr(self) -> str:
      return self._parent.holderstr

    @property
    @abstractmethod
    def pathstr(self) -> str:
      """
      nbtパスの文字列

      a / a.a / a[0] ...
      """

  class Root(INbtPath):
    """stoarge a:b {}"""
    def __init__(self,type:Literal["storage","entity","block"],holder:str) -> None:
      self._type:Literal["storage","entity","block"] = type
      self._holder = holder

    def match(self,value:Value[INbt]) -> NbtPath.INbtPath:
      assert Value.isCompound(value)
      return self.filter(value)

    def filter(self,value:Value[Compound]) -> NbtPath.INbtPath:
      return NbtPath.RootMatch(self._type,self._holder,value)

    @property
    def pathstr(self)->str:
      return f'{{}}'

    @property
    def typestr(self) -> str:
      return self._type

    @property
    def holderstr(self) -> str:
      return self._holder

  class RootMatch(INbtPath):
    """stoarge a:b {bar:buz}"""
    def __init__(self,type:Literal["storage","entity","block"],holder:str,match:Value[Compound]) -> None:
      self._condition = match
      self._type:Literal["storage","entity","block"] = type
      self._holder = holder

    def match(self,value:Value[INbt]) -> NbtPath.INbtPath:
      assert Value.isCompound(value)
      return self.filter(value)

    def filter(self,value:Value[Compound]) -> NbtPath.INbtPath:
      return NbtPath.RootMatch(self._type,self._holder,Compound.mergeValue(self._condition,value))
    
    @property
    def pathstr(self)->str:
      return self._condition.str()

    @property
    def typestr(self) -> str:
      return self._type

    @property
    def holderstr(self) -> str:
      return self._holder

  class Child(INbtPath):
    """
    stoarge a:b foo
    stoarge a:b foo.bar
    """
    def __init__(self, parent: NbtPath.INbtPath,child:str) -> None:
      super().__init__(parent)
      self._value = child

    def match(self,value:Value[NBT]) -> NbtPath.INbtPath:
      return self._parent.filter(Compound({self._value:value}))

    def filter(self,value:Value[Compound]) -> NbtPath.INbtPath:
      return NbtPath.ChildMatch(self._parent,self._value,value)

    _escape_re = re.compile(r'[\[\]\{\}"\.]')

    @staticmethod
    def _escape(value:str):
      """
      nbtパスのエスケープ処理

      []{}." がある場合ダブルクオートで囲う必要がある
      
      ダブルクオート内では"と\\をエスケープする
      """
      if NbtPath.Child._escape_re.match(value):
        return '"' + value.replace('\\','\\\\').replace('"','\\"') + '"'
      return value

    @property
    def pathstr(self)->str:
      if isinstance(self._parent,NbtPath.Root):
        return self._value
      return self._parent.pathstr + '.' + self._value

  class ChildMatch(INbtPath):
    """stoarge a:b foo.bar{buz:qux}"""
    def __init__(self, parent: NbtPath.INbtPath,child:str,match:Value[Compound]) -> None:
      super().__init__(parent)
      self._value = child
      self._condition = match

    def match(self,value:Value[NBT]) -> NbtPath.INbtPath:
      assert Value.isCompound(value)
      return self._parent.filter(Compound({self._value:Compound.mergeValue(self._condition,value)}))

    def filter(self,value:Value[Compound]) -> NbtPath.INbtPath:
      return NbtPath.ChildMatch(self._parent,self._value,value)

    @property
    def pathstr(self)->str:
      if isinstance(self._parent,NbtPath.Root):
        return f'{self._value}{self._condition.str()}'
      return self._parent.pathstr + '.' + self._value + self._condition.str()

  class Index(INbtPath):
    """stoarge a:b foo.bar[0]"""
    def __init__(self, parent: NbtPath.INbtPath,index:int) -> None:
      super().__init__(parent)
      self._index = index

    def match(self,value:Value[NBT]) -> NbtPath.INbtPath:
      raise TypeError('indexed nbt value cannot be filtered')

    def filter(self,value:Value[Compound]) -> NbtPath.INbtPath:
      raise TypeError('indexed nbt value cannot be filtered')

    @property
    def pathstr(self)->str:
      return f'{self._parent.pathstr}[{self._index}]'

  class All(INbtPath):
    """stoarge a:b  foo.bar[]"""
    def __init__(self, parent: NbtPath.INbtPath) -> None:
      super().__init__(parent)

    def match(self,value:Value[NBT]) -> NbtPath.INbtPath:
      if Value.isCompound(value):
        return NbtPath.AllMatch(self._parent,value)
      else:
        raise TypeError('nbt AllIndexPath cannot be match non-compound value')

    def filter(self,value:Value[Compound]) -> NbtPath.INbtPath:
      raise TypeError('indexed nbt value cannot be filtered')

    @property
    def pathstr(self)->str:
      return f'{self._parent.pathstr}[]'

  class AllMatch(INbtPath):
    """stoarge a:b foo.bar[{buz:qux}]"""
    def __init__(self, parent: NbtPath.INbtPath,match:Value[Compound]) -> None:
      super().__init__(parent)
      self._condition = match

    def match(self,value:Value[NBT]) -> NbtPath.INbtPath:
      assert Value.isCompound(value)
      return NbtPath.AllMatch(self._parent,Compound.mergeValue(self._condition,value))

    def filter(self,value:Value[Compound]) -> NbtPath.INbtPath:
      raise TypeError('indexed nbt value cannot be filtered')

    @property
    def pathstr(self)->str:
      return f'{self._parent.pathstr}[{self._condition.str()}]'

T = TypeVar('T')

class INbt:

  class Value:
    pass

  _cls:type[Self]
  _path:NbtPath.INbtPath
  
  def __init_subclass__(cls) -> None:
    super().__init_subclass__()
    cls._cls = cls

  def __new__(cls:type[NBT],value:NbtPath.INbtPath,type:type[NBT]) -> NBT:
    result = super().__new__(cls)
    result._cls = type
    result._path = value
    return result

  @property
  def path(self):
    return self._path.str()

  def _get(self,scale:float|None=None) -> Command:
    if scale is None:
      return Command(f"data get {self.path}")
    return Command(f"data get {self.path} {_float_to_str(scale)}")

  def remove(self) -> Command:
    return Command(f"data remove {self.path}")

  def _storeResult(self,type: Literal['byte', 'short', 'int', 'long', 'float', 'double'],scale:float) -> SubCommand:
    return self._path.store('result',type,scale)

  def _storeSuccess(self,type: Literal['byte', 'short', 'int', 'long', 'float', 'double'],scale:float) -> SubCommand:
    return self._path.store('success',type,scale)

  def isMatch(self,value:Value[Self]) -> ConditionSubCommand:
    return ConditionSubCommand(f'if data {self._path.match(value).str()}')

  def notMatch(self,value:Value[Self]) -> ConditionSubCommand:
    return ConditionSubCommand(f'unless data {self._path.match(value).str()}')

  def isExists(self) -> ConditionSubCommand:
    return ConditionSubCommand(f'if data {self._path.str()}')

  def notExists(self) -> ConditionSubCommand:
    return ConditionSubCommand(f'unless data {self._path.str()}')

  def set(self,value:Value[Self]|Self) -> Command:
    if isinstance(value,Value):
      return Command(f"data modify {self.path} set value {value.str()}")
    else:
      return Command(f"data modify {self.path} set from {value.path}")

  def jsontext(self) -> jsontextvalue:
    return self._path.to_jsontext

NBT = TypeVar('NBT',bound = INbt)
CO_NBT = TypeVar('CO_NBT',bound = INbt,covariant=True)

class Value(Generic[CO_NBT]):
  def __init__(self,type:type[CO_NBT],value:Any,tostr:Callable[[Any],str]) -> None:
    self._type = type
    self._tostr = tostr
    self.value = value

  def str(self):
    return self._tostr(self.value)

  @staticmethod
  def isCompound(value:Value[INbt]) -> TypeGuard[Value[Compound]]:
    return value._type is Compound

NUMBER = TypeVar('NUMBER',bound=Union[int,float])

class INbtGeneric(INbt,Generic[T]):
  @classmethod
  @abstractmethod
  def _str(cls:type[INBTG],value:T) -> Value[INBTG]:pass

  @overload
  def __new__(cls:type[INBTG],value:T) -> Value[INBTG]:pass
  @overload
  def __new__(cls:type[INBTG],value:NbtPath.INbtPath,type:type[INBTG]) -> INBTG:pass
  def __new__(cls:type[INBTG],value:NbtPath.INbtPath|T,type:type[INBTG]|None=None):
    if isinstance(value,NbtPath.INbtPath):
      assert type is not None
      if isinstance(value,NbtPath.Root|NbtPath.RootMatch):
        raise ValueError(f'nbt root cannot be {cls.__name__}')
      return super().__new__(cls,value,type)
    else:
      return cls._str(value)


INBTG = TypeVar('INBTG',bound=INbtGeneric[Any])

class INum(INbtGeneric[NUMBER]):
  _mode:Literal['byte', 'short', 'int', 'long', 'float', 'double']
  _prefixmap = {'byte':'b','short':'s','int':'','long':'l','float':'f','double':'d'}
  _min:int|float
  _max:int|float

  def storeResult(self,scale:float) -> SubCommand: return super()._storeResult(self._mode,scale)
  def storeSuccess(self,scale:float) -> SubCommand: return super()._storeSuccess(self._mode,scale)
  def getValue(self,scale:float|None=None) -> Command:return super()._get(scale)

  @classmethod
  def _str(cls:type[INBTG],value:NUMBER) -> Value[INBTG]:
    assert issubclass(cls,INum)
    if value < cls._min or cls._max < value:
      raise ValueError(f'{cls._mode} must be in range {cls._min}..{cls._max}')
    return Value(cls._cls,value,cls._srtingifier)

  @classmethod
  def _srtingifier(cls,value:Any):
    if isinstance(value,float):
      return f'{_float_to_str(value)}{cls._prefixmap[cls._mode]}'
    assert isinstance(value,int)
    return f'{value}{cls._prefixmap[cls._mode]}'

class Byte(INum[int]):
  _mode = 'byte'
  _min = -2**7
  _max = 2**7-1

class Short(INum[int]):
  _mode = 'short'
  _min = -2**15
  _max = 2**15-1

class Int(INum[int]):
  _mode = 'int'
  _min = -2**31
  _max = 2**31-1

class Long(INum[int]):
  _mode = 'long'
  _min = -2**63
  _max = 2**63-1

class Float(INum[float]):
  _mode = 'float'
  _min = -3.402823e+38
  _max = 3.402823e+38

class Double(INum[float]):
  _mode = 'double'
  _min = -1.797693e+308
  _max = 1.797693e+308

class Str(INbtGeneric[str]):
  @classmethod
  def _str(cls, value: str) -> Value[INbtGeneric[str]]:
    return Value(Str, value, cls._srtingifier)
  
  @classmethod
  def _srtingifier(cls,value:Any):
    assert isinstance(value,str)
    value = value.replace('\\', '\\\\').replace('"', '\\"')
    return f'"{value}"'

  def getLength(self,scale:float|None=None) -> Command:return super()._get(scale)


class IArray(INbt,Generic[NBT]):
  _prefix:str
  _arg:type[NBT]

  def __getitem__(self,index:int) -> NBT:
    return self._arg(NbtPath.Index(self._path,index),self._arg)

  def all(self) -> NBT:
    return self._arg(NbtPath.All(self._path),self._arg)

  def getLength(self,scale:float|None=None) -> Command:return super()._get(scale)
  _cls_name:str

  @staticmethod
  @abstractmethod
  def _get_arg(c:type[IArray[NBT]]) -> type[NBT]:pass

  @overload
  def __new__(cls:type[ARRAY],value:list[Value[NBT]]) -> Value[ARRAY]:pass
  @overload
  def __new__(cls:type[ARRAY],value:NbtPath.INbtPath,type:type[ARRAY]) -> ARRAY:pass
  def __new__(cls:type[ARRAY],value:NbtPath.INbtPath|list[Value[NBT]],type:type[ARRAY]|None=None):
    if isinstance(value,NbtPath.INbtPath):
      assert type is not None
      if isinstance(value,NbtPath.Root|NbtPath.RootMatch):
        raise ValueError(f'nbt root cannot be {cls._cls_name}')
      result = super().__new__(cls,value,type)
      result._arg = cls._get_arg(type)
      return result
    else:
      return Value[cls](cls,value,cls._stringify)

  @classmethod
  def _stringify(cls, value: Any):
    vlu: list[Value[NBT]] = value
    return f"[{cls._prefix}{','.join(v.str() for v in vlu)}]"

ARRAY = TypeVar('ARRAY',bound=IArray[Any])

class List(IArray[NBT]):
  _prefix=''

  @staticmethod
  def _get_arg(c:type[IArray[NBT]]) -> type[NBT]:
    return get_args(c)[0]

  def filterAll(self:List[Compound],compound:Value[Compound]) -> Compound:
    return self._arg(NbtPath.AllMatch(self._path,compound),self._arg)

class ByteArray(IArray[Byte]):
  _prefix='B;'

  @staticmethod
  def _get_arg(c:type[IArray[Byte]]) -> type[Byte]:
    return Byte

class IntArray(IArray[Int]):
  _prefix='I;'

  @staticmethod
  def _get_arg(c:type[IArray[Int]]) -> type[Int]:
    return Int

class Compound(INbt):
  @overload
  def __new__(cls,value:dict[str,Value[INbt]]) -> Value[Compound]:pass
  @overload
  def __new__(cls,value:NbtPath.INbtPath,type:type[Compound]) -> Compound:pass
  def __new__(cls,value:NbtPath.INbtPath|dict[str,Value[INbt]],type:type[Compound]|None=None):
    if isinstance(value,NbtPath.INbtPath):
      assert type is not None
      return super().__new__(cls,value,type)
    else:
      return Value(cls, value,cls._stringify)

  @classmethod
  def _stringify(cls, value: Any):
    vlu: dict[str,Value[INbt]] = value
    return f"{{{','.join( f'{k}:{v.str()}' for k,v in vlu.items())}}}"

  _escape_re = re.compile(r'[0-9a-zA-Z_\.-]+')
  @staticmethod
  def _escape_key(value:str):
    if value == "":
      raise ValueError('empty string is not allowed for Compound key')
    if Compound._escape_re.fullmatch(value):
      return value
    if '"' in value:
      return "'" + value.replace('\\','\\\\').replace("'","\\'") + "'"
    return '"' + value.replace('\\','\\\\').replace('"','\\"') + '"'


  @overload
  def __getitem__(self,value:str) -> Compound:pass
  @overload
  def __getitem__(self,value:type[NBT]) -> NBT:pass
  @overload
  def __getitem__(self,value:tuple[str,type[NBT]]) -> NBT:pass
  def __getitem__(self,value:str|type[NBT]|tuple[str,type[NBT]]):
    """子要素 self.child"""
    match value:
      case str():
        return Compound(NbtPath.Child(self._path,value),Compound)
      case (name,r):
        return r(NbtPath.Child(self._path,name),r)
      case _:
        return value(NbtPath.Child(self._path,_gen_id(prefix=':')),value)

  def childMatch(self,child:str,match:Value[Compound]):
    """条件付き子要素 self.child{foo:bar}"""
    return Compound(NbtPath.ChildMatch(self._path,child,match),Compound)

  def getLength(self,scale:float|None=None) -> Command:return super()._get(scale)

  @staticmethod
  def mergeValue(v1:Value[Compound],v2:Value[Compound]):
    value1:dict[str,Value[INbt]] = v1.value
    value2:dict[str,Value[INbt]] = v2.value
    result = {**value1}
    for k,v in value2.items():
      if Value.isCompound(v) and k in value1:
        w = value1[k]
        if Value.isCompound(w):
          result[k] = Compound.mergeValue(w,v)
        else:
          result[k] = v
      else:
        result[k] = v
    return Compound(result)

COMPOUNDVALUE = TypeVar('COMPOUNDVALUE',bound=Value[Compound])
COMPOUND = TypeVar('COMPOUND',bound=Compound)

class StorageNbt:
  def __new__(cls,name:str) -> Compound:
    return Compound(NbtPath.Root('storage',name),Compound)

class BlockNbt:
  def __new__(cls,position:Position.IPosition) -> Compound:
    return Compound(NbtPath.Root('block',position.expression()),Compound)

class EntityNbt:
  def __new__(cls,selector:ISelector) -> Compound:
    return Compound(NbtPath.Root('entity',selector.expression()),Compound)










class ISelector:
  target:str
  def __init__(
      self,
      type:str|list[str]|dict[str,bool]={},
      name:bool|str|list[str]|dict[str,bool]={},
      tag:bool|str|list[str]|dict[str,bool]={},
      team:bool|str|list[str]|dict[str,bool]={},
      scores:dict[str,str]={},
      advancements:dict[str,bool|dict[str,bool]]={},
      predicate:str|list[str]|dict[str,bool]={},
      gamemode:Literal["survival","creative","adventure","spectator"]|list[Literal["survival","creative","adventure","spectator"]]|dict[Literal["survival","creative","adventure","spectator"],bool]={},
      nbt:Value[Compound]|str|list[Value[Compound]|str|tuple[Value[Compound]|str,bool]]=[],
      origin:Position.World|None=None,
      dxdydz:tuple[float,float,float]|None=None,
      distance:str|None=None,
      pitch:str|None=None,
      yaw:str|None=None,
      level:str|None=None,
      limit:int|None=None,
      sort:Literal['nearest','furthest','random','arbitrary']|None=None,
      **kwarg:str|list[str]|dict[str,bool],
    ) -> None:
    """
    エンティティセレクタ

    実際に生成するときは以下を用いる

    EntitySelector.A() / EntitySelector.P() / EntitySelector.E() / EntitySelector.S() / EntitySelector.R()


    https://minecraft.fandom.com/ja/wiki/%E3%82%BF%E3%83%BC%E3%82%B2%E3%83%83%E3%83%88%E3%82%BB%E3%83%AC%E3%82%AF%E3%82%BF%E3%83%BC

    Parameters
    ----------
    type :
        "minecraft:armorstand" / ["armorstand","!marker"] / {"armorstand":True,"marker":False}
        否定条件のみ複数使用可
    name :
        "foo" / ["foo","!bar"] / {"foo":True,"bar":False,"buz":False}
        否定条件のみ複数使用可
    tag :
        True(1つ以上のタグを持つ) / False(いかなるタグも持たない) / "foo" / ["foo","!bar"] / {"foo":True,"bar":False,"buz":False}
    team:
        True(1つ以上のチームに所属) / False(いかなるチームにも属さない) / "foo" / ["foo","!bar"] / {"foo":True,"bar":False,"buz":False}
        否定条件のみ複数使用可
    scores:
        {"foo":"-10","bar":"1..100"}
    advancements:
        進捗の達成状況または各達成基準状況で絞り込む
        {"foo":True,"bar":{"buz":False,"qux":True}}
    predicate:
        "foo" / ["foo","!bar"] / {"foo":True,"bar":False,"buz":False}
    gamemode:
        "survival" / ["creative","!adventure"] / {"spectator":False,"survival":False}
    nbt:
        "{foo:bar}" / ["{foo:bar}","!{buz:qux}"] / {"{foo:bar}":True,"{buz:qux}":False}
    origin:
        エンティティの検索位置(ワールド座標)
    dxdydz:
        エンティティの検索範囲のオフセット
        origin:(1,2,3) dxdydz(5,10,15) の場合 (1..6,2..12,3..18)に掠るエンティティを選択する
    distance:
        エンティティの検索半径
        "3" / "10..20"
    pitch:
        仰・俯角
        "90"(真下) / "-90"(真上) / "-10..10"
    yaw:
        水平角
        "-180"(北) / "-90"(東) / "0"(南) / "90"(西) / "180"(北) / "-90..90"
    level:
        経験値レベル
        "10" / "11..20"
    limit:
        エンティティ最大数
    sort:
        エンティティの選択順
        'nearest'(近い順) / 'furthest'(遠い順),'random'(ランダム),'arbitrary'(スポーンした順※一番軽い)
    """

    def format(arg:bool|str|list[str]|dict[str,bool]):
      match arg:
        case bool():
          return {"":arg}
        case str():
          if arg.startswith("!"):
            return {arg[1:]:False}
          else:
            return {arg:True}
        case list():
          result:dict[str,bool] = {}
          for a in arg:
            if a.startswith("!"):
              result[a[1:]] = False
            else:
              result[a] = True
          return result
        case dict():
          return {**arg}

    def formatCompound(arg:Value[Compound]|str|list[str|Value[Compound]|tuple[str|Value[Compound],bool]]):
      match arg:
        case str():
          if arg.startswith("!"):
            return {arg[1:]:False}
          else:
            return {arg:True}
        case Value():
          return {arg.str():True}
        case list():
          result:dict[str,bool] = {}
          for a in arg:
            match a:
              case str():
                if a.startswith("!"):
                  result[a[1:]] = False
                else:
                  result[a] = True
              case Value():
                  result[a.str()] = True
              case (c,b):
                match c:
                  case str():
                    result[c] = b
                  case Value():
                    result[c.str()] = b
          return result

    self.kwarg = {k:format(v) for k,v in kwarg.items()}

    self["name"] = format(name)
    self["type"] = format(type)
    self["gamemode"] = format(gamemode)
    self["tag"] = format(tag)
    self["team"] = format(team)

    self["_scores"] = {}
    self["_advancements"] = {}

    self["predicate"] = format(predicate)

    self["nbt"] = formatCompound(nbt)

    if origin is not None:
      self["x"][_float_to_str(origin.x)] = True
      self["y"][_float_to_str(origin.y)] = True
      self["z"][_float_to_str(origin.z)] = True

    if dxdydz is not None:
      self["dx"][_float_to_str(dxdydz[0])] = True
      self["dy"][_float_to_str(dxdydz[1])] = True
      self["dz"][_float_to_str(dxdydz[2])] = True

    if distance is not None:self["distance"][distance] = True

    if yaw is not None:self["x_rotation"][yaw] = True
    if pitch is not None:self["y_rotation"][pitch] = True

    if level is not None:self["level"][level] = True

    if limit is not None:self["limit"][str(limit)] = True
    if sort is not None:self["sort"][sort] = True

    self.scores = scores
    self.advancements = advancements
  
  def __str__(self) -> str:
    return self.expression()

  def __getitem__(self,index:str) -> dict[str,bool]:
    if index not in self.kwarg:
      self.kwarg[index] = {}
    return self.kwarg[index]

  def __setitem__(self,index:str,value:dict[str,bool]) -> None:
    self.kwarg[index] = value
  
  def IfEntity(self):
    return ConditionSubCommand("if entity " + self.expression())

  def UnlessEntity(self):
    return ConditionSubCommand("unless entity " + self.expression())
  
  def As(self):
    return SubCommand("as " + self.expression())
  
  def At(self):
    return SubCommand("at " + self.expression())

  def PositionedAs(self):
    return SubCommand("positioned as " + self.expression())

  def FacingEntity(self):
    return SubCommand("facing entity " + self.expression())

  def RotatedAs(self):
    return SubCommand("rotated as " + self.expression())

  def expression(self):
    def bool2str(x:bool):
      return str(x).lower()

    selectors:list[str] = []

    for k,vs in self.kwarg.items():
      match k:
        case "_scores":
          if self.scores:
            selectors.append(f'scores={{{",".join(f"{k}={v}" for k,v in self.scores.items())}}}')
        case "_advancements":
          if self.advancements:
            selectors.append(f'advancements={{{",".join( k + "=" +( bool2str(v) if isinstance(v,bool) else "{"+",".join(f"{ki}={bool2str(vi)}" for ki,vi in v.items())+"}") for k,v in self.advancements.items())}}}')
        case _:
          selectors.extend([f'{k}={["!",""][b]}{v}' for v,b in vs.items()])

    if selectors:
      return f'{self.target}[{",".join(selectors)}]'
    else:
      return f'{self.target}'

  @property
  def nbt(self):
    return EntityNbt(self)

  def score(self,objective:Objective):
    return Scoreboard(objective,self)

  def PleaseMyDat(self):
    return self.As() + OhMyDat.Please()

  def TagAdd(self,id:str):
    return Command.Tag.Add(self,id)

  def TagRemove(self,id:str):
    return Command.Tag.Remove(self,id)

  def TagList(self):
    return Command.Tag.List(self)
  
  def merge(self:S,other:S):
    result = self.__class__()
    result.kwarg = {**self.kwarg,**other.kwarg}
    result.scores = {**self.scores,**other.scores}
    result.advancements = {**self.advancements,**other.advancements}
    return result
  
  def filter(
        self,
        type:str|list[str]|dict[str,bool]={},
        name:bool|str|list[str]|dict[str,bool]={},
        tag:bool|str|list[str]|dict[str,bool]={},
        team:bool|str|list[str]|dict[str,bool]={},
        scores:dict[str,str]={},
        advancements:dict[str,bool|dict[str,bool]]={},
        predicate:str|list[str]|dict[str,bool]={},
        gamemode:Literal["survival","creative","adventure","spectator"]|list[Literal["survival","creative","adventure","spectator"]]|dict[Literal["survival","creative","adventure","spectator"],bool]={},
        nbt:Value[Compound]|str|list[Value[Compound]|str|tuple[Value[Compound]|str,bool]]=[],
        origin:Position.World|None=None,
        dxdydz:tuple[float,float,float]|None=None,
        distance:str|None=None,
        pitch:str|None=None,
        yaw:str|None=None,
        level:str|None=None,
        limit:int|None=None,
        sort:Literal['nearest','furthest','random','arbitrary']|None=None,
        **kwarg:str|list[str]|dict[str,bool]
      ):
      other = self.__class__(type,name,tag,team,scores,advancements,predicate,gamemode,nbt,origin,dxdydz,distance,pitch,yaw,level,limit,sort,**kwarg)
      return self.merge(other)
  
  def jsontext(self) -> jsontextvalue:
    return {"selector":self.expression()}


S = TypeVar('S',bound=ISelector)

class Selector:
  class S(ISelector):
    """@s[...]"""
    target = "@s"

  class E(ISelector):
    """@e[...]"""
    target = "@e"

  class A(ISelector):
    """@a[...]"""
    target = "@a"

  class P(ISelector):
    """@p[...]"""
    target = "@p"

  class R(ISelector):
    """@r[...]"""
    target = "@r"

  class Player(ISelector):
    """
    プレイヤー名を直接使うセレクタ
    txkodo[gamemode=survival]
    """
    def __init__(self, player:str, type: str | list[str] | dict[str, bool] = {}, name: bool | str | list[str] | dict[str, bool] = {}, tag: bool | str | list[str] | dict[str, bool] = {}, team: bool | str | list[str] | dict[str, bool] = {}, scores: dict[str, str] = {}, advancements: dict[str, bool | dict[str, bool]] = {}, predicate: str | list[str] | dict[str, bool] = {}, gamemode: Literal["survival", "creative", "adventure", "spectator"] | list[Literal["survival", "creative", "adventure", "spectator"]] | dict[Literal["survival", "creative", "adventure", "spectator"], bool] = {}, nbt: Value[Compound] | str | list[Value[Compound] | str | tuple[Value[Compound] | str, bool]] = [], origin: Position.World | None = None, dxdydz: tuple[float, float, float] | None = None, distance: str | None = None, pitch: str | None = None, yaw: str | None = None, level: str | None = None, limit: int | None = None, sort: Literal['nearest', 'furthest', 'random', 'arbitrary'] | None = None, **kwarg: str | list[str] | dict[str, bool]) -> None:
      super().__init__(type, name, tag, team, scores, advancements, predicate, gamemode, nbt, origin, dxdydz, distance, pitch, yaw, level, limit, sort, **kwarg)
      self.target = player

class Objective:
  """
  スコアボードのobjective

  idはスコアボード名
  """  
  @staticmethod
  def List():
    return Command('scoreboard objectives list')

  def __init__(self,id:str) -> None:
    self.id = id
    
  def Add(self,condition:str='dummy',display:str|None=None):
    """
    スコアボードを追加する

    display:
      表示名
    """
    if display is None:
      return Command(f'scoreboard objectives add {self.id} {condition}')
    else:
      return Command(f'scoreboard objectives add {self.id} {condition} {display}')
  
  def Remove(self):
    """
    スコアボードを削除する
    """
    return Command(f'scoreboard objectives remove {self.id}')
  
  def Setdisplay(self,slot:str):
    """
    スコアボードを表示する

    slot:
      "sidebar" 等
    """
    return Command(f'scoreboard objectives setdisplay {slot} {self.id}')
  
  def ModifyDisplay(self,display:str):
    """
    スコアボードの表示名を変更する

    display:
      表示名
    """
    return Command(f'scoreboard objectives modify {self.id} {display}')

  def score(self,entity:ISelector|None):
    """
    エンティティのスコアを取得
    """
    return Scoreboard(self,entity)

class Scoreboard:
  @staticmethod
  def List(entity:ISelector|None):
    """ 
    エンティティに紐づいたスコアボード一覧を取得

    entity:
      None -> すべてのエンティティを対象にする
    """
    if entity is None:
      return Command('scoreboard players list *')
    return Command(f'scoreboard players list {entity.expression()}')
  
  def expression(self):
    if self.entity is None:
      return f'* {self.objective.id}'
    return f'{self.entity.expression()} {self.objective.id}'

  def __init__(self,objective:Objective,entity:ISelector|None) -> None:
    """ None:すべてのエンティティを対象にする """
    self.objective = objective
    self.entity = entity

  def Get(self):
    assert self.entity
    return Command(f'scoreboard players get {self.expression()}')

  def Set(self,value:int):
    return Command(f'scoreboard players set {self.expression()} {value}')

  def Add(self,value:int) -> Command:
    if value <= -1:
      return self.Remove(-value)
    assert 0 <= value <= 2147483647
    return Command(f'scoreboard players add {self.expression()} {value}')

  def Remove(self,value:int) -> Command:
    if value <= -1:
      return self.Add(-value)
    assert 0 <= value <= 2147483647
    return Command(f'scoreboard players remove {self.expression()} {value}')
  
  def Reset(self):
    return Command(f'scoreboard players reset {self.expression()}')
  
  def Enable(self):
    return Command(f'scoreboard players enable {self.expression()}')
  
  def Oparation(self,other:Scoreboard,operator:Literal['+=','-=','*=','/=','%=','=','<','>','><']):
    return Command(f'scoreboard players operation {self.expression()} {operator} {other.expression()}')
  
  def StoreResult(self):
    return Execute.StoreResultScore(self)
  
  def StoreSuccess(self):
    return Execute.StoreSuccessScore(self)

  def IfMatch(self,start:int,stop:int|None=None):
    return Execute.IfScoreMatch(self,start,stop)

  def UnlessMatch(self,start:int,stop:int|None=None):
    return Execute.UnlessScoreMatch(self,start,stop)

  def If(self,target:Scoreboard,operator:Literal['<', '<=', '=', '>=', '>']):
    return Execute.IfScore(self,target,operator)

  def Unless(self,target:Scoreboard,operator:Literal['<', '<=', '=', '>=', '>']):
    return Execute.UnlessScore(self,target,operator)

  def jsontext(self) -> jsontextvalue:
    assert self.entity is not None
    return {'score':{'name':self.entity.expression(),'objective':self.objective.id}}

class Item: 
  @staticmethod
  def customModel(id:str,modeldata:int):
    return Item(id,{'CustomModelData':Int(modeldata)})

  def __init__(self,id:str,nbt:dict[str,Value[INbt]]|None=None) -> None:
    """
    アイテム/アイテムタグ

    id:
      "minecraft:stone" / "#logs"  / ...

    blockstates:
      {"axis":"x"} / ...

    nbt:
      {"Items":List[Compound]\\([])} / ...
    """
    self.id = id
    self.isTag = self.id.startswith('#')
    self.nbt = nbt

  def Give(self,count:int):
    if self.isTag:
      raise ValueError(f'cannot set blocktag: {self.expression()}')
    return Command.Give(self,count)

  def expression(self):
    result = self.id
    if self.nbt is not None:
      result += Compound(self.nbt).str()
    return result

  def ToNbt(self,count:int|None=None):
    """
    {"id":"minecraft:stone","Count":1b,"tag":{}}
    """
    value:dict[str, Value[INbt]] = {'id':Str(self.id)}
    if count:
      value['Count'] = Byte(count)
    if self.nbt is not None:
      value['tag'] = Compound(self.nbt)
    return Compound(value)

  def withNbt(self,nbt:dict[str,Value[INbt]]):
    nbt = self.nbt|nbt if self.nbt is not None else nbt
    return Item(self.id,nbt)

class Block:
  def __init__(self,id:str,blockstates:dict[str,str]={},nbt:dict[str,Value[INbt]]|None=None) -> None:
    """
    ブロック/ブロックタグ

    id:
      "minecraft:stone" / "#logs"  / ...

    blockstates:
      {"axis":"x"} / ...

    nbt:
      {"Items":List[Compound]\\([])} / ...
    """
    self.id = id
    self.isTag = self.id.startswith('#')
    self.blockstates = blockstates
    self.nbt = nbt

  def SetBlock(self,pos:Position.IPosition):
    if self.isTag:
      raise ValueError(f'cannot set blocktag: {self.expression()}')
    return Command.SetBlock(self,pos)

  def IfBlock(self,pos:Position.IPosition):
    return Execute.IfBlock(pos,self)

  def expression(self):
    result = self.id
    if self.blockstates:
      result += f'[{",".join( f"{k}={v}" for k,v in self.blockstates.items())}]'
    if self.nbt is not None:
      result += Compound(self.nbt).str()
    return result

  def withNbt(self,nbt:dict[str,Value[INbt]]):
    nbt = self.nbt|nbt if self.nbt is not None else nbt
    return Block(self.id,self.blockstates,nbt)

  def withStates(self,blockstates:dict[str,str]):
    blockstates = self.blockstates|blockstates
    return Block(self.id,blockstates,self.nbt)

@runtime_checkable
class _IJsonTextable(Protocol):
  @abstractmethod
  def jsontext(self) -> jsontextvalue:pass

def evaljsontext(jsontext:jsontext) -> jsontextvalue:
  match jsontext:
    case str():
      return jsontext
    case _IJsonTextable():
      return jsontext.jsontext()
    case list():
      return list(map(evaljsontext,jsontext))

jsontext:TypeAlias = str|_IJsonTextable|list['jsontext']

jsontextvalue:TypeAlias = str|list['jsontextvalue']|dict[str,Union[dict[str,str|dict[str,str]],bool,'jsontextvalue']]

class JsonText:
  class Decotation:
    """
    tellrawや看板で使うjsontextを装飾する
    """
    def __init__(
        self,
        value:jsontext,
        color:str|None=None,
        font:str|None=None,
        bold:bool|None=None,
        italic:bool|None=None,
        underlined:bool|None=None,
        strikethrough:bool|None=None,
        obfuscated:bool|None=None,
        insertion:str|None=None,
        click_run_command:Command|None=None,
        click_suggest_command:Command|str|None=None,
        click_copy_to_clipboard:str|None=None,
        click_open_url:str|None=None,
        click_change_page:int|None=None,
        hover_show_text:str|None=None,
        hover_show_item:Item|None=None,
        hover_show_entity:tuple[str,str,str]|None=None,
      ) -> None:
      """
      color: '#000000','reset','black','dark_blue','dark_green','dark_aqua','dark_red','dark_purple','gold','gray','dark_gray','blue','green','aqua','red','light_purple','yellow','white'

      click_run_command / click_suggest_command / click_copy_to_clipboard / click_open_url / click_change_page はどれか1つまで

      hover_show_text / hover_show_item / hover_show_entity はどれか1つまで
      """
      self.value = value
      self.color = color
      self.font = font
      self.bold = bold
      self.italic = italic
      self.underlined = underlined
      self.strikethrough = strikethrough
      self.obfuscated = obfuscated
      self.insertion = insertion
      self.click_run_command = click_run_command
      self.click_suggest_command = click_suggest_command
      self.click_copy_to_clipboard = click_copy_to_clipboard
      self.click_open_url = click_open_url
      self.click_change_page = click_change_page
      self.hover_show_text = hover_show_text
      self.hover_show_item = hover_show_item
      self.hover_show_entity = hover_show_entity

    def jsontext(self) -> jsontextvalue:
      jtext = evaljsontext(self.value)
      match jtext:
        case str():
          value:jsontextvalue = {"text":""}
          result = value
        case list():
          value:jsontextvalue = {"text":""}
          jtext.insert(0,value)
          result = jtext
        case _:
          value = jtext
          result = value

      def setValue(key:str,v:bool|str|None):
        if v is not None:
          value[key] = v

      setValue('color',self.color)
      setValue('font',self.font)
      setValue('bold',self.bold)
      setValue('italic',self.italic)
      setValue('underlined',self.underlined)
      setValue('strikethrough',self.strikethrough)
      setValue('obfuscated',self.obfuscated)
      setValue('insertion',self.insertion)

      if self.click_run_command:
        value["clickEvent"] = {"action":"run_command","value":self.click_run_command.export()}
      elif self.click_suggest_command:
        cmd = self.click_suggest_command
        if isinstance(cmd,Command):
          cmd = cmd.export()
        value["clickEvent"] = {"action":"suggest_command","value":cmd}
      elif self.click_copy_to_clipboard:
        value["clickEvent"] = {"action":"copy_to_clipboard","value":self.click_copy_to_clipboard}
      elif self.click_open_url:
        value["clickEvent"] = {"action":"open_url","value":self.click_open_url}

      if self.hover_show_text:
        value["hoverEvent"] = {"action":"show_text","contents":self.hover_show_text}
      elif self.hover_show_item:
        raise NotImplementedError('hover_show_item is not implemented')
      elif self.hover_show_entity:
        value["hoverEvent"] = {"action":"show_entity","contents":{
          "name":self.hover_show_entity[0],
          "type":self.hover_show_entity[1],
          "id":self.hover_show_entity[2]
        }}
      return result

  class Translate:
    """
    tellrawや看板で使うjsontextのtranslate
    """
    def __init__(self,key:str,with_:list[jsontext]) -> None:
      self.key = key
      self.with_ = with_

    def jsontext(self) -> jsontextvalue:
      return {"translate":self.key,"with": list(map(evaljsontext,self.with_))}

  class Keybind:
    """
    tellrawや看板で使うjsontextのkeybind
    """
    def __init__(self,key:str) -> None:
      self.key = key

    def jsontext(self) -> jsontextvalue:
      return {"keybind":self.key}




















# 本来は別ファイルとしてdatapack.libralyに格納すべきだが、
# 組み込んでおいたほうがエンティティセレクタから呼び出せて便利なので組み込む
class OhMyDat(IDatapackLibrary):
  using = False

  @classmethod
  def install(cls, datapack_path: Path, datapack_id: str) -> None:
    if not (datapack_path.parent/"OhMyDat").exists():
      print("installing OhMyDat")
      cp = subprocess.run(['git', 'clone', 'https://github.com/Ai-Akaishi/OhMyDat.git'],cwd=datapack_path.parent, encoding='utf-8', stderr=subprocess.PIPE)
      if cp.returncode != 0:
        raise ImportError(cp.stderr)

  @classmethod
  def uninstall(cls,datapack_path:Path) -> None:
    if (datapack_path.parent/"OhMyDat").exists():
      print("uninstalling OhMyDat")
      cls.rmtree(datapack_path.parent/"OhMyDat")

  @classmethod
  def Please(cls):
    cls.using = True
    return Command('function #oh_my_dat:please')

  _storage = StorageNbt('oh_my_dat:')
  _data = _storage['_',List[List[List[List[List[List[List[List[Compound]]]]]]]]][-4][-4][-4][-4][-4][-4][-4][-4]
  _scoreboard = Scoreboard(Objective('OhMyDatID'),Selector.Player('_'))

  @property
  @classmethod
  def data(cls):
    """エンティティごとのデータが格納されているstorage (Compound)"""
    cls.using = True
    return cls._data

  @classmethod
  def PleaseScore(cls,score:Scoreboard):
    """scoreboardのidにアクセス"""
    cls.using = True
    f = Function()
    f += cls._scoreboard.Oparation(score,'=')
    f += Command('function #oh_its_dat:please')
    return f.call()

  @classmethod
  def PleaseResult(cls,cmd:Command):
    """コマンドの実行結果のidにアクセス"""
    cls.using = True
    f = Function()
    f += cls._scoreboard.StoreResult() + cmd
    f += Command('function #oh_its_dat:please')
    return f.call()

  @classmethod
  def Release(cls):
    """
    明示的にストレージを開放

    他のデータパックのデータを消してしまう恐れがあるため使わない
    """
    cls.using = True
    return Command('function #oh_my_dat:release')
