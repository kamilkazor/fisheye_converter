import os
import queue
import threading
from typing import Callable

import customtkinter

from converter import Converter


class ControledEntry(customtkinter.CTkEntry):
    """Entry widget that validates input using a control function.
    The control function is called each time the user enters a new character
    and should return True to accept the character or False to reject it.

    Args:
        master (widget): The parent widget.
        control_function (Callable[[str], bool]): The function that controls input.
        **kwargs: Additional keyword arguments for the CTkEntry widget.
    """

    def __init__(self, master, control_function: Callable[[str], bool], **kwargs):
        super().__init__(master, **kwargs)
        self.configure(validate="key")
        self.configure(validatecommand=(self.register(control_function), "%P"))


def validate_fov_entry(string: str) -> bool:
    """Checks the input string to see if it is a valid field of view value.

    Args:
        string (str): The string to check
    """
    if string == "":
        return True
    try:
        int_value = int(string)
        if int_value < 1:
            return False
        if int_value > 360:
            return False
    except:
        return False
    return True


class NewConversionTab(customtkinter.CTkFrame):
    """
    Tab view for collecting input values for a new conversion. Validates input and starts the conversion process.
    """

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        # Initializing the converter
        self.converter = Converter(lambda x: print(x))

        # Initializing conversion parameters
        self.input_video_path_var = customtkinter.StringVar()
        self.output_directory_path_var = customtkinter.StringVar()
        self.fov_var = customtkinter.StringVar()
        self.fov_var.set(190)

        # Video file selection
        self.input_video_frame = customtkinter.CTkFrame(master=self)
        self.input_video_frame.pack(fill="x", expand=1, padx=10, pady=10)

        self.input_video_button = customtkinter.CTkButton(
            master=self.input_video_frame,
            text="Select input video",
            command=self.select_input_video,
        )
        self.input_video_button.pack(padx=10, pady=10, fill="x")
        self.input_video_label = customtkinter.CTkLabel(
            master=self.input_video_frame, text="Selected:"
        )
        self.input_video_label.pack(padx=10, pady=10, anchor="w")

        # Output directory selection
        self.output_directory_frame = customtkinter.CTkFrame(master=self)
        self.output_directory_frame.pack(fill="x", expand=1, padx=10, pady=10)

        self.output_directory_button = customtkinter.CTkButton(
            master=self.output_directory_frame,
            text="Select output directory",
            command=self.select_output_directory,
        )
        self.output_directory_button.pack(padx=10, pady=10, fill="x")
        self.output_directory_label = customtkinter.CTkLabel(
            master=self.output_directory_frame, text="Selected:"
        )
        self.output_directory_label.pack(padx=10, pady=10, anchor="w")

        # Field of view input
        self.fov_frame = customtkinter.CTkFrame(master=self)
        self.fov_frame.pack(fill="x", expand=1, padx=10, pady=10)

        self.fov_input_label = customtkinter.CTkLabel(
            master=self.fov_frame, text="FOV (1-360):"
        )
        self.fov_input_label.pack(padx=10, pady=10, side="left")
        self.fov_input = ControledEntry(
            master=self.fov_frame,
            control_function=validate_fov_entry,
            width=40,
            justify="center",
            textvariable=self.fov_var,
        )
        self.fov_input.pack(padx=10, pady=10, side="left")

        # Start conversion button
        self.start_conversion_button = customtkinter.CTkButton(
            master=self, text="START CONVERSION", command=self.start_conversion
        )
        self.start_conversion_button.pack(padx=10, pady=10, fill="x")

        # Error label
        self.error_label = customtkinter.CTkLabel(
            master=self, text="", text_color="red"
        )

    def select_input_video(self):
        """Opens a file dialog to select a video file."""

        file_path = customtkinter.filedialog.askopenfilename()

        if not file_path:
            return

        self.input_video_path_var.set(file_path)
        self.input_video_label.configure(
            text=f"Selected: {self.input_video_path_var.get()}"
        )

        input_video_directory = os.path.dirname(self.input_video_path_var.get())
        self.output_directory_path_var.set(input_video_directory)
        self.output_directory_label.configure(
            text=f"Selected: {self.output_directory_path_var.get()}"
        )

    def select_output_directory(self):
        """Opens a file dialog to select an output directory."""

        directory_path = customtkinter.filedialog.askdirectory()

        if not directory_path:
            return

        self.output_directory_path_var.set(directory_path)
        self.output_directory_label.configure(
            text=f"Selected: {self.output_directory_path_var.get()}"
        )

    def start_conversion(self):
        """Starts the conversion process."""

        if not self.validate_variables():
            return
        self.master.master.master.start_new_conversion(
            self.input_video_path_var.get(),
            self.output_directory_path_var.get(),
            int(self.fov_var.get()),
        )

    def set_error_message(self, message: str):
        """Sets an error message to be displayed to the user.

        Args:
            message (str): The error message to display.
        """

        if message == "":
            self.error_label.configure(text="")
            self.error_label.pack_forget()
        else:
            self.error_label.configure(text=message)
            self.error_label.pack(padx=10, pady=10)

    def validate_variables(self) -> bool:
        """Validates the input variables and sets an error message if necessary."""

        # Checking input video
        if not self.input_video_path_var.get():
            self.set_error_message("Please select an input video.")
            return False
        elif not self.converter.check_path_to_input_video(
            self.input_video_path_var.get()
        ):
            self.set_error_message(
                "Input video cannot be processed. Please select a different file."
            )
            return False

        # Checking output directory
        if not self.output_directory_path_var.get():
            self.set_error_message("Please select an output directory.")
            return False
        elif not self.converter.check_path_to_output(
            self.output_directory_path_var.get()
        ):
            self.set_error_message(
                "Output directory cannot be opened. Please select a different directory."
            )
            return False

        # Checking field of view
        if not validate_fov_entry(self.fov_var.get()):
            self.error_label.configure(text="Please enter a valid field of view.")
            return False
        elif not self.converter.check_fov(int(self.fov_var.get())):
            self.error_label.configure(text="Field of view must be between 1 and 360.")
            return False

        # Removing error message
        self.set_error_message("")
        return True


