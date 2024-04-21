import atexit
import datetime
import glob
import os
import shelve
import subprocess
from pathlib import Path
from typing import Callable, Dict, Literal, TypedDict


class StatusData(TypedDict):
    """
    Type for the status data that will be passed to the callback function
    """

    completion_percentage: int
    current_process: Literal[
        "INITIALIZING", "CONVERTING_CHUNKS", "MERGING", "CLEAN_UP", "FINISHED"
    ]
    message: str
    timestamp: datetime


# write docstring for class
class Converter:
    """
    Converts side-by-side fisheye video to equirectangular video
    """

    def __init__(self, callback: Callable[[StatusData], None]):
        """
        Initializes the Converter object

        Args:
            callback (Callable[[StatusData], None]): Callback function that will be called when the status of the conversion changes.
            StatusData is a dictionary with the following structure:
                - completion_percentage (int): The percentage of the conversion process that has been completed.
                - current_process (Literal["INITIALIZING", "CONVERTING_CHUNKS", "MERGING", "CLEAN_UP", "FINISHED"]): The current step in the conversion process.
                - message (str): A message about the status of the conversion process.
                - timestamp (datetime): The time of the status update.
        """

        self.callback = callback

        self.path_to_db = None
        self.path_to_conversion_dir = None
        self.fov = None
        self.video_name = None

        self.current_process = None
        atexit.register(self.__cleanup)

    def check_path_to_input_video(self, path_to_input_video: str) -> bool:
        """
        Checks if the path to the input video is correct

        Args:
            path_to_input_video (str): Path to the input video

        Returns:
            bool: True if the path is correct, False otherwise
        """

        if not os.path.isfile(path_to_input_video):
            return False
        # checking file extension
        extension = Path(path_to_input_video).suffix
        if extension not in [".mp4", ".avi", ".mkv", ".webm", ".mov"]:
            return False
        return True

    def check_path_to_output(self, path_to_output: str) -> bool:
        """
        Checks if the path to the output directory is correct

        Args:
            path_to_output (str): Path to the output directory

        Returns:
            bool: True if the path is correct, False otherwise
        """

        return os.path.exists(path_to_output)

    def check_path_to_conversion_dir(self, path_to_conversion_dir: str) -> bool:
        """
        Checks if the path to the conversion directory is correct and the database is not corrupted

        Args:
            path_to_conversion_dir (str): Path to the conversion directory

        Returns:
            bool: True if the path is correct, False otherwise
        """

        # Checking if the path exists
        if not os.path.exists(path_to_conversion_dir):
            return False

        # Checking if database files exists
        if not os.path.exists(
            os.path.join(path_to_conversion_dir, "conversion_data.dat")
        ):
            return False
        if not os.path.exists(
            os.path.join(path_to_conversion_dir, "conversion_data.dir")
        ):
            return False
        if not os.path.exists(
            os.path.join(path_to_conversion_dir, "conversion_data.bak")
        ):
            return False

        # Checking if the database is not corrupted
        path_to_db = os.path.join(path_to_conversion_dir, "conversion_data")
        try:
            with shelve.open(path_to_db) as db:
                if not isinstance(db["chunks_all"], list):
                    return False
                if not isinstance(db["chunks_to_convert"], list):
                    return False
                if not isinstance(db["fov"], int):
                    return False
                if not isinstance(db["video_name"], str):
                    return False
        except Exception:
            return False

        return True

    def check_fov(self, fov) -> bool:
        """
        Checks if the field of view is a valid integer from the range of 1 to 360

        Args:
            fov: Field of view

        Returns:
            bool: True if the fov is a valid integer, False otherwise
        """

        if not isinstance(fov, int):
            return False
        if fov < 1:
            return False
        if fov > 360:
            return False

        return True

    def new_conversion(
        self,
        path_to_input_video: str,
        path_to_output: str,
        fov: int,
    ):
        """
        Initializes a new conversion process

        Args:
            path_to_input_video (str): Path to the input video
            path_to_output (str): Path to the output directory
            fov (str): Field of view
            chunk_length (str): Length of each chunk in seconds
        """

        # checking paths
        if not self.check_path_to_input_video(path_to_input_video):
            raise FileNotFoundError("Input video not found")
        if not self.check_path_to_output(path_to_output):
            raise FileNotFoundError("Output directory not found")

        # checking fov
        if not self.check_fov(fov):
            raise TypeError("fov must be an integer from 1 to 360")
        self.fov = fov

        # getting input video name
        self.video_name = os.path.basename(path_to_input_video)
        video_name_without_extension = self.__get_name_without_extension(
            self.video_name
        )

        # creating conversion directory
        self.__update_status("INITIALIZING", "Creating conversion directory")
        current_time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.path_to_conversion_dir = os.path.join(
            path_to_output, f"{video_name_without_extension}_converted_{current_time}"
        )
        os.mkdir(self.path_to_conversion_dir)

        # cutting video into chunks
        self.__update_status("INITIALIZING", "Cutting video into chunks")
        chunk_length = 1
        extension = Path(path_to_input_video).suffix
        command = f'ffmpeg -i "{path_to_input_video}" -c copy -map 0 -segment_time {chunk_length} -f segment -reset_timestamps 1 "{self.path_to_conversion_dir}/%d{extension}"'
        self.__run_command(command)

        # getting reversed list of created chunks names
        chunk_paths = glob.glob(self.__get_full_path("[0-9]*"))

        def sort_key(path):
            filename = os.path.basename(path)
            basename, _ = os.path.splitext(filename)
            return int(basename)

        sorted_chunk_paths = sorted(chunk_paths, key=sort_key, reverse=True)
        chunks = [os.path.basename(file) for file in sorted_chunk_paths]

        # initializing database
        self.__update_status("INITIALIZING", "Creating conversion data files")
        self.path_to_db = self.__get_full_path("conversion_data")
        with shelve.open(self.path_to_db) as db:
            db["chunks_all"] = chunks
            db["chunks_to_convert"] = chunks
            db["fov"] = fov
            db["video_name"] = self.video_name

        # starting conversion
        self.__run_conversion()

    def continue_conversion(self, path_to_conversion_dir: str):
        """
        Continues a conversion process

        Args:
            path_to_conversion_dir (str): Path to the conversion directory
        """

        # saving paths
        self.path_to_conversion_dir = path_to_conversion_dir
        self.path_to_db = self.__get_full_path("conversion_data")

        # checking conversion directory
        if not self.check_path_to_conversion_dir(path_to_conversion_dir):
            raise FileNotFoundError("Conversion directory not found")

        # loading fov and video name
        with shelve.open(self.path_to_db) as db:
            self.fov = db["fov"]
            self.video_name = db["video_name"]

        # continuing the conversion
        self.__run_conversion()

    def __run_conversion(self):
        """
        Runs the conversion process
        """

        self.__convert_chunks()
        self.__merge_chunks()
        self.__delete_database()
        self.__update_status("FINISHED", "Conversion completed")

    def __convert_chunks(self):
        """
        Converts chunks to equirectangular format
        """

        # converting chunks
        convert_chunks = True
        while convert_chunks:

            # getting chunks to convert
            with shelve.open(self.path_to_db) as db:
                chunks_to_convert = db["chunks_to_convert"]
                fov = db["fov"]

            # breaking loop if no chunks to convert
            if not chunks_to_convert:
                convert_chunks = False
                break

            # converting chunk
            current_chunk = chunks_to_convert.pop()
            self.__update_status(
                "CONVERTING_CHUNKS", f"Converting chunk {current_chunk}"
            )
            current_chunk_name = self.__get_name_without_extension(current_chunk)
            current_chunk_path = self.__get_full_path(current_chunk)
            converted_chunk_path = self.__get_full_path(
                f"{current_chunk_name}_conv.mp4"
            )
            self.__remove_file(converted_chunk_path)
            command = f'ffmpeg -i "{current_chunk_path}" -filter:v "v360=input=fisheye:ih_fov={fov}:iv_fov={fov}:output=hequirect:in_stereo=sbs:out_stereo=sbs" -map 0 -c:v libx265 -crf 18 -pix_fmt yuv420p "{converted_chunk_path}"'
            self.__run_command(command)

            # updating database
            with shelve.open(self.path_to_db) as db:
                db["chunks_to_convert"] = chunks_to_convert

            # deleting original chunk
            os.remove(current_chunk_path)

    def __merge_chunks(self):
        """
        Merges converted chunks into one video file
        """

        self.__update_status(
            "MERGING", "Merging converted chunks into single video file"
        )

        # merging chunks
        with shelve.open(self.path_to_db) as db:
            chunks_all = db["chunks_all"]
            self.video_name = db["video_name"]
            video_name_without_extension = self.__get_name_without_extension(
                self.video_name
            )

        # creating txt file for ffmpeg
        concat_file_path = self.__get_full_path("chunks.txt")
        with open(concat_file_path, "w") as f:
            for chunk in reversed(chunks_all):
                f.write(f"file '{self.__get_name_without_extension(chunk)}_conv.mp4'\n")
        output_file_path = self.__get_full_path(
            f"{video_name_without_extension}_converted.mp4"
        )
        self.__remove_file(output_file_path)
        command = f'ffmpeg -f concat -safe 0 -i "{concat_file_path}" -c copy "{output_file_path}"'
        self.__run_command(command)

        # deleting files after merging
        self.__update_status("CLEAN_UP", "Removing chunk files")
        for chunk in chunks_all:
            os.remove(
                self.__get_full_path(
                    f"{self.__get_name_without_extension(chunk)}_conv.mp4"
                )
            )
        os.remove(concat_file_path)

    def __delete_database(self):
        """
        Deletes the database files
        """

        self.__update_status("CLEAN_UP", "Removing conversion data files")

        for filename in glob.glob(self.path_to_db + "*"):
            os.remove(filename)

    def __get_full_path(self, filename: str) -> str:
        """
        Returns the full path to a file in the conversion directory

        Args:
            filename (str): Name of the file or dirrectory

        Returns:
            str: Full path to the file
        """

        return os.path.join(self.path_to_conversion_dir, filename)

    def __get_name_without_extension(self, path: str) -> str:
        """
        Returns the name of the file without extension

        Args:
            path (str): Path to the file

        Returns:
            str: Name of the file without extension
        """

        return os.path.basename(path).split(".")[0]

    def __run_command(self, command: str):
        """
        Runs a subbprocess with some default settings

        Args:
            command (str): Command to run
        """

        self.current_process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            # check=True,
            shell=False,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.CREATE_NO_WINDOW,
        )
        self.current_process.wait()

    def __cleanup(self):
        """
        Stops the current subprocess
        """
        self.current_process.terminate()

    def __remove_file(self, path: str):
        """
        Removes a file if it exists

        Args:
            path (str): Path to the file
        """

        if os.path.exists(path):
            os.remove(path)

    def __update_status(
        self,
        current_process: Literal[
            "INITIALIZING", "CONVERTING_CHUNKS", "MERGING", "CLEAN_UP", "FINISHED"
        ],
        message: str = "",
    ):
        """
        Calculates the completion percentage and runs the callback with the updated status data.

        Args:
            curent_process (Literal["INITIALIZING", "CONVERTING_CHUNKS", "MERGING", "CLEAN_UP", "FINISHED"]): Current process of the conversion
            message (str): Message including details about the current process
        """

        current_time = datetime.datetime.now()

        if current_process == "INITIALIZING":
            status_data = {
                "video_name": self.video_name,
                "fov": self.fov,
                "completion_percentage": 0,
                "current_process": "INITIALIZING",
                "message": message,
                "timestamp": current_time,
            }
            self.callback(status_data)
        elif current_process == "CONVERTING_CHUNKS":
            with shelve.open(self.path_to_db) as db:
                chunks_all_length = len(db["chunks_all"])
                chunks_to_convert_length = len(db["chunks_to_convert"])
            merging_completion = (
                chunks_all_length - chunks_to_convert_length
            ) / chunks_all_length
            total_completion = 1 + round(merging_completion * 97)
            status_data = {
                "video_name": self.video_name,
                "fov": self.fov,
                "completion_percentage": total_completion,
                "current_process": "CONVERTING_CHUNKS",
                "message": message,
                "timestamp": current_time,
            }
            self.callback(status_data)
        elif current_process == "MERGING":
            status_data = {
                "video_name": self.video_name,
                "fov": self.fov,
                "completion_percentage": 98,
                "current_process": "MERGING",
                "message": message,
                "timestamp": current_time,
            }
            self.callback(status_data)
        elif current_process == "CLEAN_UP":
            status_data = {
                "video_name": self.video_name,
                "fov": self.fov,
                "completion_percentage": 99,
                "current_process": "CLEAN_UP",
                "message": message,
                "timestamp": current_time,
            }
            self.callback(status_data)
        elif current_process == "FINISHED":
            status_data = {
                "video_name": self.video_name,
                "fov": self.fov,
                "completion_percentage": 100,
                "current_process": "FINISHED",
                "message": message,
                "timestamp": current_time,
            }
            self.callback(status_data)


