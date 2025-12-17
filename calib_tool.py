# CNC Ballscrew Auto Calibration Tool
# Uses an Arduino to read DRO values while sending incremental move commands to Acorn CNC software.
# Author: Jere Leman
# Date: 2025-06-10
# Revision: 1.0
# Requirements: pyserial, pyautogui, tkinter


# Imports
import serial
import time
import pyautogui
import re
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox

# Configurable parameters
ARDUINO_COM = None  # If None, script will ask for COM (e.g., COM5)
BAUDRATE = 115200   # Arduino serial baudrate
SETTLE_TIME = 3.0   # Seconds dwell time after move
CMD_DELAY = 0.15    # Seconds delay between commands
READ_TIMEOUT = 2.0  # Seconds read timeout

pyautogui.FAILSAFE = True


def choose_tab_file():
    """
    Open file dialog to choose .TAB file.
    
    """
    root = tk.Tk()
    root.withdraw()
    return filedialog.askopenfilename(
        title="Select CNC .tab file",
        filetypes=[("TAB files", "*.tab"), ("All files", "*.*")]
    )


def parse_tab_header(path):
    """
    Parse the .TAB file header and return parameters + full line list.
    
    Params:
        path (str): path to .TAB file
    
    Returns:
        entries (int): number of entries
        num_points (int): number of points
        step (float): step size
        unitscode (int): units code (21=mm, 20=inch)
        lines (list): full lines of the file

    """
    with open(path, 'r') as f:
        lines = [ln.rstrip('\n') for ln in f]

    unitscode = 21
    step = None
    entries = None
    axis = None

    for ln in lines:
        s = ln.strip()
        if s.upper().startswith('UNITS'):
            if 'MM' in s.upper():
                unitscode = 21
            elif 'INCH' in s.upper():
                unitscode = 20
        elif s.upper().startswith('INTERVAL'):
            try:
                step = float(s.split()[-1])
            except ValueError:
                pass
        elif s.upper().startswith('ENTRIES'):
            try:
                entries = int(s.split()[-1])
            except ValueError:
                pass
        elif s.upper().startswith('AXIS'):
            axis = s.split()[-1].upper()

        if s.startswith('+') or s.startswith('-'):
            break

    if step is None or entries is None:
        raise RuntimeError("Missing INTERVAL or ENTRIES in file header")

    num_points = entries
    print(f"Detected axis={axis}, step={step}, entries={entries}, unitscode={unitscode}")
    return entries, num_points, step, unitscode, lines


def open_serial(com):
    """
    Open serial connection to Arduino.
    
    Params:
        com (str): COM port (e.g., 'COM5')
    
    Returns:
        serial.Serial object
    """
    ser = serial.Serial(com, BAUDRATE, timeout=READ_TIMEOUT)
    time.sleep(1.0)
    ser.reset_input_buffer()
    return ser


def arduino_cmd(ser, cmd):
    """
    Send command to Arduino over serial.
    
    Params:
        ser: serial.Serial object
        cmd (str): command string   
    """
    ser.write((cmd + '\n').encode())
    ser.flush()


def arduino_read_pos(ser):
    """
    Read position from Arduino.
    
    Params:
        ser: serial.Serial object
    """
    arduino_cmd(ser, "READ")
    line = ser.readline().decode(errors='ignore').strip()
    if line.upper().startswith('POS'):
        try:
            return float(line.split()[1])
        except Exception:
            return None
    return None


def run_pass(ser, n_steps, step_size, direction_sign=1):
    """
    Perform incremental moves one by one, reading DRO each time.

    Params:
        ser: serial.Serial object
        n_steps (int): number of steps to perform
        step_size (float): step size in mm
    
    Returns:
        list: DRO readings after each step
    
    """
    readings = []

    # Enter MDI once before loop
    pyautogui.press('f3')
    time.sleep(CMD_DELAY)

    for i in range(n_steps):
        move = step_size if direction_sign > 0 else -step_size
        cmd = f"G91 X{move}"

        # Send incremental move
        pyautogui.typewrite(cmd, interval=0.02)
        pyautogui.press('enter')

        # Wait for physical movement + settling
        time.sleep(SETTLE_TIME)

        # Read DRO from Arduino
        dro = arduino_read_pos(ser)
        if dro is None:
            print(f"[WARN] step {i+1}: no DRO value, storing NaN")
            dro = float('nan')

        readings.append(dro)
        print(f"Step {i+1}/{n_steps}: DRO={dro:.4f}")

    # OPTIONAL: exit MDI mode
    pyautogui.press('esc')
    time.sleep(CMD_DELAY)

    return readings



def format_like(orig_str, value):
    """
    Preserve decimal places and plus sign style.

    Params:
        orig_str (str): original string to mimic
        value (float): value to format
    
    Returns:
        str: formatted string
    
    """
    s = orig_str.strip()
    plus = s.startswith('+')
    s_nosign = s.lstrip('+-')
    if '.' in s_nosign:
        nd = len(s_nosign.split('.', 1)[1])
        fmt = f"{{:.{nd}f}}"
    else:
        fmt = "{:.0f}"
    out = fmt.format(value)
    if plus and not out.startswith('-'):
        out = '+' + out
    return out


