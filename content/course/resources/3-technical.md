# Technical Setup

This guide walks you through everything you need to prepare your computer for the course. By the end, you will have:

- Python installed
- Visual Studio Code (VSCode) installed
- AI features (such as GitHub Copilot) disabled
- A course folder with a Python virtual environment
- Pyquist installed
- VSCode configured to use your virtual environment
- A Jupyter notebook that successfully runs Python code
- Assignment 1 downloaded and opened

If you follow these instructions carefully, you should not need to troubleshoot anything else before beginning the course.

:::{tip}
If you're having any issues with installations, come to OH, email us, or check the FAQ section below.
:::

## 1. Install Python

Download the latest stable version of Python from https://www.python.org/downloads/. Choose the correct installer for your operating system.


::::{tab-set}
:::{tab-item} Windows
1. Download the Windows installer.
2. Run the installer.
3. **Check the box that says "Add Python to PATH".**
4. Click **Install Now**.
5. When installation finishes, close the installer.
:::

:::{tab-item} macOS

1. Download the macOS installer.
2. Run the installer.
3. Accept the defaults.
4. After installation, open **Terminal** and verify the installation:

```bash
python3 --version
```

You should see something similar to

```text
Python 3.13.0
```
:::

:::{tab-item} Linux

Many Linux distributions already include Python.

Open a terminal and run

```bash
python3 --version
```

If Python is missing, install it using your distribution's package manager.

Ubuntu/Debian:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip
```

Verify installation afterwards:

```bash
python3 --version
```
:::
::::

---

## 2. Install Visual Studio Code

Download VSCode from https://code.visualstudio.com/ and follow their installation steps. Once installation is complete, launch VSCode.

## 3. Install the Jupyter Extension

Inside VSCode:

1. Click the **Extensions** icon on the left sidebar.
2. Search for **Jupyter**.
3. Install the extension published by Microsoft.

You may also wish to install the **Python** extension from Microsoft if it is not installed automatically.

## 4. Disable AI Assistance

This course is designed for you to write and understand your own code. AI tools can interfere with learning the material, though there are times in this course when it is allowed to use them. We will explicitly tell you when it is allowed to use AI tool, though your default assumption should be that they are not allowed. For now, please disable any AI coding assistants you have installed.

If GitHub Copilot or other AI assistants are installed:

1. Open the Extensions panel.
2. Search for **GitHub Copilot**.
3. Click the gear icon.
4. Select **Disable**.

If you have another AI coding extension installed (Cursor AI, Codeium, Continue, etc.), disable it as well.

You can always re-enable these extensions after the course if desired.

## 5. Create a Course Folder (optional, recommended)

We recommend keeping all your course files in a single directory. For the rest of the guide we will refer to this as **the course folder**, or `~/Documents/ICM`, but you should create it at a convenient location. Open this folder in VSCode using **File → Open Folder**. 

## 6. Create a Virtual Environment

Open a terminal inside VSCode and ensure your present working directory is the course folder, as this is where you are expected to keep your virtual environment. You can open a terminal by selecting ```Terminal → New Terminal```.

::::{tab-set}
:::{tab-item} Windows

```bash
python -m venv .venv
```
:::

:::{tab-item} macOS/Linux

```bash
python3 -m venv .venv
```
:::
::::

This creates a virtual environment named `.venv` inside your course folder.

## 7. Activate the Virtual Environment

::::{tab-set}
:::{tab-item} Windows

```bash
.venv\Scripts\activate
```
:::

:::{tab-item} macOS/Linux

```bash
source .venv/bin/activate
```
:::
::::

You should now see something similar to`(.venv)` at the beginning of your terminal prompt. Note that VSCode may automatically activate the virtual environment for you when you open a terminal in the future, but it is good to know how to do it manually. You can always deactivate the virtual environment by running `deactivate`.

## 8. Install Pyquist

With the virtual environment activated, install Pyquist:

```bash
pip install pyquist
```

Wait for installation to finish.

You can verify it by running

```bash
python -c "import pyquist"
```

If no error appears, installation was successful.
	
## 9. Connect VSCode to Your Virtual Environment

Press

```
Ctrl+Shift+P
```

(or `⌘+Shift+P` on macOS)

Search for

```
Python: Select Interpreter
```

Choose the interpreter located inside

```
.venv
```

It should look something like

```
.venv/bin/python
```

or

```
.venv\Scripts\python.exe
```

---

## 10. Create Your First Notebook

Create a new file named `hello.ipynb`

When prompted, choose the Python kernel from your virtual environment. In the first cell, type `print("Hello, world!")`

Run the cell by clicking the **Run All** button at the top, or pressing the triangle next to the cell. If everything is working correctly, you should see the output below the cell.

Congratulations! You now have Python, VSCode, Jupyter, and your virtual environment working together.

## 11. Download Assignment 1

1. Download the Assignment 1 ZIP file from the course website.
2. Move it into your course folder.
3. Extract (unzip) it.

Your folder should now look something like

```
~/Documents/ICM/
    .venv/
    Assignment1/
```

Open the Assignment 1 folder in VSCode and you're ready to begin.

## Frequently Asked Questions

:::{dropdown} VSCode can't find Python

Open the Command Palette and select

```
Python: Select Interpreter
```

Choose the interpreter inside `.venv`.
**Note:** Be sure to check the leading slash in the path. If you see a path like `/usr/bin/python` or `C:\Python39\python.exe`, you are not using the virtual environment. 
More subtly, if you see a path like `/.venv/bin/python`, you are _still_ not using the correct environment. For macOS and Linux, there should not be a leading slash before `.venv`.
:::

:::{dropdown} I accidentally installed packages globally

Activate your virtual environment and reinstall them there. You generally do **not** need to uninstall the global copy.
:::

:::{dropdown} My notebook is using the wrong Python

Click the kernel selector in the upper-right corner of the notebook and choose the interpreter from `.venv`.
:::

:::{dropdown} `pip` says the package is installed, but Python can't import it

This almost always means VSCode is using a different Python interpreter than the one where the package was installed.

Verify that:

- your virtual environment is activated
- VSCode is using the `.venv` interpreter
:::

:::{dropdown} Something still isn't working

Before asking for help, check:

- Is Python >=3.10 installed?
- Is your virtual environment activated?
- Is VSCode using the `.venv` interpreter?
- Is the notebook using the `.venv` kernel?
- Did `pip install pyquist` complete successfully?

If you've checked all of these and still have issues, include screenshots of the error and the commands you ran when asking for help.
:::