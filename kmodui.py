import os
import subprocess
from pathlib import Path

from thefuzz import process
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.widgets import Input, ListView, ListItem, Label, Static
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Button
from rich.text import Text

SYS_MODULE = Path("/sys/module")
MODPROBE_D = Path("/etc/modprobe.d")

STRINGS = {
    "search_placeholder": "Search module (fuzzy)…",
    "help": "Arrow keys switch focus between lists | Enter/Click edits selected | Esc clears search",
    "bind_edit": "Edit",
    "bind_switch": "Switch list",
    "bind_clear": "Clear search",
    "modal_title": "Edit parameter:",
    "modal_current": "Current value:",
    "btn_save": "Save",
    "btn_cancel": "Cancel",
    "warn_select_param": "Select a parameter on the right using the arrow keys",
    "warn_not_writable": "Parameter {name} is not writable at runtime",
    "ok_updated": "Updated: {name} = {value}",
    "err_write": "Error: {error}",
    "err_ui": "UI error: {error}",
    "module_title": "Module: {name}",
    "unreadable": "<Unreadable>",
    "no_desc": "No description available.",
}


# -----------------------------
# Data access
# -----------------------------

def get_loaded_modules() -> list[str]:
    if not SYS_MODULE.exists():
        return []
    return sorted([d.name for d in SYS_MODULE.iterdir() if d.is_dir()])


def get_etc_configs(module_name: str) -> dict[str, list[dict]]:
    configs: dict[str, list[dict]] = {}
    if not MODPROBE_D.exists():
        return configs

    for config_file in MODPROBE_D.glob("*.conf"):
        try:
            for raw in config_file.read_text().splitlines():
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) >= 3 and parts[0] == "options" and parts[1] == module_name:
                    for part in parts[2:]:
                        if "=" in part:
                            p_name, p_value = part.split("=", 1)
                            configs.setdefault(p_name, []).append(
                                {"value": p_value, "file": config_file.name, "line": raw.strip()}
                            )
        except Exception:
            continue

    return configs


def get_modinfo_details(module_name: str) -> dict[str, str]:
    """
    modinfo -p <mod> prints: param:description
    """
    try:
        result = subprocess.run(
            ["modinfo", "-p", module_name],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return {}
        out: dict[str, str] = {}
        for line in result.stdout.splitlines():
            clean = line.strip()
            if not clean or ":" not in clean:
                continue
            name, desc = clean.split(":", 1)
            out[name.strip()] = desc.strip()
        return out
    except Exception:
        return {}


def read_sysfs_params(module_name: str) -> list[dict]:
    param_dir = SYS_MODULE / module_name / "parameters"
    if not param_dir.exists():
        return []

    params: list[dict] = []
    for p in sorted(param_dir.iterdir(), key=lambda x: x.name):
        if not p.is_file():
            continue
            
        # Find stats info from file
        mode = p.stat().st_mode
        
        # check rw access (owner, group, others)
        is_globally_writable = bool(mode & 0o222)

        try:
            current = p.read_text().strip()
        except Exception:
            current = STRINGS["unreadable"]

        params.append(
            {
                "name": p.name,
                "current": current,
                "writable": is_globally_writable,
                "path": str(p),
            }
        )
    return params


def get_module_model(module_name: str) -> dict:
    descs = get_modinfo_details(module_name)
    etc = get_etc_configs(module_name)
    params = read_sysfs_params(module_name)

    merged = []
    for p in params:
        merged.append(
            {
                **p,
                "desc": descs.get(p["name"], STRINGS["no_desc"]),
                "persistent": etc.get(p["name"], []),
            }
        )

    return {"module": module_name, "params": merged}


# -----------------------------
# UI helpers
# -----------------------------

def format_module_details(model: dict) -> str:
    mod = model["module"]
    params = model["params"]

    if not params:
        return f"[b]{mod}[/b]\n\nNo parameters available (or no sysfs params)."

    lines = [f"[b]{mod}[/b]", ""]
    for p in params:
        rw = " (runtime writable)" if p["writable"] else ""
        lines.append(f"[b]{p['name']}[/b] = {p['current']}{rw}")
        lines.append(f"  Info: {p['desc']}")
        if p["persistent"]:
            for item in p["persistent"]:
                lines.append(f"  Persistent: {item['file']} -> {item['line']}")
        lines.append("")  # spacing
    return "\n".join(lines).strip()



class EditModal(ModalScreen):
    def __init__(self, param_name, current_value, param_path):
        super().__init__()
        self.param_name = param_name
        self.current_value = current_value
        self.param_path = param_path

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label(f"{STRINGS['modal_title']} [b]{self.param_name}[/b]"),
            Label(f"{STRINGS['modal_current']} {self.current_value}"),
            Input(value=self.current_value, id="new_value_input"),
            Horizontal(
                Button(STRINGS["btn_save"], variant="success", id="save"),
                Button(STRINGS["btn_cancel"], variant="error", id="cancel"),
            ),
            id="modal_dialog"
        )
        
    def on_mount(self) -> None:
        self.query_one("#new_value_input").focus()
        
    def on_input_changed(self, event: Input.Changed) -> None:
        event.stop()
        

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            new_val = self.query_one("#new_value_input", Input).value
            self.dismiss(new_val) # return value to main app 
        else:
            self.dismiss(None)

# -----------------------------
# Textual app
# -----------------------------

