"""Compile application sources and package a runnable ZIP."""
import pathlib
import py_compile
import zipfile

root = pathlib.Path(__file__).resolve().parents[1]
destination = root / 'dist'
destination.mkdir(exist_ok=True)
with zipfile.ZipFile(destination / 'calculator-web.zip', 'w') as archive:
    for name in ('calculator.py', 'webapp.py'):
        py_compile.compile(str(root / name), doraise=True)
        archive.write(root / name, name)
    archive.writestr(
        '__main__.py',
        'import runpy\nrunpy.run_module("webapp", run_name="__main__")\n')
print('Build successful: dist/calculator-web.zip')