class ContinueConversionTab(customtkinter.CTkFrame):
    """
    Tab view for continuing a conversion. Validates input and starts the conversion process.
    """

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        # Initializing the converter
        self.converter = Converter(lambda x: print(x))

        # Initializing conversion parameters
        self.conversion_directory_path_var = customtkinter.StringVar()

        # Conversion directory selection
        self.conversion_directory_frame = customtkinter.CTkFrame(master=self)
        self.conversion_directory_frame.pack(fill="x", expand=1, padx=10, pady=10)

        self.conversion_directory_button = customtkinter.CTkButton(
            master=self.conversion_directory_frame,
            text="Select conversion directory",
            command=self.select_conversion_directory,
        )
        self.conversion_directory_button.pack(padx=10, pady=10, fill="x")
        self.conversion_directory_label = customtkinter.CTkLabel(
            master=self.conversion_directory_frame, text="Selected:"
        )
        self.conversion_directory_label.pack(padx=10, pady=10, anchor="w")

        # Start conversion button
        self.start_conversion_button = customtkinter.CTkButton(
            master=self, text="START CONVERSION", command=self.start_conversion
        )
        self.start_conversion_button.pack(padx=10, pady=10, fill="x")

        # Error label
        self.error_label = customtkinter.CTkLabel(
            master=self, text="", text_color="red"
        )

    def select_conversion_directory(self):
        """Opens a file dialog to select a conversion directory."""

        directory_path = customtkinter.filedialog.askdirectory()

        if not directory_path:
            return

        self.conversion_directory_path_var.set(directory_path)
        self.conversion_directory_label.configure(
            text=f"Selected: {self.conversion_directory_path_var.get()}"
        )

    def start_conversion(self):
        """Starts the conversion process."""

        if not self.validate_variables():
            return

        self.master.master.master.continue_conversion(
            self.conversion_directory_path_var.get()
        )

    def set_error_message(self, message: str):
        """Sets an error message to be displayed to the user.

        Args:
            message (str): The error message to display.
        """

        if message == "":
            self.error_label.configure(text="")
            self.error_label.pack_forget()
        else:
            self.error_label.configure(text=message)
            self.error_label.pack(padx=10, pady=10)

    def validate_variables(self) -> bool:
        """Validates the input variables and sets an error message if necessary."""

        # Checking conversion directory
        if not self.conversion_directory_path_var.get():
            self.set_error_message("Please select an output directory.")
            return False
        elif not self.converter.check_path_to_conversion_dir(
            self.conversion_directory_path_var.get()
        ):
            self.set_error_message(
                "Invalid conversion directory. Please select a different directory."
            )
            return False

        # Removing error message
        self.set_error_message("")
        return True


class MyTabView(customtkinter.CTkTabview):
    """Tab view for the main window of the application. Contains two tabs:
    - New conversion
    - Continue conversion
    """

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        # create tabs
        self.add("new")
        self.add("continue")
        self.new_conversion_tab = NewConversionTab(master=self.tab("new"))
        self.new_conversion_tab.pack(fill="x", expand=1)
        self.continue_conversion_tab = ContinueConversionTab(
            master=self.tab("continue")
        )
        self.continue_conversion_tab.pack(fill="x", expand=1)


