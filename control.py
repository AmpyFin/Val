# control.py
"""
AmpyFin — Val Model
Control flags for the pipeline runtime.
Edit these booleans to change behavior (no CLI required).
"""

# --- Required by spec (original names) ---
Run_continous = True          # if False: run once; if True: run forever
Gui_mode = True               # if True: show PyQt5 GUI (best with Run_continous=False)
Broadcast_mode = False         # if True: broadcast JSON over UDP

broadcast_network = "127.0.0.1"
broadcast_port = 5002

# --- Loop timing ---
LOOP_SLEEP_SECONDS = 180       # delay between runs when Run_continous=True

# --- Back-compat/normalized constants used by stages ---
RUN_CONTINUOUS = bool(Run_continous)
GUI_MODE = bool(Gui_mode)
BROADCAST_MODE = bool(Broadcast_mode)
BROADCAST_NETWORK = broadcast_network
BROADCAST_PORT = int(broadcast_port)
