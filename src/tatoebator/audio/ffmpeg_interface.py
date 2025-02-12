import subprocess
import sys

if sys.platform == "win32":
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
else:
    startupinfo = None


# TODO: does this still throw up a shell for half a second?
def convert_bitrate(input_file, output_file, target_bitrate, overwrite=False):
    subprocess.run(
        ['ffmpeg',
         '-y' if overwrite else ''
                                '-i', input_file,
         '-b:a', target_bitrate,
         output_file],
        shell=True, startupinfo=startupinfo
    )
