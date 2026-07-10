from pathlib import Path
from core.version import APP_AUTHOR, APP_COPYRIGHT, APP_EXE_NAME, APP_NAME, APP_VERSION

major, minor, patch = APP_VERSION.split(".")
version_tuple = f"({major}, {minor}, {patch}, 0)"

content = f'''VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={version_tuple},
    prodvers={version_tuple},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040504B0',
        [
          StringStruct('CompanyName', '{APP_AUTHOR}'),
          StringStruct('FileDescription', '{APP_NAME}'),
          StringStruct('FileVersion', '{APP_VERSION}'),
          StringStruct('InternalName', '{APP_EXE_NAME}'),
          StringStruct('OriginalFilename', '{APP_EXE_NAME}.exe'),
          StringStruct('ProductName', '{APP_NAME}'),
          StringStruct('ProductVersion', '{APP_VERSION}'),
          StringStruct('LegalCopyright', '{APP_COPYRIGHT}')
        ]
      )
    ]),
    VarFileInfo([VarStruct('Translation', [1029, 1200])])
  ]
)
'''

Path("version_info.txt").write_text(content, encoding="utf-8")
print(f"Vytvořeno version_info.txt pro verzi {APP_VERSION}")