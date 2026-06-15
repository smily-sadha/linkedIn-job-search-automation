' Launches the dashboard batch file completely hidden (no console window, no
' taskbar flash). Used by the Startup-folder shortcut so the web dashboard
' starts automatically at login and keeps running 24/7.
Set sh = CreateObject("WScript.Shell")
sh.Run """d:\D\main copy\job search autiomation\deploy\run_dashboard.bat""", 0, False
