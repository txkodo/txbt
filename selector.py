from __future__ import annotations
from abc import ABCMeta
import re
from typing import Literal, TypeVar
from datapack import Compound, IPredicate, ISelector, Objective, Position, Value
from mcpath import McPath
from util import float_to_str

class Selector(ISelector,metaclass=ABCMeta):
  _max_limit = 2147483647
  _mode:Literal['self','entity','player']

  def __init__(
      self,
      type:McPath|dict[McPath,bool]={},
      name:str|dict[str,bool]={},
      tag:bool|str|list[str]|dict[str,bool]={},
      team:bool|str|dict[str,bool]={},
      scores:dict[Objective,int|tuple[int,int]]={},
      advancements:dict[McPath,bool|dict[str,bool]]={},
      predicate:IPredicate|list[IPredicate]|dict[IPredicate,bool]={},
      gamemode:Literal["survival","creative","adventure","spectator"]|dict[Literal["survival","creative","adventure","spectator"],bool]={},
      nbt:Value[Compound]|dict[Value[Compound],bool]={},
      origin:Position.World|None=None,
      dx:float|None=None,
      dy:float|None=None,
      dz:float|None=None,
      distance:float|tuple[float,float]|None=None,
      pitch:float|tuple[float,float]|None=None,
      yaw:float|tuple[float,float]|None=None,
      level:int|tuple[int,int]|None=None,
      limit:int=_max_limit,
      sort:Literal['nearest','furthest','random','arbitrary']='arbitrary'
    ) -> None:
    """
    エンティティセレクタ

    実際に生成するときは以下を用いる

    EntitySelector.A() / EntitySelector.P() / EntitySelector.E() / EntitySelector.S() / EntitySelector.R()


    https://minecraft.fandom.com/ja/wiki/%E3%82%BF%E3%83%BC%E3%82%B2%E3%83%83%E3%83%88%E3%82%BB%E3%83%AC%E3%82%AF%E3%82%BF%E3%83%BC

    Parameters
    ----------
    type :
        "minecraft:armorstand" / {"armorstand":False,"marker":False}
        否定条件のみ複数使用可
    name :
        "foo" / {"foo":False,"bar":False,"buz":False}
        否定条件のみ複数使用可
    tag :
        True(1つ以上のタグを持つ) / False(いかなるタグも持たない) / "foo" / ["foo","bar"] / {"foo":True,"bar":False,"buz":False}
    team:
        True(1つ以上のチームに所属) / False(いかなるチームにも属さない) / "foo" / ["foo","bar"] / {"foo":False,"bar":False,"buz":False}
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

    self._init_type(type)
    self._init_name(name)
    self._init_tag(tag)
    self._init_team(team)
    self._init_scores(scores)
    self._init_advancements(advancements)
    self._init_predicate(predicate)
    self._init_gamemode(gamemode)
    self._init_nbt(nbt)
    self._origin = origin
    self._dx = dx
    self._dy = dy
    self._dz = dz
    self._distance = distance
    self._pitch = pitch
    self._yaw = yaw
    self._level = level
    self._limit = limit
    self._sort:Literal['nearest','furthest','random','arbitrary'] = sort

  def _init_type(self,type:McPath|dict[McPath,bool]):
    if self._mode == 'player' and type != {}:
      raise ValueError('@a/@p/@r selector must not have "type" argument')
    self._type:dict[McPath,bool] = {type:True} if isinstance(type,McPath) else {**type}

  def _init_name(self,name:str|dict[str,bool]):
    self._name:dict[str,bool] = {name:True} if isinstance(name,str) else {**name}

  def _init_tag(self,tag:bool|str|list[str]|dict[str,bool]):
    match tag:
      case bool():
        self._tag = {'':True}
      case str():
        self._tag = {tag:True}
      case list():
        self._tag = {i:True for i in tag}
      case dict():
        self._tag = {**tag}

  def _init_team(self,team:bool|str|dict[str,bool]):
    match team:
      case bool():
        self._team = {'':True}
      case str():
        self._team = {team:True}
      case dict():
        self._team = {**team}

  def _init_scores(self,scores:dict[Objective,int|tuple[int,int]]):
    self._scores = {**scores}

  def _init_advancements(self,advancements:dict[McPath,bool|dict[str,bool]]):
    self._advancements = { McPath(k): v if isinstance(v,bool) else { kk:vv for kk,vv in v.items()} for k,v in advancements.items()}

  def _init_predicate(self,predicate:IPredicate|list[IPredicate]|dict[IPredicate,bool]):
    match predicate:
      case IPredicate():
        self._predicate = {predicate:True}
      case list():
        self._predicate = { p:True for p in predicate}
      case dict():
        self._predicate = {**predicate}

  def _init_gamemode(self,gamemode:Literal["survival","creative","adventure","spectator"]|dict[Literal["survival","creative","adventure","spectator"],bool]):
    self._gamemode:dict[Literal["survival","creative","adventure","spectator"],bool]
    match gamemode:
      case str():
        self._gamemode = {gamemode:True}
      case dict():
        self._gamemode = { k:v for k,v in gamemode.items()}

  def _init_nbt(self,nbt:Value[Compound]|dict[Value[Compound],bool]):
    self._nbt:dict[Value[Compound],bool] = {nbt:True} if isinstance(nbt,Value) else {**nbt}

  def expression(self):

    def bool2str(x:bool):
      return str(x).lower()

    selectors:list[str] = []

    def decorate(key:str):
      def _inner(arg:tuple[str,bool]):
        type,flag = arg
        type = str(type)
        return f'{key}=' + ('' if flag else '!') + (f'"{type}"' if re.match('[! ]',type) else type)
      return _inner

    selectors.extend(map(decorate('type'),[ (str(k), v) for k,v in self._type.items()]))
    selectors.extend(map(decorate('name'),self._name.items()))
    selectors.extend(map(decorate('tag') ,self._tag.items()))
    selectors.extend(map(decorate('team'),self._team.items()))

    if self._scores:
      score_map:dict[str,str] = {}
      for score,value in self._scores.items():
        match value:
          case int():
            score_map[score.id] = str(value)
          case (int(),int()):
            score_map[score.id] = f'{value[0]}..{value[1]}'
      selectors.append(f'scores={{{",".join(f"{k}={v}" for k,v in score_map.items())}}}')

    if self._advancements:
      advancement_map:dict[str,str] = {}
      for advancement,value in self._advancements.items():
        advancement = str(advancement)
        match value:
          case bool():
            advancement_map[advancement] = bool2str(value)
          case dict():
            advancement_map[advancement] = f'{{{",".join(f"{str(k)}={bool2str(v)}" for k,v in value.items())}}}'
      selectors.append(f'advancements={{{",".join(f"{k}={v}" for k,v in advancement_map.items())}}}')

    selectors.extend(map(decorate('predicate'),[(str(k.path),v) for k,v in self._predicate.items()]))
    selectors.extend(map(decorate('gamemode'),self._gamemode.items()))
    selectors.extend(map(decorate('nbt'),[(str(k.str()),v) for k,v in self._nbt.items()]))

    if self._origin:
      for k,v in zip('xyz', self._origin.tuple()):
        selectors.append(f'{k}={float_to_str(v)}')

    if self._dx:selectors.append(f'dx={float_to_str(self._dx)}')
    if self._dy:selectors.append(f'dy={float_to_str(self._dy)}')
    if self._dz:selectors.append(f'dz={float_to_str(self._dz)}')

    if self._distance:
      match self._distance:
        case float() as v:
          selectors.append(f'distance={float_to_str(v)}')
        case (s,e):
          selectors.append(f'distance={float_to_str(s)}..{float_to_str(e)}')

    if self._pitch:
      match self._pitch:
        case float() as v:
          selectors.append(f'x_rotation={float_to_str(v)}')
        case (s,e):
          selectors.append(f'x_rotation={float_to_str(s)}..{float_to_str(e)}')

    if self._yaw:
      match self._yaw:
        case float() as v:
          selectors.append(f'y_rotation={float_to_str(v)}')
        case (s,e):
          selectors.append(f'y_rotation={float_to_str(s)}..{float_to_str(e)}')

    if self._level:
      match self._level:
        case float() as v:
          selectors.append(f'level={v}')
        case (s,e):
          selectors.append(f'level={s}..{e}')

    self._limit
    self._sort

    match self._mode:
      case 'self':
        selector = '@s'
      case 'entity':
        selector = '@e'
        if self._limit != self._max_limit:
          selectors.append(f'limit={self._limit}')
        if self._sort != 'arbitrary':
          selectors.append(f'sort={self._sort}')
      case 'player':
        match (self._sort,self._limit):
          case ('arbitrary',self._max_limit):
            selector = '@a'
          case (sort,self._max_limit):
            selector = '@a'
            selectors.append(f'sort={sort}')
          case ('random',1):
            selector = '@r'
          case ('random',limit):
            selector = '@r'
            selectors.append(f'limit={limit}')
          case ('nearest',1):
            selector = '@p'
          case ('nearest',limit):
            selector = '@p'
            selectors.append(f'limit={limit}')
          case ('arbitrary',limit):
            selector = '@a'
            selectors.append(f'limit={limit}')
          case ('furthest',1):
            selector = '@p'
            selectors.append(f'sort=furthest')
          case ('furthest',limit):
            selector = '@a'
            selectors.append(f'sort=furthest')
            selectors.append(f'limit={limit}')

    if selectors:
      return f'{selector}[{",".join(selectors)}]'
    else:
      return selector

  def __and__(self:_Selector,other:_Selector):
    return self.merge(other)

  def merge(self:_Selector,other:_Selector):
    def error():
      raise ValueError(f'failed to merge selectors "{self}" and "{other}".')

    N = TypeVar('N',int,float)
    def merge_range(x:N|tuple[N,N],y:N|tuple[N,N]) -> N|tuple[N,N]:
      if not isinstance(x,tuple): x = (x,x)
      if not isinstance(y,tuple): y = (y,y)
      r = (max(x[0],y[0]),min(x[1],y[1]))
      if r[0] > r[1]:error()
      elif r[0] == r[1]:
        return r[0]
      return r

    def merge_range_or_none(x:None|N|tuple[N,N],y:None|N|tuple[N,N]) -> None|N|tuple[N,N]:
      if x is None: return y
      if y is None: return x
      return merge_range(x,y)

    if self._mode != other._mode: error()
    if self._limit != other._limit: error()
    if self._sort != other._sort: error()

    type = {**self._type}
    for k,v in other._type.items():
      if k in type :
        if  type[k] != v:error()
      else: type[k] = v
    if any(type.values()) and len(type) != 1:error()

    name = {**self._name}
    for k,v in other._name.items():
      if k in name :
        if  name[k] != v:error()
      else: name[k] = v
    if any(name.values()) and len(name) != 1:error()

    tag = {**self._tag}
    for k,v in other._tag.items():
      if k in tag: assert tag[k] == v
      else: tag[k] = v

    team = {**self._team}
    for k,v in other._team.items():
      if k in team:
        if team[k] != v:error()
      else: team[k] = v
    if any(team.values()) and len(team) != 1:error()

    scores = {**self._scores}
    for k,v in other._scores.items():
      if k in scores:
        scores[k] = merge_range(scores[k],v)
      else: scores[k] = v

    advancements:dict[McPath, bool | dict[str, bool]] = {**self._advancements}
    for k,v in other._advancements.items():
      if k in advancements:
        if isinstance(v,bool):
          if advancements[k] != v:error()
        elif isinstance(advancements[k],bool):error()
        else:
          adv = advancements[k]
          assert isinstance(adv,dict)
          for kk,vv in v.items():
            if kk in adv:
              if adv[kk] != vv:error()
            else:
              adv[kk] = vv
      else: advancements[k] = v

    predicate = {**self._predicate}
    for k,v in other._predicate.items():
      if k in predicate:
        if predicate[k] != v:error()
      else: predicate[k] = v

    gamemode:dict[Literal['survival', 'creative', 'adventure', 'spectator'], bool] = {k:v for k,v in self._gamemode.items()}
    for k,v in other._gamemode.items():
      if k in gamemode:
        if gamemode[k] != v:error()
      else: gamemode[k] = v
    if any(gamemode.values()) and len(gamemode) != 1:error()

    # TODO: nbtのdeepmerge
    nbt = {**self._nbt}
    for k,v in other._nbt.items():
      if k in nbt:
        if nbt[k] != v:error()
      else: nbt[k] = v
    
    if self._origin and other._origin and self._origin != other._origin:error()
    origin = self._origin or other._origin

    if self._dx and other._dx and self._dx != other._dx:error()
    dx = self._dx or other._dx

    if self._dy and other._dy and self._dy != other._dy:error()
    dy = self._dy or other._dy

    if self._dz and other._dz and self._dz != other._dz:error()
    dz = self._dz or other._dz
    
    distance = merge_range_or_none(self._distance,other._distance)
    pitch = merge_range_or_none(self._pitch,other._pitch)
    yaw = merge_range_or_none(self._yaw,other._yaw)
    level = merge_range_or_none(self._level,other._level)

    result = Selector(
      type,
      name,
      tag,
      team,
      scores,
      advancements,
      predicate,
      gamemode,
      nbt,
      origin,
      dx,
      dy,
      dz,
      distance,
      pitch,
      yaw,
      level,
      self._limit,
      self._sort
    )
    return result

  def ToSelf(self):
    return 

  def ToEntity(self):
    return 

  def ToPlayer(self):
    return 

  @staticmethod
  def S(
      type:McPath|dict[McPath,Literal[False]]={},
      name:str|dict[str,Literal[False]]={},
      tag:bool|str|list[str]|dict[str,bool]={},
      team:bool|str|dict[str,Literal[False]]={},
      scores:dict[Objective,int|tuple[int,int]]={},
      advancements:dict[McPath,bool|dict[str,bool]]={},
      predicate:IPredicate|list[IPredicate]|dict[IPredicate,bool]={},
      gamemode:Literal["survival","creative","adventure","spectator"]|dict[Literal["survival","creative","adventure","spectator"],Literal[False]]={},
      nbt:Value[Compound]|dict[Value[Compound],bool]={},
      origin:Position.World|None=None,
      dx:float|None=None,
      dy:float|None=None,
      dz:float|None=None,
      distance:float|tuple[float,float]|None=None,
      pitch:float|tuple[float,float]|None=None,
      yaw:float|tuple[float,float]|None=None,
      level:int|tuple[int,int]|None=None
      ):
    """@s[...]"""
    return _SelfSelector(
      type,
      name,
      tag,
      team,
      scores,
      advancements,
      predicate,
      gamemode,
      nbt,
      origin,
      dx,
      dy,
      dz,
      distance,
      pitch,
      yaw,
      level,
      1,
      'arbitrary'
      )
  
  @staticmethod
  def E(
      type:McPath|dict[McPath,Literal[False]]={},
      name:str|dict[str,Literal[False]]={},
      tag:bool|str|list[str]|dict[str,bool]={},
      team:bool|str|dict[str,Literal[False]]={},
      scores:dict[Objective,int|tuple[int,int]]={},
      advancements:dict[McPath,bool|dict[str,bool]]={},
      predicate:IPredicate|list[IPredicate]|dict[IPredicate,bool]={},
      gamemode:Literal["survival","creative","adventure","spectator"]|dict[Literal["survival","creative","adventure","spectator"],Literal[False]]={},
      nbt:Value[Compound]|dict[Value[Compound],bool]={},
      origin:Position.World|None=None,
      dx:float|None=None,
      dy:float|None=None,
      dz:float|None=None,
      distance:float|tuple[float,float]|None=None,
      pitch:float|tuple[float,float]|None=None,
      yaw:float|tuple[float,float]|None=None,
      level:int|tuple[int,int]|None=None,
      limit:int=_max_limit,
      sort:Literal['nearest','furthest','random','arbitrary']='arbitrary'
      ):
    """@e[...]"""
    return _EntitySelector(
      type,
      name,
      tag,
      team,
      scores,
      advancements,
      predicate,
      gamemode,
      nbt,
      origin,
      dx,
      dy,
      dz,
      distance,
      pitch,
      yaw,
      level,
      limit,
      sort
      )
  
  @staticmethod
  def A(
      name:str|dict[str,Literal[False]]={},
      tag:bool|str|list[str]|dict[str,bool]={},
      team:bool|str|dict[str,Literal[False]]={},
      scores:dict[Objective,int|tuple[int,int]]={},
      advancements:dict[McPath,bool|dict[str,bool]]={},
      predicate:IPredicate|list[IPredicate]|dict[IPredicate,bool]={},
      gamemode:Literal["survival","creative","adventure","spectator"]|dict[Literal["survival","creative","adventure","spectator"],Literal[False]]={},
      nbt:Value[Compound]|dict[Value[Compound],bool]={},
      origin:Position.World|None=None,
      dx:float|None=None,
      dy:float|None=None,
      dz:float|None=None,
      distance:float|tuple[float,float]|None=None,
      pitch:float|tuple[float,float]|None=None,
      yaw:float|tuple[float,float]|None=None,
      level:int|tuple[int,int]|None=None,
      limit:int=_max_limit,
      sort:Literal['nearest','furthest','random','arbitrary']='arbitrary'
      ):
    """@a[...]"""
    return _PlayerSelector(
      {},
      name,
      tag,
      team,
      scores,
      advancements,
      predicate,
      gamemode,
      nbt,
      origin,
      dx,
      dy,
      dz,
      distance,
      pitch,
      yaw,
      level,
      limit,
      sort
      )

  @staticmethod
  def P(
      name:str|dict[str,Literal[False]]={},
      tag:bool|str|list[str]|dict[str,bool]={},
      team:bool|str|dict[str,Literal[False]]={},
      scores:dict[Objective,int|tuple[int,int]]={},
      advancements:dict[McPath,bool|dict[str,bool]]={},
      predicate:IPredicate|list[IPredicate]|dict[IPredicate,bool]={},
      gamemode:Literal["survival","creative","adventure","spectator"]|dict[Literal["survival","creative","adventure","spectator"],Literal[False]]={},
      nbt:Value[Compound]|dict[Value[Compound],bool]={},
      origin:Position.World|None=None,
      dx:float|None=None,
      dy:float|None=None,
      dz:float|None=None,
      distance:float|tuple[float,float]|None=None,
      pitch:float|tuple[float,float]|None=None,
      yaw:float|tuple[float,float]|None=None,
      level:int|tuple[int,int]|None=None,
      limit:int=1,
      sort:Literal['nearest','furthest','random','arbitrary']='nearest'
      ):
    """@a[...]"""
    return _PlayerSelector(
      {},
      name,
      tag,
      team,
      scores,
      advancements,
      predicate,
      gamemode,
      nbt,
      origin,
      dx,
      dy,
      dz,
      distance,
      pitch,
      yaw,
      level,
      limit,
      sort
      )

  @staticmethod
  def R(
      name:str|dict[str,Literal[False]]={},
      tag:bool|str|list[str]|dict[str,bool]={},
      team:bool|str|dict[str,Literal[False]]={},
      scores:dict[Objective,int|tuple[int,int]]={},
      advancements:dict[McPath,bool|dict[str,bool]]={},
      predicate:IPredicate|list[IPredicate]|dict[IPredicate,bool]={},
      gamemode:Literal["survival","creative","adventure","spectator"]|dict[Literal["survival","creative","adventure","spectator"],Literal[False]]={},
      nbt:Value[Compound]|dict[Value[Compound],bool]={},
      origin:Position.World|None=None,
      dx:float|None=None,
      dy:float|None=None,
      dz:float|None=None,
      distance:float|tuple[float,float]|None=None,
      pitch:float|tuple[float,float]|None=None,
      yaw:float|tuple[float,float]|None=None,
      level:int|tuple[int,int]|None=None,
      limit:int=1,
      sort:Literal['nearest','furthest','random','arbitrary']='random'
      ):
    """@a[...]"""
    return _PlayerSelector(
      {},
      name,
      tag,
      team,
      scores,
      advancements,
      predicate,
      gamemode,
      nbt,
      origin,
      dx,
      dy,
      dz,
      distance,
      pitch,
      yaw,
      level,
      limit,
      sort
      )
  
  def ToEntitySelector(self):
    return _EntitySelector(
      self._type,
      self._name,
      self._tag,
      self._team,
      self._scores,
      self._advancements,
      self._predicate,
      self._gamemode,
      self._nbt,
      self._origin,
      self._dx,
      self._dy,
      self._dz,
      self._distance,
      self._pitch,
      self._yaw,
      self._level,
      self._limit,
      self._sort
      )

  def ToPlayerSelector(self):
    return _PlayerSelector(
      {},
      self._name,
      self._tag,
      self._team,
      self._scores,
      self._advancements,
      self._predicate,
      self._gamemode,
      self._nbt,
      self._origin,
      self._dx,
      self._dy,
      self._dz,
      self._distance,
      self._pitch,
      self._yaw,
      self._level,
      self._limit,
      self._sort
      )

  def ToSelfSelector(self):
    return _SelfSelector(
      self._type,
      self._name,
      self._tag,
      self._team,
      self._scores,
      self._advancements,
      self._predicate,
      self._gamemode,
      self._nbt,
      self._origin,
      self._dx,
      self._dy,
      self._dz,
      self._distance,
      self._pitch,
      self._yaw,
      self._level,
      1,
      'arbitrary'
      )

  @staticmethod
  def Player(name:str):
    return NameSelector(name)

_Selector = TypeVar('_Selector',bound=Selector)

class _EntitySelector(Selector):
  _mode = 'entity'

class _PlayerSelector(Selector):
  _mode = 'player'

class _SelfSelector(Selector):
  _mode = 'self'

class NameSelector(ISelector):
  """
  プレイヤー名を直接使うセレクタ
  txkodo[gamemode=survival]
  """
  def __init__(self,player:str):
    self.player = player
  
  def expression(self) -> str:
    return self.player