def write_tab_file(original_lines, forward_errors, reverse_errors, step_size, save_path):
    """
    Write updated .TAB file with new calibration errors.
    
    Params:
        original_lines (list): original .TAB file lines
        forward_errors (list): forward pass errors
        reverse_errors (list): reverse pass errors
        step_size (float): step size in mm
        save_path (str): path to save updated .TAB file

    """
    lines = original_lines[:]
    pattern = re.compile(r'^(\s*)([+-]?\S+?)(\s+)([+-]?\S+?)(\s+)([+-]?\S+?)(.*)$')

    data_start = None
    for idx, ln in enumerate(lines):
        s = ln.strip()
        if not s:
            continue
        toks = s.split()
        if len(toks) >= 3:
            try:
                float(toks[0].lstrip('+'))
                data_start = idx
                break
            except Exception:
                continue

    if data_start is None:
        raise RuntimeError("Could not find data block in .TAB")

    for i in range(len(forward_errors)):
        src_idx = data_start + i
        if src_idx >= len(lines):
            lines.append(f"{i * step_size:.4f} {forward_errors[i]:.4f} {reverse_errors[i]:.4f}")
            continue

        ln = lines[src_idx]
        m = pattern.match(ln)
        if m:
            g = m.groups()
            new_col2 = format_like(g[3], forward_errors[i])
            new_col3 = format_like(g[5], reverse_errors[i])
            lines[src_idx] = f"{g[0]}{g[1]}{g[2]}{new_col2}{g[4]}{new_col3}{g[6]}"
        else:
            leading_ws = re.match(r'^(\s*)', ln).group(1)
            lines[src_idx] = f"{leading_ws}{ln.strip().split()[0]} {forward_errors[i]:.4f} {reverse_errors[i]:.4f}"

    with open(save_path, 'w') as f:
        for ln in lines:
            f.write(ln if ln.endswith('\n') else ln + '\n')

    print(f"Saved new calibration file: {save_path}")


def main():
    print("=== CNC Ballscrew Auto Calibration ===")
    tab_path = choose_tab_file()
    if not tab_path:
        print("No TAB file chosen.")
        return

    entries, n_points, step_size, unitscode, lines = parse_tab_header(tab_path)

    global ARDUINO_COM
    if not ARDUINO_COM:
        root = tk.Tk()
        root.withdraw()
        ARDUINO_COM = simpledialog.askstring("Arduino COM", "Enter COM port (e.g. COM5):")
        if not ARDUINO_COM:
            print("No COM specified.")
            return

    ser = open_serial(ARDUINO_COM)
    print(f"Connected to Arduino on {ARDUINO_COM}")

    arduino_cmd(ser, "ZERO")
    time.sleep(0.2)
    ack = ser.readline().decode(errors='ignore').strip()
    print("Arduino:", ack)

    messagebox.showinfo("Ready",
                        f"Focus Acorn window and ensure machine is at HOME.\n"
                        f"{n_points} steps, {step_size}mm each.\nStarting in 5s...")

    for s in range(5, 0, -1):
        print("Starting in", s)
        time.sleep(1)

    # FORWARD PASS
    print("\n=== Forward Pass ===")
    forward_readings = run_pass(ser, n_points, step_size, +1)

    messagebox.showinfo("Forward Complete", "Forward pass done.\nClick OK for reverse.")
    print("\n=== Reverse Pass ===")
    reverse_readings = run_pass(ser, n_points, step_size, -1)

    # Compute per-step errors in microns
    commanded_positions = [i * step_size for i in range(n_points)]
    forward_errors = []
    reverse_errors = []

    for i in range(n_points):
        cmd = commanded_positions[i]   # mm
        f = forward_readings[i]        # mm (from Arduino)
        r = reverse_readings[i]        # mm

        # Centroid TB058 correct formula:
        err_f = (cmd - f)
        err_r = (cmd - r)

        forward_errors.append(err_f)
        reverse_errors.append(err_r)

    # Normalize to zero at home (first forward point)
    zero_offset = forward_errors[0]

    forward_errors = [e - zero_offset for e in forward_errors]
    reverse_errors = [e - zero_offset for e in reverse_errors]
    print("\nStep\tCmd(mm)\tFwdErr(um)\tRevErr(um)")

    # Save updated .TAB
    root = tk.Tk()
    root.withdraw()
    save_path = filedialog.asksaveasfilename(
        title="Save updated .TAB",
        defaultextension=".tab",
        filetypes=[("TAB files", "*.tab"), ("All files", "*.*")]
    )
    if not save_path:
        print("Save cancelled.")
        return

    write_tab_file(lines, forward_errors, reverse_errors, step_size, save_path)

    messagebox.showinfo("Done", f"Calibration done.\nFile saved to:\n{save_path}")


if __name__ == "__main__":
    main()