if __name__ == "__main__":

    def callback(data):
        """
        Callback function for the converter that prints the progress to the console
        """

        formatted_timestamp = data["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
        print(
            f"{formatted_timestamp} - completion: {data['completion_percentage']}% status: {data['current_process']} - {data['message']}"
        )

    def new_conversion_handler():
        """
        Asks the user for necessary information and starts a new conversion process
        """

        # Initializing the converter
        converter = Converter(callback=callback)

        # Asking user for the path to the input video
        path_to_input_video = input("Enter the path to the input video: ").strip()
        while not converter.check_path_to_input_video(path_to_input_video):
            print("Input video not found")
            path_to_input_video = input("Enter the path to the input video: ").strip()

        # Asking user for the path to the output directory
        print("")
        path_to_output = input("Enter the path to the output directory: ").strip()
        while not converter.check_path_to_output(path_to_output):
            print("Output directory not found")
            path_to_output = input("Enter the path to the output directory: ").strip()

        # Asking user for the field of view
        def check_fov(fov):
            try:
                fov_int = int(fov)
                return converter.check_fov(fov_int)
            except ValueError:
                return False

        print("")
        fov = input("Enter the field of view (Integer from 1 to 360): ").strip()
        while not check_fov(fov):
            print("Invalid field of view")
            fov = input("Enter the field of view (Integer from 1 to 360): ").strip()
        fov_int = int(fov)

        # Starting the conversion process
        print("")
        print("STARTING NEW CONVERSION")
        print("")
        converter.new_conversion(path_to_input_video, path_to_output, fov_int)

    def continue_conversion_handler():
        """
        Asks the user for necessary information and continues a conversion process
        """

        # Initializing the converter
        converter = Converter(callback=callback)

        # Asking user for the path to the conversion directory
        path_to_conversion_dir = input(
            "Enter the path to the conversion directory: "
        ).strip()
        while not converter.check_path_to_conversion_dir(path_to_conversion_dir):
            print("Conversion directory not found")
            path_to_conversion_dir = input(
                "Enter the path to the conversion directory: "
            ).strip()

        # Continuing the conversion process
        print("")
        print("CONTINUING CONVERSION")
        print("")
        converter.continue_conversion(path_to_conversion_dir)

    def main():
        """
        Asks the user for necessary information and starts the conversion process
        """
        print("WELCOME TO THE FISHEYE VIDEO CONVERTER")
        print("")

        # Asking user for the action
        print("AVIABLE ACTIONS:")
        print("1 - Start a new conversion")
        print("2 - Continue a conversion")
        print("")
        action = input("Enter the number of the action you want to perform: ").strip()
        while action not in ["1", "2"]:
            print("Invalid action")
            action = input(
                "Enter the number of the action you want to perform: "
            ).strip()
        print("")

        # running the selected action
        if action == "1":
            new_conversion_handler()
        elif action == "2":
            continue_conversion_handler()

    main()
