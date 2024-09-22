import os
import tkinter as tk
from tkinter import filedialog, messagebox

# Initialize tkinter
root = tk.Tk()
root.title("CNC Tab File Calibration")
root.geometry("800x500")

# Global variables to hold file data
data = []
input_file = None
output_file = None
cumulative_error_mode = tk.BooleanVar()  # Variable to track the state of cumulative error mode

# Function to load the .tab file
def load_file():
    global data, input_file

    # Ask user to select a file
    input_file = filedialog.askopenfilename(
        title="Select a TAB File",
        filetypes=(("TAB files", "*.tab"), ("All files", "*.*"))
    )

    if not input_file:
        return

    # Read file content
    with open(input_file, mode='r') as file:
        lines = file.readlines()

    # Skip headers and store data (from line 6 onwards)
    data = lines[5:]
    
    # Update label to show file loaded
    file_label.config(text=f"Loaded: {os.path.basename(input_file)}")

    # Enable navigation
    next_button.config(state=tk.NORMAL)
    save_button.config(state=tk.NORMAL)
    
    # Display first row
    display_row(0)

# Variables to hold row index
current_row = 0

# Function to display row
def display_row(row_index):
    global current_row

    if row_index >= 0 and row_index < len(data):
        current_row = row_index
        row = data[row_index].split()

        index_val.set(row[0])
        measured_val.set(row[1])
        correction_val.set(row[2])
        row_label.config(text=f"Row {current_row+1}/{len(data)}")

        # Enable/disable navigation buttons based on row index
        prev_button.config(state=tk.NORMAL if row_index > 0 else tk.DISABLED)
        next_button.config(state=tk.NORMAL if row_index < len(data) - 1 else tk.DISABLED)

# Function to update the current row with a new measured position
def update_row(event=None):
    global data, current_row

    # Get the new measured position from the user
    new_measured = new_measured_entry.get()

    # Validate input
    try:
        if input_file != None:
            new_measured_float = float(new_measured)
        else:
            messagebox.showerror("No file loaded", "Please, load a file!")
    except ValueError:
        messagebox.showerror("Invalid input", "Please enter a valid number for Measured Position")
        return

    # Parse current row
    row = data[current_row].split()
    index = float(row[0])
    prev_measured = float(row[1])
    prev_correction = float(row[2])

    # Calculate new correction
    new_error = index - new_measured_float
    
    if cumulative_error_mode.get():  # If cumulative mode is enabled
        new_correction = prev_correction + new_error
    else:  # Otherwise, override the correction
        new_correction = new_error

    # Update the row data
    data[current_row] = f"    {index:+.8f}    {new_measured_float:+.8f}    {new_correction:+.8f}\n"

    # Update the UI display
    measured_val.set(f"{new_measured_float:+.8f}")
    correction_val.set(f"{new_correction:+.8f}")

    # Clear the input field
    new_measured_entry.delete(0, tk.END)

    # Move to the next row automatically
    if current_row < len(data) - 1:
        display_row(current_row + 1)

# Function to save the updated file
def save_file():
    global output_file

    # Ask user where to save the updated file
    output_file = filedialog.asksaveasfilename(
        title="Save Updated TAB File",
        defaultextension=".tab",
        filetypes=(("TAB files", "*.tab"), ("All files", "*.*"))
    )

    if not output_file:
        return

    # Read the original headers and append the modified data
    with open(input_file, mode='r') as file:
        headers = file.readlines()[:5]  # First 5 lines (headers)

    with open(output_file, mode='w') as file:
        file.writelines(headers)  # Write headers
        file.writelines(data)     # Write updated data

    messagebox.showinfo("File Saved", f"Updated file saved as {os.path.basename(output_file)}")

# Create UI Components
file_label = tk.Label(root, text="No file loaded", pady=10)
file_label.pack()

row_label = tk.Label(root, text="Row 0/0", pady=10)
row_label.pack()

index_val = tk.StringVar()
measured_val = tk.StringVar()
correction_val = tk.StringVar()

# Index, Measured Position, Correction display
tk.Label(root, text="Axis position (mm):").pack()
tk.Label(root, textvariable=index_val, padx=10).pack()

tk.Label(root, text="Measured Position (mm):").pack()
tk.Label(root, textvariable=measured_val, padx=10).pack()

tk.Label(root, text="Correction (mm):").pack()
tk.Label(root, textvariable=correction_val, padx=10).pack()

# Entry to update Measured Position
new_measured_label = tk.Label(root, text="New Measured DRO Position (mm):")
new_measured_label.pack()
new_measured_entry = tk.Entry(root)
new_measured_entry.pack()
new_measured_entry.bind('<Return>', update_row)  # Bind Enter key to update the row

# Checkbox for cumulative error mode
cumulative_checkbox = tk.Checkbutton(root, text="Cumulative Error Mode", variable=cumulative_error_mode)
cumulative_checkbox.pack(pady=10)

# Update Button
update_button = tk.Button(root, text="Update Row", command=update_row)
update_button.pack(pady=10)

# Navigation Buttons
nav_frame = tk.Frame(root)
nav_frame.pack(pady=10)

prev_button = tk.Button(nav_frame, text="Previous", state=tk.DISABLED, command=lambda: display_row(current_row - 1))
prev_button.grid(row=0, column=0, padx=10)

next_button = tk.Button(nav_frame, text="Next", state=tk.DISABLED, command=lambda: display_row(current_row + 1))
next_button.grid(row=0, column=1, padx=10)

# Load file button
load_button = tk.Button(root, text="Load File", command=load_file)
load_button.pack(pady=10)

# Save file button
save_button = tk.Button(root, text="Save Updated File", state=tk.DISABLED, command=save_file)
save_button.pack(pady=10)

# Run the tkinter main loop
root.mainloop()
