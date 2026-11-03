$ErrorActionPreference='Stop'
$root=$PSScriptRoot
$python='D:\Anaconda\python.exe'
if(!(Test-Path -LiteralPath $python)){throw '请用已安装 PyQt5/numpy/scipy 的 Python 执行 app.py'}
& $python (Join-Path $root 'app.py')
