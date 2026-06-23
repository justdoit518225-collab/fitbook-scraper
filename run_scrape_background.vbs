' 背景執行 scrape_fitbook.py，不顯示終端機視窗（手動測試用）
Option Explicit

Dim shell, fso, root, pythonw, script, pathFile

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)
pathFile = root & "\.run_pythonw_path.txt"

If fso.FileExists(pathFile) Then
    pythonw = Trim(fso.OpenTextFile(pathFile, 1).ReadAll())
Else
    pythonw = "pythonw.exe"
End If

script = root & "\scrape_fitbook.py"
shell.CurrentDirectory = root
shell.Run """" & pythonw & """ """ & script & """", 0, False
