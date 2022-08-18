from pathlib import Path
from random import randint
from datapack import Command, ExistFunction, Function, FunctionTag, IDatapackLibrary, Selector, StorageNbt, Str

_id_upper = tuple(map(chr, range(ord('A'), ord('Z')+1)))
_id_lower = tuple(map(chr, range(ord('a'), ord('z')+1)))
_id_number = tuple(map(chr, range(ord('0'), ord('9')+1)))

def _gen_id(length: int = 8, prefix: str = '', suffix: str = '', upper: bool = True, lower: bool = True, number: bool = True):
  """{length=8}桁のIDを生成する [0-9a-zA-Z]"""
  chars: list[str] = []
  if upper:
    chars.extend(_id_upper)
  if lower:
    chars.extend(_id_lower)
  if number:
    chars.extend(_id_number)
  maxidx = len(chars) - 1
  return prefix + ''.join(chars[randint(0, maxidx)] for _ in range(length)) + suffix

build_id = _gen_id(16,upper=False)
def setBuildId(id:str):
  global build_id
  build_id = id

class OnInstall(IDatapackLibrary):
  _uninstall_all_func = Function()
  install_func = Function(commands=[_uninstall_all_func.call()])
  uninstall_func = Function()

  @classmethod
  def install(cls, datapack_path: Path, datapack_id: str) -> None:
    build_nbt = StorageNbt('install:')['build_ids'][datapack_id, Str]

    # installの解決
    cls.install_func.set_name('install',f'{datapack_id}/install')
    load = Function()
    load += build_nbt.notMatch(Str(build_id)) + cls.install_func.call()
    cls.install_func += build_nbt.set(Str(build_id))
    cls.install_func += Command.Tellraw(Selector.A(),f"[{datapack_id}] installed build_id={build_id}")
    FunctionTag.load.append(load)

    cls._uninstall_all_func

    cls.uninstall_func += Command.Tellraw(Selector.A(),f"[{datapack_id}] uninstalled build_id={build_id}")
    cls.uninstall_func.set_name('install',f'{datapack_id}/uninstall/{build_id}')
    cls.uninstall_func.delete_on_regenerate = False

    # uninstall_all
    uninstallpath = datapack_path/f'data/install/functions/{datapack_id}/uninstall'
    if uninstallpath.exists():
      for func in uninstallpath.iterdir():
        if func.suffix == '.mcfunction':
          if func.stem == build_id:
            raise ValueError(f'build_id {build_id} is not unique id')
          cls._uninstall_all_func += build_nbt.isMatch(Str(func.stem)) + ExistFunction('install',f'{datapack_id}/uninstall/{func.stem}').call()

    # uninstallの解決
    uninstall_func = Function('install',f'{datapack_id}/uninstall')

    uninstall_func += build_nbt.isMatch(Str(build_id)) + cls.uninstall_func.call()

    cls.uninstall_func += build_nbt.remove()
