# fisheye_converter
 
The simple application used for conversion of side by side fisheye vr videos into equirectangular. The app uses ffmpeg library under the hood and requires it to be installed your mashine. You can find ffmpeg installers on their official website: [https://ffmpeg.org/](https://ffmpeg.org/)

Since the conversion process might took some time the app is made the way that it allows to continue interruped conversion without losing progress. For simplyfying whole process the simple GUI was created with the use of customtkinter.

## How to run

You must have installed python on your mashine. Besides that the customtkinter library is needed, but I recommend setting up venv and installing dependencies from requirements.txt

After that you can start the app by running:

```bash
...\fisheye_converter> py app.py
```

You can also try to create executable file with the  pyinstaller:

```bash
...\fisheye_converter>pyinstaller app.py --onefile -w
```

## Preview

![fisheye_converter1](https://github.com/kamilkazor/fisheye_converter/assets/79405091/7456079f-764b-4e77-9917-1df4f3a103af)
