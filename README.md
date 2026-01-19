# KModUI

# KModUI

**KModUI** is a lightweight TUI-based tool for inspecting and modifying Linux kernel module parameters.

The goal of the project is to make kernel module parameter handling more approachable.

---

## Features

- Fuzzy-searchable list of **currently loaded kernel modules**
- Clear distinction between **read-only (RO)** and **runtime-writable (RW)** parameters
- Displays:
  - Current runtime values (via `sysfs`)
  - Parameter descriptions (via `modinfo`)
  - Persistent configuration (`/etc/modprobe.d/*.conf`)
- Edit runtime-writable parameters directly from the UI

---

## How It Works

KModUI does not introduce any custom kernel interfaces.
It combines existing some sources:

- **Loaded modules**:  
  `/sys/module`

- **Runtime parameters**:  
  `/sys/module/<module>/parameters/*`

- **Parameter metadata**:  
  `modinfo -p <module>`

- **Persistent configuration**:  
  `/etc/modprobe.d/*.conf`

Runtime changes affect the currently loaded module only.  
Persistent changes must be configured separately (currently read-only in the UI).

---

## Installation

### Requirements

- Linux
- Python 3.10+
- Kernel with `sysfs` enabled
- `modinfo` available (usually via `kmod` package)

It is recommended to run KModUI inside a Python virtual environment
to avoid polluting the system Python installation.

```bash
git clone https://github.com/<your-username>/kmodui.git
cd kmodui
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Running
```bash
python kmodui.py
``` 
No root privileges are required for browsing.
Editing runtime parameters may require elevated permissions depending on the parameter.


# Test Module (Dummy Driver)
This repository includes a small dummy kernel module under the `testmod/` directory.
It is intended for safely testing KModUI without touching real hardware drivers.

The test module exposes both:
- a **runtime-writable (RW)** parameter
- a **read-only (RO)** parameter

This makes it ideal for verifying how KModUI detects permissions and handles edits.

---

### Test Module Features

The module defines two parameters:
- `test_value`  
  - Type: `int`  
  - Permissions: `0644`  
  - Runtime-writable  
  - Can be modified via `/sys/module/test_mod/parameters/test_value`

- `readonly_value`  
  - Type: `int`  
  - Permissions: `0444`  
  - Read-only  
  - Cannot be modified at runtime

Both parameters are visible via:
```bash
modinfo -p test_mod
```


## Building the Test Module
Navigate to the `testmod/` directory:
```bash
cs testmod
make
```
this produces `test_mod.ko`

## Loading and unloading test_mod.ko module:
Load module to the kernel:
```bash
sudo insmod test_mod.ko
```
Verify it:
```bash
lsmod | grep test_mod
```

Unload the module:
```bash
sudo rmmod test_mod
```

Kernel log output can be inspected like this:
```bash
dmesg | tail
```



## Disclaimer

This tool allows interaction with kernel module parameters.
Incorrect values may lead to system instability or crashes.
Use with care.