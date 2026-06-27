Draft Commander — desktop launchers
===================================

Start Draft Commander.bat
  - Launches the backend under the supervisor (backend/run_service.py), hidden
    (no console window). The server keeps running after this window closes.
  - Waits until the server answers /api/system/health, then opens the app in
    your browser (http://127.0.0.1:5000/app/).
  - Because it runs under the supervisor, the in-app "Restart" button works.

Stop Draft Commander.bat
  - Stops the supervisor first (so it won't relaunch), then the server child.
  - Use this to fully shut the backend down.

Notes
  - Uses Python 3.12 at "C:\Program Files\Python312\pythonw.exe".
    If you move/upgrade Python, edit the path in Start Draft Commander.bat.
  - Project path is hard-coded to the canonical location:
    C:\Users\adam\Projects\ebay-draft-commander
  - Logs: data/supervisor.log (supervisor) and data/backend_service.log (server).
