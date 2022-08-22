from typing import Literal
from datapack import Command, Byte, Compound, Selector, INbt, Item, List, Function, Position, Str, Value
from id import gen_id
from library.item_frame_hook import ItemFrameHook
from txbt import IEvent, InitAbort, Run, WaitFunctionCall

class ItemFrame:
  onOut:Function
  onIn:Function
  onRot:Function
  _init = False

  @classmethod
  def init(cls):
    if cls._init:
      return
    cls._init = True
    cls.onOut = Function()
    ItemFrameHook.OnOut.append(cls.onOut)
    cls.onIn = Function()
    ItemFrameHook.OnIn.append(cls.onIn)
    cls.onRot = Function()
    ItemFrameHook.OnRot.append(cls.onRot)

  def __init__(self) -> None:
    self.__class__.init()
    self.id = gen_id(prefix='IFH.')
    self.tags = [self.id,'IFH']
    self.selector = Selector.E('item_frame',tag=self.id,limit=1)
    self.selfselector = Selector.S(tag=self.id)
    self._fixed = self.selector.nbt['Fixed',Byte]
    self._invulnerable = self.selector.nbt['Invulnerable',Byte]

  def Summon(self,pos:Position.IPosition,item:Item|None = None):
    """額縁を召喚

    回転：×、取得：×
    """
    if item:
      return Command.Summon(
        'item_frame',
        pos,
        Tags=List[Str]([Str(tag) for tag in self.tags]),
        Invulnerable=Byte(1),
        Facing=Byte(1),
        Fixed=Byte(1),
        Item=item.ToNbt(1)
        )
    else:
      return Command.Summon(
        'item_frame',
        pos,
        Tags=List[Str]([Str(tag) for tag in self.tags]),
        Invulnerable=Byte(1),
        Facing=Byte(1),
        Fixed=Byte(1)
        )

  def SummonEvent(self, pos: Position.IPosition, item: Item | None = None) -> IEvent:
    """
    額縁を召喚するだけのイベント
    初期化時に該当額縁をkillする
    """
    kill = self.Kill()
    return InitAbort(Run(self.Summon(pos, item)), init=Function(commands=[kill]), abort=Function(commands=[kill]))

  def Kill(self):
    return Command.Kill(self.selector)

  def SetState(self,i:bool,o:bool,r:bool):
    return self.selector.As() + ItemFrameHook.ChangeState(i,o,r)

  def _getnbt(self,item:Item|None=None,rotation:Literal[0,1,2,3,4,5,6,7]|None=None):
    d:dict[str,Value[INbt]] = {}
    if item is not None:
      d["Item"] = item.ToNbt()
    if rotation is not None:
      d["ItemRotation"] = Byte(rotation)
    return Compound(d)

  def item(self):
    """{id:Str,Count:Byte,tag:{CustomModelData:Int}}"""
    return self.selector.nbt["Item"]

  def rotation(self):
    """Byte"""
    return self.selector.nbt["ItemRotation",Byte]

  def ItemCondition(self,item:Item):
    return self.selector.filter(nbt=self._getnbt(item)).IfEntity()

  def RotateCondition(self,rotation:Literal[0,1,2,3,4,5,6,7]):
    return self.selector.filter(nbt=self._getnbt(rotation=rotation)).IfEntity()

  def ItemRotateCondition(self,item:Item,rotation:Literal[0,1,2,3,4,5,6,7]):
    return self.selector.filter(nbt=self._getnbt(item,rotation)).IfEntity()

  def WaitUntilPut(self):
    """何かしらのアイテムが入れられるまで待機
    """
    func = Function()
    ItemFrame.onIn += self.selfselector.IfEntity() + func.Call()
    return WaitFunctionCall(func)

  def WaitUntilPutItem(self, item:Item):
    """特定のアイテムが入れられるまで待機
    """
    func = Function()
    ItemFrame.onIn += self.selfselector.filter(nbt=self._getnbt(item)).IfEntity() + func.Call()
    return WaitFunctionCall(func)

  def WaitUntilPick(self):
    """中のアイテムを失うまで待機
    """
    func = Function()
    ItemFrame.onOut += self.selfselector.IfEntity() + func.Call()
    return WaitFunctionCall(func)

  def WaitUntilRotate(self):
    """回転するまで待機
    """
    func = Function()
    ItemFrame.onRot += self.selfselector.IfEntity() + func.Call()
    return WaitFunctionCall(func)

  def WaitUntilRotateTo(self,rotation:Literal[0,1,2,3,4,5,6,7]):
    """特定の角度になるまで待機
    """
    func = Function()
    ItemFrame.onRot += self.selfselector.filter(nbt=self._getnbt(rotation=rotation)).IfEntity() + func.Call()
    return WaitFunctionCall(func)

  def WaitUntilMatchState(self,item:Item,rotation:Literal[0,1,2,3,4,5,6,7]):
    """特定のアイテムが入った状態で特定の角度になるまで待機
    """
    func = Function()
    ItemFrame.onRot += self.selfselector.filter(nbt=self._getnbt(item,rotation)).IfEntity() + func.Call()
    ItemFrame.onIn += self.selfselector.filter(nbt=self._getnbt(item,rotation)).IfEntity() + func.Call()
    return WaitFunctionCall(func)
