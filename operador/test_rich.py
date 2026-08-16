from rich.console import Console
from rich.panel import Panel
from rich.box import ROUNDED, DOUBLE, HEAVY
from rich.text import Text
from rich.layout import Layout
from rich.live import Live
import time

print(f"ROUNDED type: {type(ROUNDED)}")
print(f"DOUBLE type: {type(DOUBLE)}")
print(f"HEAVY type: {type(HEAVY)}")

console = Console()

try:
    p = Panel("Hello", box=ROUNDED)
    console.print(p)
    print("Panel with ROUNDED worked")
except Exception as e:
    print(f"Panel with ROUNDED failed: {e}")

try:
    layout = Layout()
    layout.split(Layout(name="a"), Layout(name="b"))
    layout["a"].update(Panel("A", box=DOUBLE))
    layout["b"].update(Panel("B", box=HEAVY))
    
    print("Starting Live...")
    with Live(layout, refresh_per_second=4, screen=False) as live:
        time.sleep(1)
        live.update(layout)
        time.sleep(1)
    print("Live worked")
except Exception as e:
    print(f"Live failed: {e}")
    import traceback
    traceback.print_exc()

