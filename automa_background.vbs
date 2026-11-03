Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "F:\automa"
WshShell.Run """F:\automa\.venv\Scripts\pythonw.exe"" -m automa.cli autostart", 0, False

