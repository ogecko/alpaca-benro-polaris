# Installation Troubleshooting
Problems installing, starting or updating the Alpaca Driver, including setup.bat, uv and Python packages, Windows security warnings, opening Alpaca Pilot and starting the driver at boot.

See [Troubleshooting](./troubleshooting.md) for the other guides, and the [FAQ](./faq.md) for common questions.

## A1 - Git or uv Won't Install
`setup.bat` installs [Git](https://git-scm.com) with `winget` (built into Windows 11), and falls back to downloading the official Git installer, so it needs an internet connection. If it stops with `Git could not be installed` or `uv could not be installed`, install the missing tool yourself and run `setup.bat` again:

* **Git**: download and run the installer from https://git-scm.com/download/win
* **uv**: open PowerShell and run `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`, or see the [uv installation guide](https://docs.astral.sh/uv/getting-started/installation/)

You do **not** need to install Python: uv downloads the correct version by itself, and the driver never uses any other Python on your PC.

## A2 - uv Download Fails
In some countries, your ISP's Domain Name Servers may redirect traffic to invalid Python Package servers. If `setup.bat` fails at step 3 (`uv sync`) with errors like the following.
```
error: Failed to fetch: `https://pypi.org/simple/falcon/`
```
You can force Windows to resolve the host names for the Python Package servers to their correct IPv4 addresses. Using Administrator, edit the file `hosts` in the directory 
`C:\Windows\System32\drivers\etc`. Add the following two lines to the end of the `hosts` file, then run `setup.bat` again.
```
151.101.0.223 pypi.org
151.101.0.233 files.pythonhosted.org

```

## A3 - ModuleNotFoundError

The Alpaca Driver requires certain Python packages to be installed before it can run. If you encounter an error like the following when first launching the Driver:

```text
Traceback (most recent call last):
  File "D:\Astro\Bin\alpaca-benro-polaris\driver\main.py", line 38, in <module>
    import discovery
  File "D:\Astro\Bin\alpaca-benro-polaris\driver\discovery.py", line 8, in <module>
    from config import Config
  File "D:\Astro\Bin\alpaca-benro-polaris\driver\config.py", line 36, in <module>
    import os, toml, json
ModuleNotFoundError: No module named 'toml'
```

This indicates that the required dependencies have not yet been installed.

To resolve this, run `setup.bat` again (see the [Installation Guide](./installation.md)). It installs all the Python packages the Driver needs, including `toml`. If you only want to reinstall the packages, run this from the project root:

```command
uv sync --locked
```

## A4 - Smart App Control
If Windows shows a **Smart App Control blocked a file that may be unsafe** message while installing or running the driver, it comes from Smart App Control (SAC), a built-in Windows 11 security feature introduced in the 22H2 update. SAC blocks untrusted or unsigned applications, especially those downloaded from the internet. For the Mini-PC, we recommend turning off Smart App Control.

To turn off Smart App Control

1. Open Settings
2. Go to Privacy & security
3. Select Windows Security
4. Click App & browser control
5. Open Smart App Control settings
6. Set it to Off
7. Windows will ask **Are you sure?**. Confirm **Yes I'm sure**

## A5 - Socket Bind Fails
This may be caused by HTTP.sys, a kernel-mode HTTP listener built into Windows that prevents the Driver from binding to port 80. There are two approaches to resolving this conflict

To change the Port used by Alpaca Pilot:

* You can change the port used by Alpaca Pilot by changing config.toml line
    ```
    alpaca_pilot_http_port = 80                     
    ```

* Choose a free port like 8081. 
* When using a browser to navigate to Alpaca pilot you will need to pass the new port number. For Example: http://hostname:8081

To disable the http.sys driver if you dont need it:

* Disable the HTTP Service (Recommended). This prevents the kernel-mode driver from claiming port 80 upon startup.
* Open Registry Editor: Press Win + R, type regedit, and press Enter.
* Navigate to: HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\services\HTTP.
* Modify "Start": Locate the Start value, double-click it, and change the data to 4 (Disabled).
* Restart: Restart your computer to apply changes.

## A6 - Shortcut Startup Issue
If you have created a Windows shortcut to start the Polaris Alpaca Driver and a message briefly appears but the driver does not launch, follow the steps below to view the full error message:

1. Right-click the shortcut and select **Properties**.
2. In the **Target** field, click inside the text box, then press **Ctrl + A** to select all text.
3. Press **Ctrl + C** to copy the target string.
4. Open **PowerShell** or **Command Prompt**.
5. Press **Ctrl + V** to paste the copied target string, then press **Enter** to execute it.
6. Review any error message displayed in the console.
7. If necessary, correct the **Target** field in the shortcut based on the error details.

This process allows you to see the full error output, which may not remain visible when launching the shortcut normally.

## A7 - Alpaca Pilot Won't Load
If Alpaca Pilot suddenly won't load in your normal browser window — even though the Driver is confirmed running (e.g. `ping` to its address works, and a raw connection test to the port succeeds) — the browser itself is holding onto stale state for that address, not a problem with the Driver or your network. This is especially common after re-imaging the Pi, or after its IP address changes.

**How to tell it's this issue:** the page loads fine in an Incognito/Private window, but not in your normal one.

**Fix, in your normal (non-Incognito) browser window:**

1. Clear that site's cached data:
    * **Chrome/Edge**: Settings → Privacy and security → Site settings → search for the address (e.g. `192.168.50.161` or `ap.local`) → click it → **Delete data**.
    * **Safari on iOS/iPadOS**: Settings → Safari → Clear History and Website Data.
2. Check Chrome/Edge's secure-connections setting: Settings → Privacy and security → Security → **"Always use secure connections"** (sometimes shown as *"Warns you before connecting to sites that don't use a secure connection"*). If this is on, the browser can silently try to upgrade a plain HTTP address to HTTPS and fail — since the Driver may not be running HTTPS, this makes the page look completely unreachable. Turn it off, or add an exception for the Driver's address.
3. Always type the address with its scheme explicitly, e.g. `http://192.168.50.161:8080` rather than just `192.168.50.161:8080` — some browsers default an unscoped address to `https://`.
4. Close and fully reopen the browser afterwards.

If Alpaca Pilot doesn't load in an Incognito/Private window either, the browser may not be able to find the driver at all: see [C7 - Can't Reach ap.local](./troubleshooting-network.md#c7---cant-reach-aplocal).


## A8 - No Start at Boot
`setup.bat` registers a Task Scheduler task named `StartupAlpacaDriver`. If the driver is not running after the PC starts:

1. Check the task's last result. `0` means it ran without error.
    ```
    schtasks /Query /TN StartupAlpacaDriver /V /FO LIST
    ```

2. **If the result mentions a user name or password** (for example `0x8007052E`), you have changed your Windows password since running `setup.bat`. Run `setup.bat` again and enter the new password.
3. **If the task is missing**, you skipped it (`-s`) or pressed Enter at the password prompt. Run `setup.bat` again and enter your password. Blank passwords are not supported by Task Scheduler.
4. Start the driver by hand to see any error message. From the `alpaca-benro-polaris` folder run:
    ```
    .venv\Scripts\python.exe driver\main.py
    ```

5. Read the end of `alpaca-benro-polaris\logs\alpaca.log`. A line such as `port 80 is already in use` means another program, for example IIS or a web server, is using a port the driver needs. Stop that program, or choose different ports in Alpaca Pilot Network Settings.
6. To see Task Scheduler's own history, open **Task Scheduler** (`Win + R`, `taskschd.msc`), select `StartupAlpacaDriver`, and use **Enable All Tasks History** in the right-hand Actions panel.

## A9 - Driver Won't Download
If `setup.bat` stops at step 2 with an error like:
```
fatal: unable to access 'https://github.com/ogecko/alpaca-benro-polaris.git/': Failed to connect to github.com:443 after 21070 ms: Could not connect to server
```
then Git could not connect to GitHub, even though `setup.bat` tried twice. The cause is usually one of these:

* **Security software is blocking Git.** Antivirus suites with their own firewall (Norton, McAfee, ESET, Kaspersky, Bitdefender and others) often block a newly installed program without asking. In that software, allow `C:\Program Files\Git\mingw64\libexec\git-core\git-remote-https.exe` and `C:\Program Files\Git\cmd\git.exe`, or temporarily turn its firewall off, then run `setup.bat` again.
* **No internet, or a VPN is in the way.** Check that https://github.com opens in a browser, disconnect any VPN, and run `setup.bat` again.
* **A proxy that needs a login.** Set it for Git yourself, then run `setup.bat` again:
    ```
    git config --global http.proxy http://user:password@proxyhost:port
    ```
