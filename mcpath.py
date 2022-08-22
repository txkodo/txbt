from __future__ import annotations
from pathlib import Path
import re
from typing_extensions import Self

class McPathError(Exception):pass

class McPath:
  default_namespace = 'minecraft'
  _namespace:str
  _parts:list[str]
  _istag:bool

  def __new__(cls: type[Self],mcpath:str|McPath|None=None) -> Self:
    match mcpath:
      case McPath():
        return mcpath
      case None:
        self = super().__new__(cls)
        self._namespace = cls.default_namespace
        self._parts = []
        return self
      case str():
        self = super().__new__(cls)
        match = re.fullmatch(r'(#?)(?:([0-9a-z_\.-]*)\:)?((?:[0-9a-z_\.-]+/)*[0-9a-z_\.-]*)',mcpath)
        if not match:
          raise McPathError(f'"{mcpath}" is not valid ResourceLocation')
        self._istag = match.groups()[0] == '#'
        self._namespace = match.groups()[1] or 'minecraft'
        self._parts = match.groups()[2].split('/')
        return self
  
  @property
  def istag(self):
    return self._istag

  def __str__(self) -> str:
    return self.str

  @property
  def str(self) -> str:
    if self._namespace == self.default_namespace:
      if self.istag:
        return '#' + '/'.join(self.parts)
      if self.parts:
        return '/'.join(self.parts)
      else:
        return ':'
    return ('#' if self.istag else '') + self._namespace + ':' + '/'.join(self.parts)

  def __truediv__(self,path:str):
    if self._parts and self._parts[-1] == '':
      raise McPathError(f'"{str(self)}/{path}" is not valid ResourceLocation')
    match = re.fullmatch(r'(?:[0-9a-z_\.-]+/)*[0-9a-z_\.-]*',path)
    if not match:
      raise McPathError(f'"{str(self)}/{path}" is not valid ResourceLocation')
    result = McPath()
    result._namespace = self._namespace
    result._parts = self._parts + path.split('/')
    result._istag = self._istag
    return result

  @property
  def parent(self):
    if not self._parts:
      raise McPathError(f'"{str(self)}" is root ResourceLocation')
    result = McPath()
    result._namespace = self._namespace
    result._parts = self._parts[:-1]
    return result

  @property
  def namespace(self):
    return self._namespace

  @property
  def parts(self):
    return self._parts

  @property
  def name(self):
    return '/'.join(self._parts)

  def function(self,root:Path):
    assert not self.istag
    return root/'data'/self._namespace/'functions'/('/'.join(self._parts)+'.mcfunction')

  def function_dir(self,root:Path):
    assert not self.istag
    return root/'data'/self._namespace/'functions'/('/'.join(self._parts))

  def function_tag(self,root:Path):
    assert self.istag
    return root/'data'/self._namespace/'tags/functions'/('/'.join(self._parts)+'.json')

  def predicate(self,root:Path):
    assert not self.istag
    return root/'data'/self._namespace/'predicates'/('/'.join(self._parts)+'.json')

