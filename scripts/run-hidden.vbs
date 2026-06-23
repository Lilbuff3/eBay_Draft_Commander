Set WshShell = CreateObject("WScript.Shell")
If WScript.Arguments.Count = 0 Then
    WScript.Quit
End If

Set FSO = CreateObject("Scripting.FileSystemObject")

' Rebuild the command line arguments
Dim cmdLine
cmdLine = ""

' Resolve the first argument (the executable/script) to an absolute path if it exists
Dim firstArg
firstArg = WScript.Arguments(0)
If FSO.FileExists(firstArg) Then
    firstArg = FSO.GetAbsolutePathName(firstArg)
End If

If InStr(firstArg, " ") > 0 Then
    cmdLine = """" & firstArg & """"
Else
    cmdLine = firstArg
End If

For i = 1 To WScript.Arguments.Count - 1
    Dim arg
    arg = WScript.Arguments(i)
    ' If this argument is a file that exists, resolve it to absolute path too
    If FSO.FileExists(arg) Then
        arg = FSO.GetAbsolutePathName(arg)
    End If
    If InStr(arg, " ") > 0 Then
        arg = """" & arg & """"
    End If
    cmdLine = cmdLine & " " & arg
Next

' Run hidden (window style 0, wait for completion False)
WshShell.Run cmdLine, 0, False