class KModUI(App):
    BINDINGS = [
        ("e", "edit_parameter", STRINGS["bind_edit"]),
        ("tab", "switch_list", STRINGS["bind_switch"]),
        ("escape", "clear_search", STRINGS["bind_clear"]),
    ]
    
    CSS = """
Screen {
    padding: 0 1;
}

#root {
    height: 1fr; 
    layout: horizontal;
}

#left, #right {
    height: 1fr;
}

#search {
    width: 100%;
    margin: 0 0 1 0;
}


#left {
    width: 35%;
    min-width: 25;
    border: tall $primary;
    padding: 0;
}


#left ListItem {
    padding: 0 1;
    height: 1;
}

ListItem:focus {
    background: $accent 20%;
    color: $text-primary;
}

#right {
    width: 65%;
    border: tall $primary;
    padding: 0;
}


.title {
    padding: 1;
    background: $primary;
    color: $text-primary;
    text-style: bold;
    text-align: center;
    width: 100%;
}

#param_list {
    background: $surface;
    margin: 0;
}


#param_list ListItem {
    padding: 0 1;
    height: auto;

    border-bottom: solid $primary 10%;
}

#help {
    color: $text-muted;
    text-align: center;
}

#modal_dialog {
    width: 50;
    height: auto;
    border: thick $primary;
    background: $surface;
    padding: 1;
    content-align: center middle;
}

#modal_dialog Horizontal {
    margin-top: 1;
    height: auto;
    align: center middle;
}
"""
    
    def action_clear_search(self) -> None:
        self.query_one("#search", Input).value = ""
        self.query_one("#search", Input).focus()

    def action_switch_list(self) -> None:
        left = self.query_one("#left")
        right = self.query_one("#param_list")
        if self.focused is left:
            right.focus()
        else:
            left.focus()

    def action_edit_parameter(self) -> None:
        try:
            plist = self.query_one("#param_list", ListView)
            if plist.index is None:
                self.notify(STRINGS["warn_select_param"], severity="warning")
                return
            
            selected_item = plist.children[plist.index]
            
            if not hasattr(selected_item, "param_data"):
                return
                
            p = selected_item.param_data

            if not p["writable"]:
                self.notify(STRINGS["warn_not_writable"].format(name=p["name"]), severity="warning")
                return

            def check_edit(new_value: str | None):
                if new_value is not None:
                    try:
                        # needs sudo
                        Path(p['path']).write_text(new_value)
                        self.notify(STRINGS["ok_updated"].format(name=p["name"], value=new_value))
                        self._load_details(self.current_model['module'])
                    except Exception as e:
                        self.notify(STRINGS["err_write"].format(error=e), severity="error")

            self.push_screen(EditModal(p['name'], p['current'], p['path']), check_edit)
        except Exception as e:
            self.notify(STRINGS["err_ui"].format(error=e), severity="error")
    

    all_modules: list[str] = []
    filtered: reactive[list[str]] = reactive([])

        
    def compose(self) -> ComposeResult:
        yield Vertical(
            Input(placeholder=STRINGS["search_placeholder"], id="search"),
            Horizontal(
                ListView(id="left"),
                Vertical(
                    Static(id="mod_title", classes="title"),
                    ListView(id="param_list"),
                    id="right"
                ),
                id="root",
            ),
            Label(STRINGS["help"], id="help"),
        )

    def on_mount(self) -> None:
        self.all_modules = get_loaded_modules()
        self.filtered = self.all_modules[:]  # show all initially
        self._render_list(self.filtered)

    def _render_list(self, names: list[str]) -> None:
        lv = self.query_one("#left", ListView)
        lv.clear()
        for n in names:
            item = ListItem(Label(n))
            item.data = n  # store the module name here
            lv.append(item)

        if names:
            lv.index = 0
            self._load_details(names[0])
            
        
    def _load_details(self, module_name: str) -> None:
        self.current_model = get_module_model(module_name)
        
        self.query_one("#mod_title", Static).update(
            f"[b][u]{STRINGS['module_title'].format(name=module_name)}[/u][/b]"
        )
        
        param_list = self.query_one("#param_list", ListView)
        param_list.clear()
        
        for p in self.current_model["params"]:
            # Create rich text object for colors
            
            content = Text()
            
            if p["writable"]:
                content.append("[RW] ", style="bold green")
                name_style = "green"
            else:
                content.append("[RO] ", style="dim white")
                name_style = "white"
                
            content.append(p["name"], style=f"bold {name_style}")
            content.append(f" = {p['current']}\n", style="bold yellow")
            content.append(p["desc"], style="italic dim")
            

            item = ListItem(Static(content))
            item.param_data = p
            param_list.append(item)
        


    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "search":
            return
        
        q = event.value.strip()
        if not q:
            self.filtered = self.all_modules[:]
            self._render_list(self.filtered)
            return

        # Fuzzy rank from all modules; show top N that are "relevant enough"
        results = process.extract(q, self.all_modules, limit=200)
        # Heuristic cutoff so list shrinks as query gets specific
        
        threshold = 65 if len(q) >= 2 else 50
        ranked = [name for name, score in results if score >= threshold]

        # Fallback: if threshold filters everything, show top 20 anyway
        if not ranked:
            ranked = [name for name, _ in results[:20]]

        self.filtered = ranked
        self._render_list(self.filtered)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id == "left":
            module_name = getattr(event.item, "data", None)
            if module_name:
                self._load_details(module_name)
        
        elif event.list_view.id == "param_list":
            self.action_edit_parameter()
            
if __name__ == "__main__":
    KModUI().run()