class ConversionProgressFrame(customtkinter.CTkFrame):
    """Frame for displaying the progress of a conversion"""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        # Title label
        self.title_label = customtkinter.CTkLabel(
            master=self, text="Converting video...", font=("Arial", 14)
        )
        self.title_label.pack(padx=10, pady=10)

        # Video label
        self.video_label = customtkinter.CTkLabel(
            master=self, text="Video:"
        )
        self.video_label.pack(padx=10, pady=0, anchor="w")

        # FOV label
        self.fov_label = customtkinter.CTkLabel(
            master=self, text="FOV:"
        )
        self.fov_label.pack(padx=10, pady=0, anchor="w")

        # Progress label
        self.progress_label = customtkinter.CTkLabel(
            master=self, text="Finished: 0%",
        )
        self.progress_label.pack(padx=10, pady=0, anchor="e")

        # Progress bar
        self.progress_bar = customtkinter.CTkProgressBar(master=self)
        self.progress_bar.pack(padx=10, pady=5, fill="x")
        self.progress_bar.set(0)

        # Logs
        self.logs_frame = customtkinter.CTkScrollableFrame(
            master=self, height=50, label_text="Logs:"
        )
        self.logs_frame.pack(fill="both", padx=10, pady=10)
        self.logs_label = customtkinter.CTkLabel(master=self.logs_frame, text="", justify="left")
        self.logs_label.pack(padx=10, pady=0, anchor="w")

    def update_progress(self, progress_data: dict):
        """Function for updating gui with new progress data."""

        # Updating the title label
        if progress_data["completion_percentage"] == 100:
            self.title_label.configure(text="Conversion finished!")

        # Updating video and fov labels
        self.video_label.configure(
            text=f"Video: {progress_data['video_name']}"
        )
        self.fov_label.configure(
            text=f"FOV: {progress_data['fov']}"
        )

        # Updating the progress label
        self.progress_label.configure(text=f"Finished: {progress_data['completion_percentage']}%")

        # Updating the progress bar
        self.progress_bar.set(progress_data["completion_percentage"] / 100)

        # Adding new log
        formated_time = progress_data["timestamp"].strftime("%H:%M:%S")
        new_log = f"{formated_time}  -  {progress_data["current_process"]}  -  {progress_data["message"]}\n"
        old_logs = self.logs_label.cget("text")
        combined_logs = new_log + old_logs
        self.logs_label.configure(text=combined_logs)


class App(customtkinter.CTk):
    """
    Main application window. Contains the tab view and the progress frame. Handles the conversion process.
    """

    def __init__(self):
        super().__init__()

        # Setting up the main window
        customtkinter.set_appearance_mode("dark")
        self.title("Fisheye converter")
        self.minsize(width=600, height=100)

        # Initializing the converter and progress queue
        self.thread = None
        self.progress_queue = queue.Queue()
        self.converter = Converter(self.progress_queue.put)

        self.tab_view = MyTabView(master=self)
        self.tab_view.pack(fill="both", expand=1, padx=10, pady=(0, 20))

        self.progress_frame = ConversionProgressFrame(master=self)
        # self.progress_frame.pack(fill="both", expand=1, padx=10, pady=20)

    def check_progress(self):
        """Checks the progress queue for new progress data and updates the progress frame."""

        # Emptying the queue and updating the progress frame
        while not self.progress_queue.empty():
            progress_data = self.progress_queue.get()
            self.progress_frame.update_progress(progress_data)

        # Checking if the conversion thread is still running
        if self.check_thread():
            self.after(100, self.check_progress)

    def start_new_conversion(
        self, input_video_path: str, output_directory_path: str, fov: int
    ):
        """Changes the view to the progress frame and starts a new conversion thread."""

        # Changing the view
        self.tab_view.pack_forget()
        self.progress_frame.pack(fill="both", expand=1, padx=10, pady=20)

        # Starting the conversion thread
        self.thread = threading.Thread(
            target=self.converter.new_conversion,
            args=(input_video_path, output_directory_path, fov),
        )
        self.thread.daemon = True
        self.thread.start()

        # Starting the progress check loop
        self.check_progress()

    def continue_conversion(self, conversion_directory_path: str):
        """Changes the view to the progress frame and starts a continue conversion thread."""

        # Changing the view
        self.tab_view.pack_forget()
        self.progress_frame.pack(fill="both", expand=1, padx=10, pady=20)

        # Starting the conversion thread
        self.thread = threading.Thread(
            target=self.converter.continue_conversion, args=(conversion_directory_path,)
        )
        self.thread.daemon = True
        self.thread.start()

        # Starting the progress check loop
        self.check_progress()

    def check_thread(self) -> bool:
        """Checks if the conversion thread is still running."""

        if self.thread and self.thread.is_alive():
            return True
        else:
            return False


# Running the application
app = App()
app.mainloop()

