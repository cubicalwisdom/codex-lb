Option Explicit

Dim shell
Dim appDir
Dim batPath

appDir = "H:\Opencode IDE\codex-ib\codex-lb"
batPath = appDir & "\scripts\windows\start-codex-ib-hidden.bat"

Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = appDir
shell.Run """" & batPath & """", 0, False
