from pathlib import Path
from random import randint
from datapack import Function, FunctionTag, IDatapackLibrary, Mcpath, StorageNbt, Str


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



class OnInstall(IDatapackLibrary):
  install_func = Function()
  uninstall_func = Function()

  install_path: Mcpath
  uninstall_path:Mcpath

  @classmethod
  def install(cls, datapack_path: Path, datapack_id: str) -> None:
    if not hasattr(cls, 'install_path'):
      'please set OnInstall.install_path before export datapack'
    if not hasattr(cls, 'uninstall_path'):
      'please set OnInstall.uninstall_path before export datapack'

    build_nbt = StorageNbt('pydp:')['build_ids'][datapack_id, Str]

    # installの解決
    buildid = _gen_id(16,upper=False)
    cls.install_func.set_name(
        cls.install_path.namespace, cls.install_path.name)
    load = Function()
    load += build_nbt.notMatch(Str(buildid)) + cls.install_func.call()
    cls.install_func += build_nbt.set(Str(buildid))
    FunctionTag.load.append(load)

    # uninstallの解決
    cls.uninstall_func.set_name(cls.uninstall_path.namespace,
                           cls.uninstall_path.name)
    cls.uninstall_func += build_nbt.remove()
