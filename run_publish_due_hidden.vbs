' Runs run_publish_due.bat with no visible console window.
'
' Task Scheduler runs this every 10 minutes. Without this wrapper a black
' console window would flash on screen every 10 minutes all day, which is
' maddening. The "0" below is the hidden window style; the "False" means do
' not wait for it to finish.
'
' The final "True" means WAIT for the batch file to finish. That matters: if
' this script exited immediately, Task Scheduler would mark the task complete
' within a second, and its own "do not start a second copy" rule would never
' apply. A slow run could then overlap the next 10-minute tick and publish the
' same post twice. publish_due.py also takes its own lock as a second guard.

Dim shell, here
Set shell = CreateObject("WScript.Shell")
here = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = here
shell.Run """" & here & "\run_publish_due.bat""", 0, True
